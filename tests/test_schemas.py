from pathlib import Path

import pytest
from pydantic import ValidationError

from modalmeter.schemas import (
    EvidenceDocument,
    EvidenceKind,
    Measurement,
    MediaManifest,
    ProcessedFrame,
    SourceFrame,
)


def evidence(value: int | float | None, **overrides: object) -> Measurement:
    data: dict[str, object] = {
        "value": value,
        "unit": "ms",
        "evidence_kind": "measured",
        "source": "synthetic unit fixture",
        "scope": "one operation",
        "method": "fixture value; not a runtime benchmark",
    }
    data.update(overrides)
    return Measurement.model_validate(data)


def test_zero_is_not_missing() -> None:
    assert evidence(0).value == 0
    with pytest.raises(ValidationError):
        evidence(None)


def test_unavailable_requires_null_and_reason() -> None:
    record = evidence(None, evidence_kind="unavailable", unavailable_reason="Not captured")
    assert record.evidence_kind == EvidenceKind.UNAVAILABLE
    for value, reason in [(0, "Not captured"), (None, None), (None, " ")]:
        with pytest.raises(ValidationError):
            evidence(value, evidence_kind="unavailable", unavailable_reason=reason)
    with pytest.raises(ValidationError):
        evidence(1, unavailable_reason="Contradictory")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "1"])
def test_rejects_nonfinite_and_coerced_values(value: object) -> None:
    with pytest.raises(ValidationError):
        Measurement.model_validate({**evidence(1).model_dump(), "value": value})


@pytest.mark.parametrize("field", ["source", "scope", "method", "unit"])
def test_requires_meaningful_provenance(field: str) -> None:
    with pytest.raises(ValidationError):
        evidence(1, **{field: " "})


def test_golden_roundtrip_and_schema_rejection() -> None:
    raw = (Path(__file__).parent / "fixtures/evidence-v1.json").read_text()
    doc = EvidenceDocument.model_validate_json(raw)
    assert EvidenceDocument.model_validate_json(doc.model_dump_json()) == doc
    assert doc.measurements["encoder_execution_ms"].value is None
    for version in ["2.0", "1.1", "0.9"]:
        with pytest.raises(ValidationError):
            EvidenceDocument.model_validate_json(raw.replace('"1.0"', f'"{version}"'))
    for field in ["schema_version", "record_kind"]:
        incomplete = doc.model_dump()
        incomplete.pop(field)
        with pytest.raises(ValidationError):
            EvidenceDocument.model_validate(incomplete)
    with pytest.raises(ValidationError):
        EvidenceDocument.model_validate({**doc.model_dump(), "unknown_field": 1})


def test_actual_rational_timestamps_require_coherent_availability() -> None:
    still = SourceFrame(ordinal=0, timestamp_unavailable_reason="Still image has no PTS.")
    assert still.timestamp_seconds is None
    frame = SourceFrame(
        ordinal=0,
        pts=-1000,
        time_base_numerator=1,
        time_base_denominator=1000,
        timestamp_seconds=-1.0,
    )
    assert frame.timestamp_seconds == -1.0  # Negative source origins are legitimate.
    for overrides in (
        {"timestamp_seconds": 0.0},
        {"timestamp_seconds": None},
        {"time_base_denominator": None},
        {"time_base_numerator": 0},
        {"timestamp_unavailable_reason": "Contradictory"},
    ):
        with pytest.raises(ValidationError):
            SourceFrame.model_validate({**frame.model_dump(), **overrides})
    for overrides in (
        {"timestamp_unavailable_reason": None},
        {"timestamp_unavailable_reason": " "},
        {"timestamp_seconds": 1.0},
        {"pts": 0},
    ):
        with pytest.raises(ValidationError):
            SourceFrame.model_validate({**still.model_dump(), **overrides})


def video_manifest() -> MediaManifest:
    return MediaManifest(
        kind="video",
        sha256="a" * 64,
        display_name="video",
        source_bytes=1,
        source_width=96,
        source_height=64,
        oriented_width=96,
        oriented_height=64,
        source_frame_count=2,
        source_duration_seconds=1.0,
        average_fps=2.0,
        selected_frames=[
            SourceFrame(
                ordinal=index,
                pts=index * 500,
                time_base_numerator=1,
                time_base_denominator=1000,
                timestamp_seconds=index / 2,
                processor_timestamp_seconds=index / 2,
            )
            for index in range(2)
        ],
        selected_frame_count=2,
        processed_frame_count=2,
        processed_frames=[
            ProcessedFrame(
                position=index,
                selected_position=index,
                source_ordinal=index,
                duplicated=False,
            )
            for index in range(2)
        ],
        sampling_policy="uniform",
        sampling_method="Two endpoints.",
        timestamp_policy="Actual PTS and ordinal/FPS retained separately.",
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"source_duration_seconds": -1.0},
        {"source_duration_seconds": None},
        {"source_duration_reason": "Contradictory"},
        {"average_fps": 0.0},
        {"average_fps": -2.0},
        {"average_fps": None},
        {"fps_reason": "Contradictory"},
    ],
)
def test_manifest_rejects_impossible_or_unexplained_source_facts(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MediaManifest.model_validate({**video_manifest().model_dump(), **updates})


def test_manifest_allows_known_zero_duration_and_explained_missing_metadata() -> None:
    zero = video_manifest().model_copy(update={"source_duration_seconds": 0.0})
    assert MediaManifest.model_validate_json(zero.model_dump_json()).source_duration_seconds == 0.0
    data = video_manifest().model_dump()
    data.update(
        source_duration_seconds=None,
        source_duration_reason="No stream duration was reported.",
        average_fps=None,
        fps_reason="No nominal frame rate was reported.",
    )
    for frame in data["selected_frames"]:
        frame["processor_timestamp_seconds"] = None
    assert MediaManifest.model_validate(data).average_fps is None


def test_manifest_rejects_out_of_source_range_and_inconsistent_processor_time() -> None:
    data = video_manifest().model_dump()
    data["selected_frames"][1]["ordinal"] = 10
    data["processed_frames"][1]["source_ordinal"] = 10
    with pytest.raises(ValidationError, match="source frame count"):
        MediaManifest.model_validate(data)
    data = video_manifest().model_dump()
    data["selected_frames"][1]["processor_timestamp_seconds"] = 99.0
    with pytest.raises(ValidationError, match="ordinal / nominal FPS"):
        MediaManifest.model_validate(data)


def test_duplicate_flags_and_reasons_must_match_real_mapping() -> None:
    with pytest.raises(ValidationError, match="require a reason"):
        ProcessedFrame(position=1, selected_position=0, source_ordinal=0, duplicated=True)
    with pytest.raises(ValidationError, match="require a reason"):
        ProcessedFrame(
            position=0,
            selected_position=0,
            source_ordinal=0,
            duplicated=False,
            duplication_reason="Contradictory",
        )
    data = video_manifest().model_dump()
    data["processed_frames"][0].update(duplicated=True, duplication_reason="No prior identity")
    with pytest.raises(ValidationError, match="Duplication flag"):
        MediaManifest.model_validate(data)
    data = video_manifest().model_dump()
    data["processed_frames"][1].update(
        source_ordinal=0,
        selected_position=0,
        duplicated=True,
        duplication_reason="Padding",
    )
    with pytest.raises(ValidationError, match="Every selected frame"):
        MediaManifest.model_validate(data)
