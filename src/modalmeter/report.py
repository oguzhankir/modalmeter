"""Portable, escaped reports and input comparisons from stored typed results.

This module uses only base dependencies. It never opens media, imports an
inspection processor, downloads an artifact, or measures inference performance.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import shlex
from datetime import UTC, datetime
from importlib.resources import files
from typing import Literal
from uuid import uuid4

from jinja2 import Environment, StrictUndefined
from pydantic import JsonValue

from modalmeter import __version__
from modalmeter.schemas import (
    ComparisonResult,
    ConfigDifference,
    InspectionConfig,
    InspectionResult,
    Measurement,
)

MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 512 * 1024

_URL = re.compile(r"\b(?:https?|file|s3)://[^\s<>\"']+", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"\b(?:Bearer|Basic)\s+[^\s<>\"']+|"
    r"\b(?:api[_-]?key|password|secret|authorization)\s*[:=]\s*[^\s<>\"']+",
    re.IGNORECASE,
)
_WINDOWS_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s<>\"']+")
_UNIX_PATH = re.compile(r"(?<![\w:])/(?:[^/\s<>\"']+/)*[^/\s<>\"']+")
_PRIVATE_KEY = re.compile(
    r"(?:^|[_.])(?:prompt|messages|content|raw_output|output_text)$|"
    r"(?:^|_)(?:path|filename|display_name|raw_prompt|raw_text|prompt_text|"
    r"authorization|credential|api_key|password|secret|endpoint|url|uri)(?:$|_)",
    re.IGNORECASE,
)
_DATA_URI = re.compile(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})\Z")


def _clean_text(value: str, names: tuple[str, ...] = ()) -> str:
    """Omit local identifiers without trusting filenames or warning text as HTML."""
    for name in names:
        if name:
            value = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", "[media name omitted]", value)
    value = _URL.sub("[URL omitted]", value)
    value = _CREDENTIAL.sub("[credential omitted]", value)
    value = _WINDOWS_PATH.sub("[path omitted]", value)
    return _UNIX_PATH.sub("[path omitted]", value)


def _clean_value(value: object, names: tuple[str, ...] = ()) -> object:
    if isinstance(value, str):
        return _clean_text(value, names)
    if isinstance(value, dict):
        return {
            _clean_text(str(key), names): (
                "[omitted]" if _PRIVATE_KEY.search(str(key)) else _clean_value(item, names)
            )
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_clean_value(item, names) for item in value]
    return value


def _pretty(value: object, names: tuple[str, ...] = ()) -> str:
    return json.dumps(_clean_value(value, names), indent=2, sort_keys=True, ensure_ascii=False)


def _number(value: int | float | None) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def _thumbnail(value: str | None) -> str | None:
    """Accept only bounded raster data URIs, never SVG or a network address."""
    if value is None or len(value) > MAX_THUMBNAIL_BYTES * 4 // 3 + 64:
        return None
    match = _DATA_URI.fullmatch(value)
    if match is None:
        return None
    try:
        data = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        return None
    signatures = {
        "png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpeg": data.startswith(b"\xff\xd8\xff"),
        "webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    }
    return value if len(data) <= MAX_THUMBNAIL_BYTES and signatures[match[1]] else None


def _metric(label: str, measurement: Measurement, names: tuple[str, ...]) -> dict[str, str]:
    return {
        "label": label,
        "value": _number(measurement.value),
        "unit": _clean_text(measurement.unit, names),
        "kind": measurement.evidence_kind.value,
        "method": _clean_text(measurement.method, names),
        "reason": _clean_text(measurement.unavailable_reason or "", names),
    }


def _fact(label: str, value: object, names: tuple[str, ...] = ()) -> dict[str, str]:
    return {"label": label, "value": _clean_text(str(value), names)}


def _inspection_view(result: InspectionResult, include_media: bool) -> dict[str, object]:
    manifest = result.manifest
    tokens = result.token_accounting
    names = () if manifest.display_name == manifest.kind else (manifest.display_name,)
    visual = tokens.visual_placeholder_positions
    prompt = tokens.nonpadding_prompt_positions
    encoder = tokens.encoder_grid_positions
    input_facts = [
        _fact("Input", f"{manifest.kind.title()} · {manifest.sha256[:12]}"),
        _fact("Source dimensions", f"{manifest.source_width} × {manifest.source_height} px"),
        _fact("After orientation", f"{manifest.oriented_width} × {manifest.oriented_height} px"),
        _fact("Processed dimensions", f"{result.processed_width} × {result.processed_height} px"),
        _fact("Source size", f"{manifest.source_bytes:,} bytes"),
        _fact("Transforms", ", ".join(manifest.transforms) or "None reported", names),
    ]
    if manifest.kind == "video":
        reported_frames = (
            str(manifest.reported_frame_count)
            if manifest.reported_frame_count is not None
            else "Unavailable"
        )
        duration = _number(manifest.source_duration_seconds)
        if manifest.source_duration_seconds is not None:
            duration += " seconds"
        else:
            duration += f" — {manifest.source_duration_reason or 'Duration was not captured.'}"
        input_facts.extend(
            [
                _fact("Source duration", duration, names),
                _fact(
                    "Decoded / reported frames",
                    f"{manifest.source_frame_count} / {reported_frames}",
                ),
                _fact("Average FPS", _number(manifest.average_fps)),
                _fact("Timestamp policy", manifest.timestamp_policy, names),
            ]
        )
    processor_facts = [
        _fact("Model", result.processor.model_id, names),
        _fact("Immutable revision", result.processor.revision, names),
        _fact("Adapter", result.processor.adapter_version, names),
        _fact("Grid [T, H, W]", str(result.grid_thw)),
        _fact("Processor check", result.compatibility.processor_verification),
        _fact("Server parity", result.compatibility.server_parity),
    ]
    frames: list[dict[str, object]] = []
    for index, frame in enumerate(manifest.selected_frames):
        lines: list[str] = []
        if manifest.kind == "video":
            if frame.timestamp_seconds is None:
                lines.append("Source PTS: unavailable")
                lines.append(frame.timestamp_unavailable_reason or "No presentation timestamp")
            else:
                lines.append(f"Source PTS: {_number(frame.timestamp_seconds)} s")
                if frame.pts is not None:
                    lines.append(
                        f"Exact: {frame.pts} × "
                        f"{frame.time_base_numerator}/{frame.time_base_denominator} s"
                    )
            lines.append(f"Processor: {_number(frame.processor_timestamp_seconds)} s")
        processed = [item for item in manifest.processed_frames if item.selected_position == index]
        lines.append("Processed positions: " + ", ".join(str(item.position) for item in processed))
        lines.extend(
            f"Duplicate: {item.duplication_reason or 'upstream temporal padding'}"
            for item in processed
            if item.duplicated
        )
        thumbnail = None
        if include_media and index < len(result.thumbnails):
            thumbnail = _thumbnail(result.thumbnails[index])
        frames.append(
            {
                "label": f"Selection {index + 1} · source #{frame.ordinal}",
                "alt": f"Selected {manifest.kind} frame {index + 1}",
                "lines": [_clean_text(line, names) for line in lines],
                "thumbnail": thumbnail,
            }
        )
    token_metrics = [
        _metric("Vision encoder grid positions", encoder, names),
        _metric("Visual embedding placeholder positions", visual, names),
        _metric("Grid-derived visual positions", tokens.grid_derived_visual_positions, names),
        _metric("Complete non-padding processed prompt", prompt, names),
        _metric("Nonvisual prompt residual", tokens.nonvisual_prompt_positions, names),
        _metric("Vision boundary positions", tokens.vision_boundary_positions, names),
        _metric("Video timestamp positions", tokens.video_timestamp_positions, names),
        _metric("Isolated user-text positions", tokens.user_text_positions, names),
        _metric("Server-reported prompt usage", tokens.server_prompt_usage, names),
        _metric("Server-reported completion usage", tokens.server_completion_usage, names),
    ]
    runtime_metrics = [
        _metric(key.replace("_", " ").capitalize(), value, names)
        for key, value in {**result.timings, **result.unavailable_metrics}.items()
    ]
    # A stored inspection with an empty metrics mapping must still expose the
    # missing serving measurements rather than make them disappear from the UI.
    runtime_metrics.extend(
        {
            "label": label,
            "value": "Unavailable",
            "unit": unit,
            "kind": "unavailable",
            "method": "",
            "reason": reason,
        }
        for label, unit, reason in (
            ("Serving latency", "ms", "No serving endpoint request was made."),
            ("Vision encoder execution time", "ms", "No model forward pass was executed."),
            ("GPU memory", "bytes", "No device or server memory measurement was captured."),
            ("Answer quality", "evaluation", "No model answer or task-specific evaluation exists."),
        )
    )
    provenance_facts = [
        _fact("Run ID", result.run_id),
        _fact("Created", result.created_at.isoformat()),
        _fact("Schema / tool", f"{result.schema_version} / {result.tool_version}"),
        _fact("Source SHA-256", manifest.sha256),
        _fact("Prompt SHA-256", result.prompt_sha256),
        _fact("Template SHA-256", result.template_sha256),
        _fact("Processor evidence", result.compatibility.processor_evidence, names),
        _fact("Server parity evidence", result.compatibility.server_parity_reason, names),
    ]
    warnings = list(dict.fromkeys([*manifest.warnings, *result.warnings]))
    if manifest.source_duration_seconds is None and manifest.source_duration_reason:
        warnings.append(manifest.source_duration_reason)
    if manifest.average_fps is None and manifest.fps_reason:
        warnings.append(manifest.fps_reason)
    if include_media and any(_thumbnail(item) is None for item in result.thumbnails):
        warnings.append("An invalid, oversized, or unsupported thumbnail was omitted.")
    visual_fraction = None
    if prompt.value and visual.value is not None and 0 <= visual.value <= prompt.value:
        visual_fraction = round(100 * visual.value / prompt.value, 2)
    duplicates = sum(frame.duplicated for frame in manifest.processed_frames)
    frame_summary = f"{manifest.selected_frame_count} / {manifest.processed_frame_count}"
    frame_note = f"{duplicates} repeated or temporally padded positions"
    if manifest.kind == "image":
        frame_summary = (
            f"{manifest.source_width} × {manifest.source_height} → "
            f"{result.processed_width} × {result.processed_height}"
        )
        frame_note = "Width × height, pixels; processor owns resizing"
    settings = {
        "requested_settings": result.requested_settings,
        "effective_settings": result.processor.effective_settings,
        "dependency_versions": result.processor.dependency_versions,
        "decoder_versions": manifest.decoder_versions,
        "processor_artifact_sha256": result.processor.artifact_sha256,
        "runtime": result.processor.runtime,
    }
    evidence = {
        "manifest": manifest.model_dump(mode="json"),
        "grid_thw": result.grid_thw,
        "group_timestamp_labels": result.group_timestamp_labels,
        "token_accounting": tokens.model_dump(mode="json"),
        "compatibility": result.compatibility.model_dump(mode="json"),
    }
    reproduction_args = [
        "modalmeter",
        "inspect",
        "LOCAL_MEDIA_PATH",
        "--offline",
        "--output",
        "NEW_RUN_DIRECTORY",
        "--processor-dir",
        "LOCAL_PROCESSOR_DIRECTORY",
        "--prompt-file",
        "LOCAL_PROMPT_FILE",
        "--model",
        result.processor.model_id,
        "--revision",
        result.processor.revision,
    ]
    if manifest.kind == "video":
        reproduction_args.extend(["--sampling", manifest.sampling_policy])
        if manifest.sampling_policy == "uniform" and manifest.requested_frames is not None:
            reproduction_args.extend(["--frames", str(manifest.requested_frames)])
    pixel_budget = result.requested_settings.get("pixel_budget")
    if isinstance(pixel_budget, int):
        reproduction_args.extend(["--pixel-budget", str(pixel_budget)])
    for setting, value in result.requested_settings.items():
        if setting.startswith("max_") and setting in InspectionConfig.model_fields:
            if value != InspectionConfig.model_fields[setting].default:
                reproduction_args.extend(["--" + setting.replace("_", "-"), str(value)])
    if include_media:
        reproduction_args.append("--include-media")
    reproduction = (
        "# Replace LOCAL_* placeholders; output must be a new directory.\n"
        + shlex.join(reproduction_args)
        + f"\n# Source SHA-256: {manifest.sha256}"
        + f"\n# Prompt SHA-256: {result.prompt_sha256}"
    )
    requested_frames = (
        str(manifest.requested_frames) if manifest.requested_frames is not None else "model default"
    )
    return {
        "kind": manifest.kind,
        "heading": f"{manifest.kind.title()} input · {manifest.sha256[:12]}",
        "short_id": str(result.run_id)[:8],
        "visual_count": _number(visual.value),
        "visual_evidence": visual.evidence_kind.value,
        "prompt_count": _number(prompt.value),
        "prompt_evidence": prompt.evidence_kind.value,
        "encoder_count": _number(encoder.value),
        "encoder_evidence": encoder.evidence_kind.value,
        "visual_fraction": visual_fraction,
        "selected_count": manifest.selected_frame_count,
        "processed_count": manifest.processed_frame_count,
        "frame_summary": frame_summary,
        "frame_note": frame_note,
        "input_facts": input_facts,
        "processor_facts": processor_facts,
        "sampling_summary": _clean_text(
            f"Sampling: {manifest.sampling_policy} · requested: "
            f"{requested_frames}"
            f" · selected: {manifest.selected_frame_count}"
            f" · processed: {manifest.processed_frame_count}",
            names,
        ),
        "padding_summary": (
            f"{duplicates} processed positions repeat a selected source frame. "
            "The complete duplication map is preserved in the frame manifest."
            if duplicates
            else ""
        ),
        "frames": frames,
        "token_metrics": token_metrics,
        "runtime_metrics": runtime_metrics,
        "provenance_facts": provenance_facts,
        "warnings": [_clean_text(warning, names) for warning in warnings],
        "settings_json": _pretty(settings, names),
        "evidence_json": _pretty(evidence, names),
        "reproduction": _clean_text(reproduction, names),
    }


def _flatten(value: dict[str, JsonValue], prefix: str) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}"
        if isinstance(item, dict) and item:
            result.update(_flatten(item, name))
        else:
            result[name] = item
    return result


def _comparison_fields(result: InspectionResult) -> dict[str, JsonValue]:
    manifest = result.manifest
    fields: dict[str, JsonValue] = {
        "manifest.kind": manifest.kind,
        "manifest.sha256": manifest.sha256,
        "prompt_sha256": result.prompt_sha256,
        "template_sha256": result.template_sha256,
        "processor.model_id": result.processor.model_id,
        "processor.revision": result.processor.revision,
        "processor.adapter_version": result.processor.adapter_version,
        "processor.dependency_versions": dict(result.processor.dependency_versions),
        "processor.artifact_sha256": dict(result.processor.artifact_sha256),
        "manifest.decoder_versions": dict(manifest.decoder_versions),
        "manifest.source_dimensions": [manifest.source_width, manifest.source_height],
        "manifest.oriented_dimensions": [manifest.oriented_width, manifest.oriented_height],
        "manifest.transforms": list(manifest.transforms),
        "manifest.source_frame_count": manifest.source_frame_count,
        "manifest.source_duration_seconds": manifest.source_duration_seconds,
        "manifest.average_fps": manifest.average_fps,
        "manifest.timestamp_policy": manifest.timestamp_policy,
        "processor.runtime": dict(result.processor.runtime),
        "effective.grid_thw": list(result.grid_thw),
        "effective.processed_width": result.processed_width,
        "effective.processed_height": result.processed_height,
        "effective.selected_frame_count": manifest.selected_frame_count,
        "effective.processed_frame_count": manifest.processed_frame_count,
        "effective.selected_frames": [
            frame.model_dump(mode="json") for frame in manifest.selected_frames
        ],
        "effective.processed_frames": [
            frame.model_dump(mode="json") for frame in manifest.processed_frames
        ],
        "effective.group_timestamp_labels": list(result.group_timestamp_labels),
        "effective.sampling_policy": manifest.sampling_policy,
        "effective.sampling_method": manifest.sampling_method,
    }
    fields.update(_flatten(result.requested_settings, "requested"))
    fields.update(_flatten(result.processor.effective_settings, "effective.processor"))
    return fields


def compare_results(results: list[InspectionResult]) -> ComparisonResult:
    """Compare each explicitly identified variant with the first input baseline.

    This compares processor input facts only. An incompatible baseline retains
    every run and difference, while HTML omits cross-run arithmetic deltas.
    """
    if not 2 <= len(results) <= 8:
        raise ValueError("Compare requires between two and eight inspection results.")
    validated = [InspectionResult.model_validate(item.model_dump(mode="json")) for item in results]
    if len({item.run_id for item in validated}) != len(validated):
        raise ValueError("Comparison requires distinct run IDs; do not compare a run with itself.")
    baseline = validated[0]
    baseline_fields = _comparison_fields(baseline)
    differences: list[ConfigDifference] = []
    incompatibilities: list[str] = []
    warnings = [
        "Inspection-only comparison: serving latency, GPU memory, "
        "and answer quality are unavailable.",
        "Server configuration and media transport are unknown; serving parity is not established.",
    ]
    for item in validated:
        if item.compatibility.processor_verification == "processor_mismatch":
            incompatibilities.append(
                f"Run {item.run_id}: processor correctness mismatch prevents a trusted comparison."
            )
        elif item.compatibility.processor_verification == "not_run":
            warnings.append(f"Run {item.run_id}: processor reference verification was not run.")
        if not item.processor.dependency_versions or not item.processor.artifact_sha256:
            incompatibilities.append(
                f"Run {item.run_id}: processor version or artifact provenance is incomplete."
            )
    intentional_fields = {"requested.sampling", "requested.frames", "requested.pixel_budget"}
    for variant in validated[1:]:
        variant_fields = _comparison_fields(variant)
        changed: set[str] = set()
        for field in sorted(baseline_fields.keys() | variant_fields.keys()):
            old, new = baseline_fields.get(field), variant_fields.get(field)
            if old == new:
                continue
            changed.add(field)
            category: Literal["intentional", "effective", "confounding"]
            if field in intentional_fields:
                category = "intentional"
            elif field.startswith("effective."):
                category = "effective"
            else:
                category = "confounding"
                if field != "processor.runtime":
                    incompatibilities.append(
                        f"Run {variant.run_id}: {field} differs from baseline."
                    )
                else:
                    warnings.append(
                        f"Run {variant.run_id}: local runtime differs; "
                        "preparation timings may be confounded."
                    )
            differences.append(
                ConfigDifference(
                    run_id=variant.run_id,
                    field=field,
                    baseline_value=old,
                    compared_value=new,
                    category=category,
                )
            )
        resize_changed = bool(changed & {"effective.processed_width", "effective.processed_height"})
        sampling_changed = bool(
            changed & {"requested.sampling", "requested.frames", "effective.selected_frame_count"}
        )
        if resize_changed and sampling_changed:
            warnings.append(
                f"Run {variant.run_id}: frame selection and processed dimensions both changed; "
                "the token delta reflects coupled sampling and resize effects."
            )
        elif resize_changed:
            warnings.append(f"Run {variant.run_id}: processed dimensions changed.")
    return ComparisonResult(
        schema_version="1.0",
        record_kind="comparison",
        tool_version=__version__,
        run_id=uuid4(),
        created_at=datetime.now(UTC),
        results=validated,
        baseline_run_id=baseline.run_id,
        comparable=not incompatibilities,
        incompatibilities=incompatibilities,
        differences=differences,
        warnings=warnings,
    )


def render_report(
    result: InspectionResult | ComparisonResult, *, include_media: bool = False
) -> str:
    """Render a bounded, self-contained HTML document from validated result data.

    Raw prompts and filenames are always omitted. ``include_media`` opts into
    rendering already-stored bounded raster thumbnails, never loading source files.
    """
    if len(result.model_dump_json().encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Stored result exceeds the 32 MiB report input limit.")
    comparison: dict[str, object] | None = None
    if isinstance(result, ComparisonResult):
        result = ComparisonResult.model_validate(result.model_dump(mode="json"))
        results = result.results
        # Recompute compatibility from the actual embedded records; do not trust
        # externally edited compatibility flags or a stale configuration diff.
        checked = compare_results(results)
        if result.baseline_run_id != results[0].run_id:
            raise ValueError("Comparison baseline must identify the first embedded run.")
        comparable = result.comparable and checked.comparable
        incompatibilities = list(
            dict.fromkeys([*checked.incompatibilities, *result.incompatibilities])
        )
        if not comparable and not incompatibilities:
            incompatibilities.append("The stored comparison was marked incompatible.")
        differences = list(checked.differences)
        known_differences = {(item.run_id, item.field) for item in differences}
        differences.extend(
            item
            for item in result.differences
            if (item.run_id, item.field) not in known_differences
        )
        names = tuple(
            item.manifest.display_name
            for item in results
            if item.manifest.display_name != item.manifest.kind
        )
        base_value = results[0].token_accounting.visual_placeholder_positions.value
        deltas: list[str] = []
        for item in results:
            value = item.token_accounting.visual_placeholder_positions.value
            if not comparable or base_value is None or value is None:
                deltas.append("Unavailable")
            else:
                delta = value - base_value
                deltas.append(("+" if delta > 0 else "") + _number(delta))
        comparison = {
            "comparable": comparable,
            "incompatibilities": [_clean_text(item, names) for item in incompatibilities],
            "warnings": [
                _clean_text(item, names)
                for item in dict.fromkeys([*checked.warnings, *result.warnings])
            ],
            "deltas": deltas,
            "differences": [
                {
                    "run_id": str(item.run_id)[:8],
                    "field": _clean_text(item.field, names),
                    "baseline_value": (
                        "[omitted]"
                        if _PRIVATE_KEY.search(item.field.replace(".", "_"))
                        else _pretty(item.baseline_value, names)
                    ),
                    "compared_value": (
                        "[omitted]"
                        if _PRIVATE_KEY.search(item.field.replace(".", "_"))
                        else _pretty(item.compared_value, names)
                    ),
                    "category": item.category,
                }
                for item in differences
            ],
        }
        title = "How input choices change the prompt"
        subtitle = (
            f"{len(results)} recorded inspections, one explicit baseline, "
            "and every effective change visible."
        )
    else:
        result = InspectionResult.model_validate(result.model_dump(mode="json"))
        results = [result]
        title = f"Your {result.manifest.kind}, through the processor"
        subtitle = (
            f"{result.processor.model_id} · See the selected input, transformed dimensions, "
            "and recorded token accounting before any model generation."
        )
    environment = Environment(
        autoescape=True, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True
    )
    template = environment.from_string(
        files("modalmeter").joinpath("templates/report.html").read_text(encoding="utf-8")
    )
    html = template.render(
        title=title,
        subtitle=_clean_text(
            subtitle,
            tuple(
                item.manifest.display_name
                for item in results
                if item.manifest.display_name != item.manifest.kind
            ),
        ),
        tool_version=_clean_text(result.tool_version),
        include_media=include_media,
        comparison=comparison,
        parity_summary=(
            "Serving parity unverified"
            if all(
                item.compatibility.server_parity == "server_parity_unverified" for item in results
            )
            else "See recorded serving parity evidence"
        ),
        runs=[_inspection_view(item, include_media) for item in results],
    )
    if len(html.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Rendered HTML exceeds the 32 MiB report size limit.")
    return html
