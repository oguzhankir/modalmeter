"""Actionable public errors without raw input paths or upstream payloads."""


class InvalidInput(ValueError):
    """Unsupported input or invalid user configuration (CLI exit 2)."""


class MissingExtra(InvalidInput):
    """An optional inspection dependency is missing."""


class InspectionError(RuntimeError):
    """Execution or artifact-integrity failure (CLI exit 1)."""
