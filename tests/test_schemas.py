from pathlib import Path

import pytest
from pydantic import ValidationError

from modalmeter.schemas import EvidenceDocument, EvidenceKind, Measurement


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
