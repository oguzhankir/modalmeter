"""Versioned evidence primitives, not yet a complete inspection schema."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
