"""Resource and CPU isolation regressions for observed native processor behavior."""

import importlib
import os
import socket
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from modalmeter import adapters
from modalmeter.adapters import QwenProcessorAdapter
from modalmeter.artifacts import ResolvedArtifacts, resolve_processor_artifacts
from modalmeter.errors import InvalidInput
from modalmeter.media import LoadedMedia, load_media
from modalmeter.schemas import InspectionConfig, MediaManifest, ProcessedFrame, SourceFrame


def synthetic_image(width: int, height: int) -> LoadedMedia:
    """Use metadata only; the guard must run before allocating input tensors."""
    manifest = MediaManifest(
        kind="image",
        sha256="a" * 64,
        display_name="image",
        source_bytes=1,
        source_width=width,
        source_height=height,
        oriented_width=width,
        oriented_height=height,
        source_frame_count=1,
        source_duration_reason="Still image has no duration.",
        fps_reason="Still image has no frame rate.",
        selected_frames=[SourceFrame(ordinal=0, timestamp_unavailable_reason="Still image.")],
        selected_frame_count=1,
        processed_frame_count=1,
        processed_frames=[
            ProcessedFrame(
                position=0,
                selected_position=0,
                source_ordinal=0,
                duplicated=False,
            )
        ],
        sampling_policy="not_applicable",
        sampling_method="One image.",
        timestamp_policy="Still image has no timeline.",
    )
    return LoadedMedia(manifest=manifest, content=None, thumbnails=[])


def test_downsampled_large_input_rejected_before_processor_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native 4096-square PIL processing retains two 48-MiB tensors pre-resize.

    A 60-MiB tensor budget must reject that input even when final pixels shrink
    to 256 square. The old guard reserved only one source tensor and accepted
    this configuration. These sizes were observed using the pinned processor.
    """
    adapter = object.__new__(QwenProcessorAdapter)
    adapter.config = InspectionConfig(
        path=Path("synthetic.png"),
        pixel_budget=65536,
        max_tensor_bytes=60 * 1024**2,
    )

    def unexpected_processing(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Resource guard must fail before prompt or tensor processing.")

    adapter.processor = SimpleNamespace(
        image_processor=SimpleNamespace(
            size={"shortest_edge": 65536, "longest_edge": 16777216},
            patch_size=16,
            merge_size=2,
            temporal_patch_size=2,
        ),
        apply_chat_template=unexpected_processing,
    )

    # The independent pinned resize observation for both square fixtures is
    # 256x256; no optional Torch/Transformers import is needed for this guard.
    def native_module(name: str) -> Any:
        if name == "torch":
            return SimpleNamespace(device=lambda name: nullcontext())
        return SimpleNamespace(smart_resize=lambda *args, **kwargs: (256, 256))

    monkeypatch.setattr(
        adapters,
        "importlib",
        SimpleNamespace(import_module=native_module),
    )
    with pytest.raises(InvalidInput, match="working-tensor budget"):
        adapter.process(synthetic_image(4096, 4096))
    # A small input really fits; do not accidentally reject every resize.
    adapter._configure_and_bound(synthetic_image(256, 256))


@pytest.fixture
def cached_artifacts(monkeypatch: pytest.MonkeyPatch) -> ResolvedArtifacts:
    directory = os.environ.get("MODALMETER_TEST_PROCESSOR_DIR")
    if not directory:
        pytest.skip("Set MODALMETER_TEST_PROCESSOR_DIR to an explicitly prepared offline cache.")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Guard regressions must not access the network.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    return resolve_processor_artifacts(
        cache_dir=Path(directory),
        processor_dir=Path(directory),
        offline=True,
    )


@pytest.mark.processor
@pytest.mark.parametrize("marker", ["<|placeholder|>", "<|image_pad|>", "<|video_pad|>"])
def test_internal_and_tokenizer_markers_rejected_before_prompt_mutation(
    cached_artifacts: ResolvedArtifacts,
    marker: str,
) -> None:
    # The native processor globally replaces its internal placeholder text;
    # preserving user literal text here would silently add visual positions.
    config = InspectionConfig(path=Path("synthetic.png"), prompt=f"Literal {marker} text.")
    with pytest.raises(InvalidInput, match="reserved tokenizer markers"):
        QwenProcessorAdapter(config, cached_artifacts)


@pytest.mark.processor
def test_processor_stays_cpu_without_changing_caller_default_device(
    cached_artifacts: ResolvedArtifacts,
    tmp_path: Path,
) -> None:
    image_module = importlib.import_module("PIL.Image")
    torch = importlib.import_module("torch")
    path = tmp_path / "image.png"
    image_module.new("RGB", (96, 64), (40, 100, 160)).save(path)
    config = InspectionConfig(path=path)
    adapter = QwenProcessorAdapter(config, cached_artifacts)
    loaded = load_media(config)
    with torch.device("meta"):
        batch, _ = adapter.process(loaded)
        assert torch.empty(0).device.type == "meta"
    assert batch["pixel_values"].device.type == "cpu"
    assert batch["image_grid_thw"].device.type == "cpu"
