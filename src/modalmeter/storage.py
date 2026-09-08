"""Bounded result loading and transactional, sanitized local artifacts."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import TypeAlias, cast

from pydantic import ValidationError

from modalmeter.errors import InspectionError, InvalidInput
from modalmeter.report import _PRIVATE_KEY, _clean_value, _thumbnail, compare_results, render_report
from modalmeter.schemas import ComparisonResult, InspectionResult

Result: TypeAlias = InspectionResult | ComparisonResult
MAX_RESULT_BYTES = 32 * 1024 * 1024
_RUN_FILES = {
    "inspection": {"inspection.json", "manifest.json", "report.html"},
    "comparison": {"comparison.json", "report.html"},
}


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidInput("Result JSON must contain a structured object.")
    return cast(dict[str, object], value)


def _identity(value: object, kind: str) -> dict[str, object]:
    data = _object(value)
    if data.get("schema_version") != "1.0":
        raise InvalidInput("Unsupported or missing result schema_version; expected 1.0.")
    if data.get("record_kind") != kind:
        raise InvalidInput(f"Unsupported or missing record_kind; expected {kind}.")
    return data


def _inspection_identity(value: object) -> None:
    data = _identity(value, "inspection")
    _identity(data.get("manifest"), "media_manifest")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    values: dict[str, object] = {}
    for key, value in pairs:
        if key in values:
            raise InvalidInput("Result JSON contains duplicate object keys.")
        values[key] = value
    return values


def _reject_nonfinite(value: str) -> None:
    raise InvalidInput("Result JSON contains a non-finite numeric value.")


def load_result(path: Path | str) -> Result:
    """Read a versioned inspection/comparison JSON file or an owned run directory."""
    source = Path(path)
    try:
        if source.is_symlink():
            raise InvalidInput("Result input must not be a symbolic link.")
        if source.is_dir():
            candidates = [source / "inspection.json", source / "comparison.json"]
            matches = [candidate for candidate in candidates if candidate.exists()]
            if len(matches) != 1:
                raise InvalidInput("Run directory must contain exactly one result JSON record.")
            source = matches[0]
        if source.is_symlink() or not source.is_file():
            raise InvalidInput(
                "Result input must be a regular JSON file or a completed run directory."
            )
        if source.stat().st_size > MAX_RESULT_BYTES:
            raise InvalidInput("Result JSON exceeds the 32 MiB input limit.")
        with source.open("rb") as handle:
            payload = handle.read(MAX_RESULT_BYTES + 1)
        if len(payload) > MAX_RESULT_BYTES:
            raise InvalidInput("Result JSON exceeds the 32 MiB input limit.")
        raw = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
        data = _object(raw)
        if data.get("record_kind") == "inspection":
            _inspection_identity(data)
            return InspectionResult.model_validate(data)
        if data.get("record_kind") == "comparison":
            _identity(data, "comparison")
            records = data.get("results")
            if not isinstance(records, list):
                raise InvalidInput("Comparison JSON must contain a list of inspection records.")
            for record in records:
                _inspection_identity(record)
            result = ComparisonResult.model_validate(data)
            if result.baseline_run_id != result.results[0].run_id:
                raise InvalidInput("Comparison baseline must identify the first embedded run.")
            return result
        raise InvalidInput("Unsupported or missing record_kind; expected inspection or comparison.")
    except (UnicodeError, json.JSONDecodeError, ValidationError, RecursionError) as exc:
        raise InvalidInput(
            "Invalid result JSON; verify the schema and required evidence fields."
        ) from exc
    except OSError as exc:
        raise InspectionError(
            "Could not read result JSON; check access to the supplied input."
        ) from exc


def sanitized_result(result: Result, *, include_media: bool = False) -> Result:
    """Return a validated export copy, retaining hashes but omitting private text."""
    records = result.results if isinstance(result, ComparisonResult) else [result]
    names = tuple(
        item.manifest.display_name
        for item in records
        if item.manifest.display_name != item.manifest.kind
    )
    data = _object(_clean_value(result.model_dump(mode="json"), names))
    exported = data["results"] if isinstance(result, ComparisonResult) else [data]
    for value, original in zip(cast(list[object], exported), records, strict=True):
        record = _object(value)
        manifest = _object(record["manifest"])
        manifest["display_name"] = manifest["kind"]
        manifest["privacy_mode"] = "media_included" if include_media else "sanitized"
        record["thumbnails"] = (
            [_thumbnail(item) or "" for item in original.thumbnails] if include_media else []
        )
    if isinstance(result, ComparisonResult):
        for value in cast(list[object], data["differences"]):
            difference = _object(value)
            if _PRIVATE_KEY.search(str(difference["field"]).replace(".", "_")):
                difference["baseline_value"] = "[omitted]"
                difference["compared_value"] = "[omitted]"
        return ComparisonResult.model_validate(data)
    return InspectionResult.model_validate(data)


def validate_output_directory(directory: Path | str, *, overwrite: bool = False) -> None:
    """Reject replacement of unrelated content before expensive inspection begins."""
    destination = Path(directory)
    if destination.is_symlink():
        raise InvalidInput("Output directory must not be a symbolic link.")
    if not destination.exists():
        return
    if not overwrite:
        raise InvalidInput("Output already exists. Choose a new output or pass --overwrite.")
    if not destination.is_dir():
        raise InvalidInput("Output must be a directory owned by a previous ModalMeter run.")
    existing = load_result(destination)
    expected = _RUN_FILES[existing.record_kind]
    if {item.name for item in destination.iterdir()} != expected:
        raise InvalidInput("Refusing to overwrite a directory with missing or unrelated files.")
    if any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
        raise InvalidInput("Refusing to overwrite a run containing symbolic links or non-files.")


def _write_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _json_bytes(result: Result) -> bytes:
    payload = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_RESULT_BYTES:
        raise InvalidInput("Result JSON exceeds the 32 MiB output limit.")
    return payload


def _write_run(result: Result, directory: Path, *, overwrite: bool, include_media: bool) -> Path:
    validate_output_directory(directory, overwrite=overwrite)
    clean = sanitized_result(result, include_media=include_media)
    payload = _json_bytes(clean)
    html = render_report(clean, include_media=include_media).encode("utf-8")
    staging: Path | None = None
    backup: Path | None = None
    reserved = False
    committed = False
    try:
        directory.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".modalmeter-staging-", dir=directory.parent))
        _write_bytes(staging / f"{clean.record_kind}.json", payload)
        if isinstance(clean, InspectionResult):
            _write_bytes(
                staging / "manifest.json",
                (clean.manifest.model_dump_json(indent=2) + "\n").encode(),
            )
        _write_bytes(staging / "report.html", html)
        if directory.exists():
            validate_output_directory(directory, overwrite=overwrite)
            backup = Path(tempfile.mkdtemp(prefix=".modalmeter-backup-", dir=directory.parent))
            backup.rmdir()
            os.replace(directory, backup)
        else:
            directory.mkdir()
            reserved = True
        try:
            os.replace(staging, directory)
            committed = True
        except BaseException:
            if reserved:
                directory.rmdir()
                reserved = False
            if backup is not None:
                os.replace(backup, directory)
                backup = None
            raise
        return directory
    except FileExistsError as exc:
        raise InvalidInput(
            "Output appeared during writing; choose a different output directory."
        ) from exc
    except OSError as exc:
        raise InspectionError(
            "Could not write the complete run; previous artifacts were preserved."
        ) from exc
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        if committed and backup is not None and backup.exists():
            shutil.rmtree(backup)


def write_inspection_run(
    result: InspectionResult,
    directory: Path | str,
    *,
    overwrite: bool = False,
    include_media: bool = False,
) -> Path:
    return _write_run(result, Path(directory), overwrite=overwrite, include_media=include_media)


def write_comparison_run(
    result: ComparisonResult,
    directory: Path | str,
    *,
    overwrite: bool = False,
    include_media: bool = False,
) -> Path:
    return _write_run(result, Path(directory), overwrite=overwrite, include_media=include_media)


def write_html_report(
    result: Result,
    path: Path | str,
    *,
    overwrite: bool = False,
    include_media: bool = False,
) -> Path:
    destination = Path(path)
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise InvalidInput("HTML output must be a regular file.")
    if destination.exists() and not overwrite:
        raise InvalidInput("HTML output already exists. Choose a new file or pass --overwrite.")
    html = render_report(result, include_media=include_media).encode("utf-8")
    temporary: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".modalmeter-report-", dir=destination.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(html)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            if destination.is_symlink() or (destination.exists() and not destination.is_file()):
                raise InvalidInput("HTML output changed during writing; refusing replacement.")
            os.replace(temporary, destination)
        else:
            # Linking within the same directory is atomic and refuses any existing
            # destination, including one created after the initial check.
            os.link(temporary, destination)
        return destination
    except FileExistsError as exc:
        raise InvalidInput(
            "HTML output appeared during writing; existing content was preserved."
        ) from exc
    except OSError as exc:
        raise InspectionError(
            "Could not write HTML output; previous content was preserved."
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def compare_runs(paths: list[Path | str]) -> ComparisonResult:
    if not 2 <= len(paths) <= 8:
        raise InvalidInput("Compare requires between two and eight inspection inputs.")
    results = [load_result(path) for path in paths]
    if any(not isinstance(result, InspectionResult) for result in results):
        raise InvalidInput("Comparison inputs must be inspection records, not comparison records.")
    try:
        return compare_results(cast(list[InspectionResult], results))
    except ValueError as exc:
        raise InvalidInput("Comparison requires distinct, valid inspection records.") from exc
