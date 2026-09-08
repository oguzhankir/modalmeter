"""Versioned inspection records with explicit evidence and media provenance."""

import math
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

NonEmptyText = Annotated[str, Field(min_length=1, pattern=r"\S")]


class EvidenceKind(StrEnum):
    OBSERVED = "observed"
    MEASURED = "measured"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Measurement(ContractModel):
    """A finite numeric value with an auditable source, scope, and method."""

    value: Annotated[int, Field(strict=True)] | Annotated[float, Field(strict=True)] | None
    unit: NonEmptyText
    evidence_kind: EvidenceKind
    source: NonEmptyText
    scope: NonEmptyText
    method: NonEmptyText
    unavailable_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.evidence_kind == EvidenceKind.UNAVAILABLE:
            if self.value is not None or self.unavailable_reason is None:
                raise ValueError("Unavailable evidence requires a null value and a reason.")
        elif self.value is None or self.unavailable_reason is not None:
            raise ValueError("Available evidence requires a value and no unavailable reason.")
        return self


class EvidenceDocument(ContractModel):
    """M0 evidence interchange; inspection/benchmark records are deferred."""

    schema_version: Literal["1.0"]
    record_kind: Literal["evidence"]
    measurements: dict[NonEmptyText, Measurement]


MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
MODEL_REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class InspectionConfig(ContractModel):
    path: Path
    model_id: str = MODEL_ID
    revision: str = MODEL_REVISION
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "modalmeter")
    processor_dir: Path | None = None
    offline: bool = False
    prompt: str = "Describe this media."
    sampling: Literal["model-default", "uniform"] = "model-default"
    frames: PositiveInt | None = None
    include_media: bool = False
    pixel_budget: PositiveInt | None = None
    max_file_bytes: PositiveInt = 256 * 1024**2
    max_pixels: PositiveInt = 16_777_216
    max_frames: PositiveInt = 128
    max_decoded_frames: PositiveInt = 10_000
    max_decoded_bytes: PositiveInt = 256 * 1024**2
    max_decode_seconds: Annotated[float, Field(gt=0)] = 30.0
    max_tensor_bytes: PositiveInt = 256 * 1024**2
    max_prompt_bytes: PositiveInt = 16_384

    @model_validator(mode="after")
    def validate_controls(self) -> Self:
        if self.sampling == "model-default" and self.frames is not None:
            raise ValueError("--frames requires --sampling uniform.")
        if self.sampling == "uniform" and self.frames is None:
            raise ValueError("Uniform sampling requires --frames.")
        if self.frames is not None and self.frames > self.max_frames:
            raise ValueError(f"Requested frames exceed the configured limit ({self.max_frames}).")
        if len(self.prompt.encode("utf-8")) > self.max_prompt_bytes:
            raise ValueError("Prompt exceeds the configured UTF-8 byte limit.")
        return self


class SourceFrame(ContractModel):
    ordinal: NonNegativeInt
    pts: Annotated[int, Field(strict=True)] | None = None
    time_base_numerator: PositiveInt | None = None
    time_base_denominator: PositiveInt | None = None
    timestamp_seconds: Annotated[float, Field(strict=True)] | None = None
    timestamp_unavailable_reason: NonEmptyText | None = None
    processor_timestamp_seconds: Annotated[float, Field(ge=0, strict=True)] | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        parts = (self.pts, self.time_base_numerator, self.time_base_denominator)
        if all(part is None for part in parts):
            if self.timestamp_seconds is not None or self.timestamp_unavailable_reason is None:
                raise ValueError("Missing PTS requires a null timestamp and an unavailable reason.")
        elif any(part is None for part in parts):
            raise ValueError("PTS and time-base numerator/denominator must be present together.")
        else:
            if self.timestamp_seconds is None or self.timestamp_unavailable_reason is not None:
                raise ValueError("Available PTS requires a timestamp and no unavailable reason.")
            assert self.pts is not None
            assert self.time_base_numerator is not None
            assert self.time_base_denominator is not None
            expected = float(
                self.pts * Fraction(self.time_base_numerator, self.time_base_denominator)
            )
            if not math.isclose(self.timestamp_seconds, expected, rel_tol=1e-12, abs_tol=1e-9):
                raise ValueError("Timestamp seconds disagree with the exact rational PTS.")
        return self


class ProcessedFrame(ContractModel):
    position: NonNegativeInt
    selected_position: NonNegativeInt
    source_ordinal: NonNegativeInt
    duplicated: bool
    duplication_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_duplication_reason(self) -> Self:
        if self.duplicated != (self.duplication_reason is not None):
            raise ValueError("Duplicated frames require a reason; ordinary frames must omit it.")
        return self


class MediaManifest(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    record_kind: Literal["media_manifest"] = "media_manifest"
    kind: Literal["image", "video"]
    sha256: Sha256
    display_name: str
    source_bytes: NonNegativeInt
    source_width: PositiveInt
    source_height: PositiveInt
    oriented_width: PositiveInt
    oriented_height: PositiveInt
    source_mode: str | None = None
    transforms: list[str] = Field(default_factory=list)
    source_frame_count: PositiveInt
    reported_frame_count: NonNegativeInt | None = None
    source_duration_seconds: Annotated[float, Field(ge=0, strict=True)] | None = None
    source_duration_reason: NonEmptyText | None = None
    average_fps: Annotated[float, Field(gt=0, strict=True)] | None = None
    fps_reason: NonEmptyText | None = None
    selected_frames: list[SourceFrame]
    requested_frames: PositiveInt | None = None
    selected_frame_count: PositiveInt
    processed_frame_count: PositiveInt
    processed_frames: list[ProcessedFrame]
    sampling_policy: str
    sampling_method: str
    timestamp_policy: str
    warnings: list[str] = Field(default_factory=list)
    decoder_versions: dict[str, str] = Field(default_factory=dict)
    privacy_mode: Literal["sanitized", "media_included"] = "sanitized"

    @model_validator(mode="after")
    def validate_frame_mapping(self) -> Self:
        if (self.source_duration_seconds is None) != (self.source_duration_reason is not None):
            raise ValueError("Unavailable duration requires a reason; available duration omits it.")
        if (self.average_fps is None) != (self.fps_reason is not None):
            raise ValueError("Unavailable FPS requires a reason; available FPS omits it.")
        if len(self.selected_frames) != self.selected_frame_count:
            raise ValueError("Selected frame count does not match the frame manifest.")
        if len(self.processed_frames) != self.processed_frame_count:
            raise ValueError("Processed frame count does not match the padding map.")
        for selected in self.selected_frames:
            if selected.ordinal >= self.source_frame_count:
                raise ValueError("Selected frame ordinal exceeds the decoded source frame count.")
            if selected.processor_timestamp_seconds is not None:
                if self.average_fps is None or not math.isclose(
                    selected.processor_timestamp_seconds,
                    selected.ordinal / self.average_fps,
                    rel_tol=1e-12,
                    abs_tol=1e-9,
                ):
                    raise ValueError(
                        "Processor timestamp disagrees with source ordinal / nominal FPS."
                    )
        seen: set[int] = set()
        mapped: set[int] = set()
        for index, frame in enumerate(self.processed_frames):
            if frame.position != index or frame.selected_position >= self.selected_frame_count:
                raise ValueError("Invalid processed-frame mapping.")
            if self.selected_frames[frame.selected_position].ordinal != frame.source_ordinal:
                raise ValueError("Processed frame references a different source identity.")
            if frame.duplicated != (frame.source_ordinal in seen):
                raise ValueError("Duplication flag disagrees with the processed source identities.")
            seen.add(frame.source_ordinal)
            mapped.add(frame.selected_position)
        if mapped != set(range(self.selected_frame_count)):
            raise ValueError("Every selected frame must map to at least one processed position.")
        return self


class ProcessorProvenance(ContractModel):
    model_id: str
    revision: str
    adapter_version: str
    dependency_versions: dict[str, str]
    artifact_sha256: dict[str, str]
    effective_settings: dict[str, JsonValue]
    runtime: dict[str, str]


class TokenAccounting(ContractModel):
    encoder_grid_positions: Measurement
    visual_placeholder_positions: Measurement
    grid_derived_visual_positions: Measurement
    nonpadding_prompt_positions: Measurement
    nonvisual_prompt_positions: Measurement
    vision_boundary_positions: Measurement
    video_timestamp_positions: Measurement
    user_text_positions: Measurement
    server_prompt_usage: Measurement
    server_completion_usage: Measurement
    placeholder_token_id: NonNegativeInt
    observed_placeholder_indices: list[NonNegativeInt]
    grid_matches_placeholders: bool


class Compatibility(ContractModel):
    modality: Literal["image", "video"]
    processor_verification: Literal["not_run", "processor_verified", "processor_mismatch"]
    processor_evidence: str
    server_parity: Literal[
        "server_parity_unverified", "server_parity_verified", "server_parity_mismatch"
    ] = "server_parity_unverified"
    server_parity_reason: str = "No live serving endpoint was tested."


class InspectionResult(ContractModel):
    schema_version: Literal["1.0"]
    record_kind: Literal["inspection"]
    tool_version: str
    run_id: UUID
    created_at: datetime
    completion_status: Literal["complete"] = "complete"
    manifest: MediaManifest
    processor: ProcessorProvenance
    token_accounting: TokenAccounting
    grid_thw: list[PositiveInt] = Field(min_length=3, max_length=3)
    processed_width: PositiveInt
    processed_height: PositiveInt
    prompt_sha256: Sha256
    template_sha256: Sha256
    prompt_retained: Literal[False] = False
    group_timestamp_labels: list[str] = Field(default_factory=list)
    thumbnails: list[str] = Field(default_factory=list)
    compatibility: Compatibility
    timings: dict[str, Measurement]
    unavailable_metrics: dict[str, Measurement]
    requested_settings: dict[str, JsonValue]
    warnings: list[str] = Field(default_factory=list)


class ConfigDifference(ContractModel):
    run_id: UUID
    field: str
    baseline_value: JsonValue
    compared_value: JsonValue
    category: Literal["intentional", "effective", "confounding"]


class ComparisonResult(ContractModel):
    schema_version: Literal["1.0"]
    record_kind: Literal["comparison"]
    tool_version: str
    run_id: UUID
    created_at: datetime
    results: list[InspectionResult] = Field(min_length=2, max_length=8)
    baseline_run_id: UUID
    comparable: bool
    incompatibilities: list[str]
    differences: list[ConfigDifference]
    warnings: list[str]
