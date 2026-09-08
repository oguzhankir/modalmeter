"""Offline artifact resolver behavior with tiny synthetic downloads."""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from modalmeter import artifacts
from modalmeter.artifacts import Artifact, ArtifactManifest
from modalmeter.errors import InspectionError, InvalidInput

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
ALLOWED_NAMES = {
    "config.json",
    "preprocessor_config.json",
    "video_preprocessor_config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "chat_template.json",
    "vocab.json",
    "merges.txt",
}


@dataclass(frozen=True)
class SyntheticArtifacts:
    manifest: ArtifactManifest
    payloads: dict[str, bytes]

    def populate(self, directory: Path) -> None:
        directory.mkdir(parents=True)
        for item in self.manifest.artifacts:
            (directory / item.file).write_bytes(self.payloads[item.url])


@pytest.fixture(autouse=True)
def reject_unmocked_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Unit tests must not download processor artifacts.")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


@pytest.fixture
def tiny_artifacts(monkeypatch: pytest.MonkeyPatch) -> SyntheticArtifacts:
    entries = []
    payloads = {}
    for name in sorted(ALLOWED_NAMES):
        payload = f"Original synthetic resolver fixture for {name}\n".encode()
        url = f"https://example.invalid/{name}"
        entries.append(
            Artifact(
                file=name,
                url=url,
                bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
        payloads[url] = payload
    manifest = ArtifactManifest(
        model_id=MODEL_ID, revision=REVISION, weight_files_downloaded=0, artifacts=entries
    )
    monkeypatch.setattr(artifacts, "artifact_manifest", lambda: manifest)
    return SyntheticArtifacts(manifest, payloads)


def test_packaged_manifest_is_exact_immutable_processor_allowlist() -> None:
    manifest = artifacts.artifact_manifest()
    assert manifest.model_id == MODEL_ID
    assert manifest.revision == REVISION
    assert manifest.weight_files_downloaded == 0
    assert len(manifest.artifacts) == 8
    assert {item.file for item in manifest.artifacts} == ALLOWED_NAMES
    for item in manifest.artifacts:
        assert item.url == f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{item.file}"
        assert item.bytes > 0
        assert len(item.sha256) == 64


@pytest.mark.parametrize(
    ("model_id", "revision"),
    [("Qwen/another-checkpoint", REVISION), (MODEL_ID, "main"), (MODEL_ID, "0" * 40)],
)
def test_unsupported_model_or_mutable_revision_rejected_before_network(
    tmp_path: Path, model_id: str, revision: str
) -> None:
    cache = tmp_path / "cache"
    with pytest.raises(InvalidInput, match="Supported processor"):
        artifacts.resolve_processor_artifacts(cache_dir=cache, model_id=model_id, revision=revision)
    assert not cache.exists()


def test_offline_cache_miss_never_creates_or_downloads(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    with pytest.raises(InvalidInput, match="not cached"):
        artifacts.resolve_processor_artifacts(cache_dir=cache, offline=True)
    assert not cache.exists()


def test_explicit_processor_directory_is_always_read_only(tmp_path: Path) -> None:
    source = tmp_path / "missing-explicit"
    cache = tmp_path / "cache"
    with pytest.raises(InvalidInput, match="not cached"):
        artifacts.resolve_processor_artifacts(cache_dir=cache, processor_dir=source, offline=False)
    assert not source.exists()
    assert not cache.exists()


def test_cached_allowlist_verified_without_network(
    tmp_path: Path, tiny_artifacts: SyntheticArtifacts
) -> None:
    cache = tmp_path / "cache"
    destination = cache / REVISION
    tiny_artifacts.populate(destination)
    result = artifacts.resolve_processor_artifacts(cache_dir=cache, offline=True)
    assert result.directory == destination
    assert result.hashes == {item.file: item.sha256 for item in tiny_artifacts.manifest.artifacts}
    assert {entry.name for entry in destination.iterdir()} == ALLOWED_NAMES


@pytest.mark.parametrize("damage", ["size", "hash", "missing", "extra-weight", "symlink"])
def test_invalid_cache_is_rejected_without_repair_or_download(
    tmp_path: Path, tiny_artifacts: SyntheticArtifacts, damage: str
) -> None:
    cache = tmp_path / "cache"
    destination = cache / REVISION
    tiny_artifacts.populate(destination)
    target = destination / "config.json"
    if damage == "size":
        target.write_bytes(b"bad")
    elif damage == "hash":
        target.write_bytes(b"X" + target.read_bytes()[1:])
    elif damage == "missing":
        target.unlink()
    elif damage == "extra-weight":
        (destination / "model.safetensors").write_bytes(b"not real weights")
    elif damage == "symlink":
        outside = tmp_path / "external-config"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
    with pytest.raises(InspectionError, match="artifact|allowlisted"):
        artifacts.resolve_processor_artifacts(cache_dir=cache, offline=False)
    assert {entry.name for entry in cache.iterdir()} == {REVISION}


def test_symlinked_processor_directory_is_rejected(
    tmp_path: Path, tiny_artifacts: SyntheticArtifacts
) -> None:
    original = tmp_path / "original"
    tiny_artifacts.populate(original)
    linked = tmp_path / "linked"
    linked.symlink_to(original, target_is_directory=True)
    with pytest.raises(InspectionError, match="regular directory"):
        artifacts.resolve_processor_artifacts(
            cache_dir=tmp_path / "cache", processor_dir=linked, offline=True
        )


def test_download_reads_only_eight_bounded_files_and_publishes_complete_cache(
    tmp_path: Path, tiny_artifacts: SyntheticArtifacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    destination = cache / REVISION
    requests: list[str] = []
    read_sizes: list[int] = []

    class Response(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            assert size is not None
            read_sizes.append(size)
            return super().read(size)

    def download(request: Any, timeout: int) -> Response:
        assert timeout == 30
        assert not destination.exists(), "A partial artifact cache must not become the final cache."
        requests.append(request.full_url)
        return Response(tiny_artifacts.payloads[request.full_url])

    monkeypatch.setattr(urllib.request, "urlopen", download)
    result = artifacts.resolve_processor_artifacts(cache_dir=cache)
    assert requests == [item.url for item in tiny_artifacts.manifest.artifacts]
    assert read_sizes == [item.bytes + 1 for item in tiny_artifacts.manifest.artifacts]
    assert result.directory == destination
    assert {path.name for path in cache.iterdir()} == {REVISION}
    assert {path.name for path in destination.iterdir()} == ALLOWED_NAMES
    for item in tiny_artifacts.manifest.artifacts:
        assert (destination / item.file).read_bytes() == tiny_artifacts.payloads[item.url]


@pytest.mark.parametrize("failure", ["too-short", "too-large", "wrong-hash", "network"])
def test_failed_download_removes_partial_cache_and_staging(
    tmp_path: Path,
    tiny_artifacts: SyntheticArtifacts,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    cache = tmp_path / "cache"
    calls: list[str] = []

    def download(request: Any, timeout: int) -> io.BytesIO:
        calls.append(request.full_url)
        data = tiny_artifacts.payloads[request.full_url]
        if len(calls) == 3:
            if failure == "network":
                raise urllib.error.URLError("synthetic offline transport failure")
            if failure == "too-short":
                data = data[:-1]
            elif failure == "too-large":
                data += b"excess"
            else:
                data = b"X" + data[1:]
        return io.BytesIO(data)

    monkeypatch.setattr(urllib.request, "urlopen", download)
    with pytest.raises(InspectionError, match="download|verification"):
        artifacts.resolve_processor_artifacts(cache_dir=cache)
    assert len(calls) == 3
    assert not (cache / REVISION).exists()
    assert list(cache.iterdir()) == []


def test_artifact_summary_omits_private_cache_path(
    tmp_path: Path, tiny_artifacts: SyntheticArtifacts
) -> None:
    destination = tmp_path / "private-cache" / REVISION
    tiny_artifacts.populate(destination)
    resolved = artifacts.resolve_processor_artifacts(
        cache_dir=destination.parent, processor_dir=destination, offline=True
    )
    summary = artifacts.artifact_summary(resolved)
    assert str(tmp_path) not in summary
    assert "weight_files_downloaded" in summary
    assert REVISION in summary
