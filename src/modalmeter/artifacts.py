"""A bounded, hash-verified allowlist for one immutable processor revision."""

import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from modalmeter.errors import InspectionError, InvalidInput
from modalmeter.schemas import MODEL_ID, MODEL_REVISION


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    url: str
    bytes: int
    sha256: str


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    revision: str
    weight_files_downloaded: int
    artifacts: list[Artifact]


@dataclass(frozen=True)
class ResolvedArtifacts:
    directory: Path
    hashes: dict[str, str]


def artifact_manifest() -> ArtifactManifest:
    raw = files("modalmeter").joinpath("data/processor-artifacts.json").read_text()
    return ArtifactManifest.model_validate_json(raw)


def validate_model(model_id: str, revision: str) -> None:
    if model_id != MODEL_ID or revision != MODEL_REVISION:
        raise InvalidInput(
            f"Supported processor: {MODEL_ID} at revision {MODEL_REVISION}. "
            "Other checkpoints/revisions need a verified adapter."
        )


def _validate_directory(directory: Path, manifest: ArtifactManifest) -> ResolvedArtifacts:
    expected = {item.file for item in manifest.artifacts}
    if directory.is_symlink() or not directory.is_dir():
        raise InspectionError("Processor cache must be a regular directory of verified artifacts.")
    if {path.name for path in directory.iterdir()} != expected:
        raise InspectionError(
            "Processor directory must contain exactly the eight allowlisted artifact files. "
            "Use 'modalmeter prepare' with a clean cache directory."
        )
    hashes: dict[str, str] = {}
    for item in manifest.artifacts:
        path = directory / item.file
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item.bytes:
            raise InspectionError(f"Invalid processor artifact size/type: {item.file}.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item.sha256:
            raise InspectionError(f"Processor artifact integrity mismatch: {item.file}.")
        hashes[item.file] = digest
    return ResolvedArtifacts(directory=directory, hashes=hashes)


def resolve_processor_artifacts(
    *,
    cache_dir: Path,
    model_id: str = MODEL_ID,
    revision: str = MODEL_REVISION,
    offline: bool = False,
    processor_dir: Path | None = None,
) -> ResolvedArtifacts:
    """Download only the pinned eight files, or verify a complete offline cache.

    Custom directories are always read-only and must contain exactly the allowlist.
    No hub snapshot, remote Python code, model class or weight API is involved.
    """
    validate_model(model_id, revision)
    manifest = artifact_manifest()
    destination = processor_dir if processor_dir is not None else cache_dir / revision
    if destination.exists():
        return _validate_directory(destination, manifest)
    if offline or processor_dir is not None:
        raise InvalidInput(
            "Processor artifacts are not cached. Run 'modalmeter prepare --cache-dir CACHE' "
            "with network access, then retry with the same cache and --offline."
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".processor-", dir=cache_dir))
    try:
        for item in manifest.artifacts:
            request = urllib.request.Request(item.url, headers={"User-Agent": "ModalMeter/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(item.bytes + 1)
            except (OSError, urllib.error.URLError) as exc:
                raise InspectionError(
                    f"Could not download processor artifact {item.file}. "
                    "Check network access or use a prepared offline cache."
                ) from exc
            if len(data) != item.bytes or hashlib.sha256(data).hexdigest() != item.sha256:
                raise InspectionError(
                    f"Downloaded processor artifact failed verification: {item.file}."
                )
            (staging / item.file).write_bytes(data)
        _validate_directory(staging, manifest)
        try:
            os.rename(staging, destination)
        except OSError:
            if not destination.exists():
                raise
            # Another process may have completed the identical immutable cache.
        return _validate_directory(destination, manifest)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def artifact_summary(resolved: ResolvedArtifacts) -> str:
    """Machine-readable provenance without a local path or remote credentials."""
    return json.dumps(
        {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "artifact_count": len(resolved.hashes),
            "weight_files_downloaded": 0,
            "artifact_sha256": resolved.hashes,
        },
        sort_keys=True,
        allow_nan=False,
    )
