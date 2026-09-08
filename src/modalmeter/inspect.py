"""Public CPU inspection API shared by the CLI and Python callers."""

import hashlib
import importlib.metadata
import time
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from modalmeter import __version__
from modalmeter.adapters import QwenProcessorAdapter, account_tokens, unavailable
from modalmeter.artifacts import resolve_processor_artifacts, validate_model
from modalmeter.errors import InspectionError, InvalidInput, MissingExtra
from modalmeter.media import load_media
from modalmeter.schemas import EvidenceKind, InspectionConfig, InspectionResult, Measurement


def _elapsed(start: int, method: str) -> Measurement:
    return Measurement(
        value=(time.perf_counter_ns() - start) / 1_000_000,
        unit="ms",
        evidence_kind=EvidenceKind.MEASURED,
        source="client time.perf_counter_ns",
        scope="local CPU inspection workflow",
        method=method,
    )


def inspect_media(config: InspectionConfig) -> InspectionResult:
    """Inspect one local input without loading model weights or contacting a server.

    Artifact preparation may download only the pinned allowlist unless offline=True.
    Paths, raw prompts, and media are omitted from the result by default.
    """
    workflow_start = time.perf_counter_ns()
    validate_model(config.model_id, config.revision)
    if not config.path.is_file():
        raise InvalidInput("Input must be an existing regular local media file.")
    if not 0 < config.path.stat().st_size <= config.max_file_bytes:
        raise InvalidInput("Input is empty or exceeds the configured file byte limit.")
    try:
        for dependency in ("transformers", "torch", "torchvision", "pillow", "av"):
            importlib.metadata.version(dependency)
    except importlib.metadata.PackageNotFoundError as exc:
        raise MissingExtra(
            "Inspection requires 'modalmeter[inspect]' or 'uv sync --extra inspect'."
        ) from exc
    timings: dict[str, Measurement] = {}
    start = time.perf_counter_ns()
    artifacts = resolve_processor_artifacts(
        cache_dir=config.cache_dir,
        model_id=config.model_id,
        revision=config.revision,
        offline=config.offline,
        processor_dir=config.processor_dir,
    )
    timings["artifact_preparation_ms"] = _elapsed(
        start, "Resolve/download and hash-check artifacts."
    )
    start = time.perf_counter_ns()
    adapter = QwenProcessorAdapter(config, artifacts)
    timings["processor_load_ms"] = _elapsed(start, "Load pinned processor/tokenizer on CPU.")
    start = time.perf_counter_ns()
    media = load_media(config, default_frame_indices=adapter.default_frame_indices)
    timings["media_preparation_ms"] = _elapsed(
        start,
        "Hash, decode, select frames, transform EXIF/RGB and optionally create thumbnails.",
    )
    start = time.perf_counter_ns()
    batch, template_hash = adapter.process(media)
    timings["cpu_processor_ms"] = _elapsed(
        start,
        "Apply chat template and one native CPU processor call, including tensor preparation.",
    )
    accounting = account_tokens(adapter.processor, batch, media.manifest.kind)
    grid_key = "image_grid_thw" if media.manifest.kind == "image" else "video_grid_thw"
    grid = [int(value) for value in batch[grid_key].tolist()[0]]
    provenance = adapter.provenance(media.manifest.kind)
    component = (
        adapter.processor.image_processor
        if media.manifest.kind == "image"
        else adapter.processor.video_processor
    )
    if media.manifest.kind == "video" and (
        grid[0] * int(component.temporal_patch_size) != media.manifest.processed_frame_count
    ):
        raise InspectionError(
            "Observed processor temporal grid disagrees with the padding manifest."
        )
    warnings = list(media.manifest.warnings)
    if not accounting.grid_matches_placeholders:
        warnings.append("Processor patch-grid/placeholder disagreement; inspect recorded counts.")
    if media.manifest.kind == "video":
        warnings.append(
            "Timestamp token positions are not isolated; timestamp text and boundaries are "
            "included in the nonvisual prompt residual. Native labels use index/FPS, not PTS."
        )
    requested: dict[str, JsonValue] = {
        name: value
        for name, value in config.model_dump(mode="json").items()
        if name
        not in {
            "path",
            "model_id",
            "revision",
            "cache_dir",
            "processor_dir",
            "offline",
            "prompt",
            "include_media",
        }
    }
    timings["workflow_ms"] = _elapsed(
        workflow_start,
        "API entry through accounting; excludes JSON/HTML serialization and output writes.",
    )
    return InspectionResult(
        schema_version="1.0",
        record_kind="inspection",
        tool_version=__version__,
        run_id=uuid4(),
        created_at=datetime.now(UTC),
        manifest=media.manifest,
        processor=provenance,
        token_accounting=accounting,
        grid_thw=grid,
        processed_width=grid[2] * int(component.patch_size),
        processed_height=grid[1] * int(component.patch_size),
        prompt_sha256=hashlib.sha256(config.prompt.encode("utf-8")).hexdigest(),
        template_sha256=template_hash,
        group_timestamp_labels=adapter.group_labels(batch)
        if media.manifest.kind == "video"
        else [],
        thumbnails=media.thumbnails,
        compatibility=adapter.compatibility(
            media.manifest.kind, accounting.grid_matches_placeholders
        ),
        timings=timings,
        unavailable_metrics={
            "time_to_first_output_ms": unavailable("No serving request was performed.", unit="ms"),
            "end_to_end_server_ms": unavailable("No serving request was performed.", unit="ms"),
            "gpu_memory_bytes": unavailable(
                "No GPU or serving-host telemetry was collected.", unit="bytes"
            ),
            "vision_encoder_ms": unavailable("No model/vision encoder was loaded.", unit="ms"),
            "answer_quality": unavailable(
                "No model output or task-quality evaluation was produced.", unit="score"
            ),
        },
        requested_settings=requested,
        warnings=warnings,
    )
