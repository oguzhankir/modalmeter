"""Offline report checks use synthetic typed records, never benchmark evidence."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Literal
from uuid import UUID, uuid4

import pytest

from modalmeter import report
from modalmeter.report import compare_results, render_report
from modalmeter.schemas import (
    MODEL_ID,
    MODEL_REVISION,
    Compatibility,
    EvidenceKind,
    InspectionResult,
    Measurement,
    MediaManifest,
    ProcessedFrame,
    ProcessorProvenance,
    SourceFrame,
    TokenAccounting,
)

PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def measurement(value: int | float | None, *, derived: bool = False) -> Measurement:
    return Measurement(
        value=value,
        unit="positions",
        evidence_kind=(
            EvidenceKind.UNAVAILABLE
            if value is None
            else EvidenceKind.DERIVED
            if derived
            else EvidenceKind.OBSERVED
        ),
        source="Synthetic unit-test fixture",
        scope="single synthetic prompt",
        method="Synthetic observations for HTML tests; no inference was performed.",
        unavailable_reason="Not captured by this inspection." if value is None else None,
    )


def inspection(kind: Literal["image", "video"] = "video") -> InspectionResult:
    count = 3 if kind == "video" else 1
    selected = [
        SourceFrame(
            ordinal=index,
            pts=index * 500 if kind == "video" else None,
            time_base_numerator=1 if kind == "video" else None,
            time_base_denominator=1000 if kind == "video" else None,
            timestamp_seconds=index / 2 if kind == "video" else None,
            timestamp_unavailable_reason=None
            if kind == "video"
            else "Still image has no timeline.",
            processor_timestamp_seconds=index / 2 if kind == "video" else None,
        )
        for index in range(count)
    ]
    processed = [
        ProcessedFrame(
            position=index,
            selected_position=min(index, count - 1),
            source_ordinal=min(index, count - 1),
            duplicated=index >= count,
            duplication_reason="temporal padding" if index >= count else None,
        )
        for index in range(count + 1)
    ]
    visual = 8 if kind == "video" else 4
    return InspectionResult(
        schema_version="1.0",
        record_kind="inspection",
        tool_version="0.0.0.dev0",
        run_id=UUID("11111111-1111-4111-8111-111111111111"),
        created_at=datetime(2026, 9, 8, tzinfo=UTC),
        manifest=MediaManifest(
            kind=kind,
            sha256="a" * 64,
            display_name="private-recording.mp4" if kind == "video" else "private-image.png",
            source_bytes=1234,
            source_width=64,
            source_height=48,
            oriented_width=64,
            oriented_height=48,
            source_mode="RGB",
            source_frame_count=count,
            selected_frames=selected,
            requested_frames=count if kind == "video" else None,
            selected_frame_count=count,
            processed_frame_count=count + 1,
            processed_frames=processed,
            source_duration_seconds=1.5 if kind == "video" else None,
            source_duration_reason=None if kind == "video" else "Still image has no duration.",
            average_fps=2.0 if kind == "video" else None,
            fps_reason=None if kind == "video" else "Still image has no frame rate.",
            sampling_policy="uniform" if kind == "video" else "single-image",
            sampling_method="Nearest presentation timestamp, earlier index breaks ties.",
            timestamp_policy="Decoded PTS preserved separately from processor index / FPS.",
            decoder_versions={"av": "16.1.0"},
        ),
        processor=ProcessorProvenance(
            model_id=MODEL_ID,
            revision=MODEL_REVISION,
            adapter_version="qwen3-vl/1",
            dependency_versions={"transformers": "4.57.6", "torch": "2.9.1"},
            artifact_sha256={"config.json": "c" * 64},
            effective_settings={"patch_size": 16, "spatial_merge_size": 2},
            runtime={"platform": "synthetic-test-fixture", "python": "3.12"},
        ),
        token_accounting=TokenAccounting(
            encoder_grid_positions=measurement(visual * 4, derived=True),
            visual_placeholder_positions=measurement(visual),
            grid_derived_visual_positions=measurement(visual, derived=True),
            nonpadding_prompt_positions=measurement(visual + 12),
            nonvisual_prompt_positions=measurement(12, derived=True),
            vision_boundary_positions=measurement(4 if kind == "video" else 2),
            video_timestamp_positions=measurement(None),
            user_text_positions=measurement(None),
            server_prompt_usage=measurement(None),
            server_completion_usage=measurement(None),
            placeholder_token_id=151656,
            observed_placeholder_indices=list(range(4, 4 + visual)),
            grid_matches_placeholders=True,
        ),
        grid_thw=[2 if kind == "video" else 1, 4, 4],
        processed_width=64,
        processed_height=64,
        prompt_sha256="b" * 64,
        template_sha256="d" * 64,
        group_timestamp_labels=["0.2", "1.0"] if kind == "video" else [],
        thumbnails=[PIXEL_PNG] * count,
        compatibility=Compatibility(
            modality=kind,
            processor_verification="processor_verified",
            processor_evidence="Synthetic test record; not an actual processor acceptance run.",
        ),
        timings={},
        unavailable_metrics={},
        requested_settings={"sampling": "uniform", "frames": count},
    )


class TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def test_report_is_deterministic_and_self_contained() -> None:
    result = inspection()
    html = render_report(result)
    assert html == render_report(InspectionResult.model_validate_json(result.model_dump_json()))
    parsed = TagCollector()
    parsed.feed(html)
    assert not any(tag in {"script", "link", "iframe", "object", "embed"} for tag, _ in parsed.tags)
    assert not any("src" in attributes for _, attributes in parsed.tags)
    assert "Content-Security-Policy" in html
    assert "@media(max-width:760px)" in html
    assert "Vision encoder grid positions" in html
    assert "Complete non-padding processed prompt" in html
    assert "Source PTS: 0.5 s" in html
    assert "Exact: 500 × 1/1000 s" in html
    assert "temporal padding" in html
    assert "1 processed positions repeat" in html
    assert MODEL_REVISION in html


def test_sanitized_report_omits_names_media_paths_and_secrets() -> None:
    original = inspection()
    result = original.model_copy(
        update={
            "requested_settings": {
                "raw_prompt": "SECRET_PROMPT",
                "prompt": "SECRET_DIRECT_PROMPT",
                "messages": [{"role": "user", "content": "SECRET_MESSAGE"}],
                "processor_path": "/Users/owner/secret-processor",
                "api_key": "SECRET_API_KEY",
                "nested": {"endpoint": "https://user:pass@example.test/?key=SECRET_QUERY"},
            },
            "warnings": [
                "Cannot open /Users/owner/secret-file.mp4",
                "Remote https://example.test/private?key=SECRET_QUERY",
                "Authentication Bearer SECRET_BEARER",
                "Source private-recording.mp4 had a missing timestamp.",
            ],
        }
    )
    html = render_report(result)
    for private in (
        "private-recording.mp4",
        "data:image/",
        "SECRET_PROMPT",
        "SECRET_DIRECT_PROMPT",
        "SECRET_MESSAGE",
        "SECRET_API_KEY",
        "SECRET_QUERY",
        "SECRET_BEARER",
        "/Users/owner",
        "secret-file.mp4",
    ):
        assert private not in html
    assert "[omitted]" in html
    assert "[path omitted]" in html
    assert original.thumbnails == result.thumbnails
    assert result.requested_settings["raw_prompt"] == "SECRET_PROMPT"


def test_media_flag_includes_only_stored_raster_images() -> None:
    result = inspection()
    html = render_report(result, include_media=True)
    parsed = TagCollector()
    parsed.feed(html)
    images = [attributes for tag, attributes in parsed.tags if tag == "img"]
    assert len(images) == 3
    assert all(image["src"] == PIXEL_PNG for image in images)
    assert "object-fit:contain" in html
    assert result.manifest.display_name not in html
    assert "Embedded thumbnails were explicitly requested" in html


@pytest.mark.parametrize(
    "thumbnail",
    [
        "https://tracking.example/image.png",
        "data:image/svg+xml;base64,PHN2Zy8+",
        "data:text/html;base64,PHNjcmlwdD4=",
        "data:image/png;base64,bm90LWFuLWltYWdl",
        'data:image/png;base64,abcd" onerror="alert(1)',
    ],
)
def test_bad_thumbnail_is_omitted(thumbnail: str) -> None:
    result = inspection("image").model_copy(update={"thumbnails": [thumbnail]})
    html = render_report(result, include_media=True)
    assert "<img " not in html
    assert "unsupported thumbnail was omitted" in html


def test_image_report_does_not_invent_a_video_timeline() -> None:
    html = render_report(inspection("image"))
    assert "Input preview" in html
    assert "Selected-frame timeline" not in html
    assert "64 × 48 → 64 × 64" in html
    assert "Source PTS:" not in html
    assert "Serving latency" in html
    assert "Vision encoder execution time" in html
    assert "GPU memory" in html
    assert "Unavailable" in html
    assert "No model forward pass was executed." in html


def test_missing_timestamps_keep_explanation() -> None:
    result = inspection()
    frame = result.manifest.selected_frames[0].model_copy(
        update={
            "timestamp_seconds": None,
            "pts": None,
            "time_base_numerator": None,
            "time_base_denominator": None,
            "timestamp_unavailable_reason": "Decoder did not expose PTS.",
        }
    )
    manifest = result.manifest.model_copy(
        update={"selected_frames": [frame, *result.manifest.selected_frames[1:]]}
    )
    html = render_report(result.model_copy(update={"manifest": manifest}))
    assert "Source PTS: unavailable" in html
    assert "Decoder did not expose PTS." in html


def test_external_html_and_long_labels_are_escaped() -> None:
    result = inspection().model_copy(
        update={
            "warnings": ['<img src=x onerror="alert(1)">', "Long observation " + "x" * 2000],
        }
    )
    html = render_report(result)
    assert '<img src=x onerror="alert(1)">' not in html
    assert "&lt;img src=x onerror=&#34;alert(1)&#34;&gt;" in html
    assert "x" * 2000 in html
    assert "overflow-wrap:anywhere" in html


def test_real_zero_duration_stays_distinct_from_unavailable() -> None:
    observed_zero = Measurement(
        value=0,
        unit="ms",
        evidence_kind=EvidenceKind.MEASURED,
        source="Synthetic timer fixture",
        scope="local preparation",
        method="Synthetic clock with zero elapsed ticks.",
    )
    result = inspection().model_copy(update={"timings": {"preparation_ms": observed_zero}})
    html = render_report(result)
    assert "Synthetic clock with zero elapsed ticks." in html
    assert '<span class="metric-value">0</span><span class="unit">ms</span>' in html
    assert "No serving endpoint request was made." in html


def test_base_render_imports_no_heavy_dependencies() -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import modalmeter.report; "
            "assert not ({'torch', 'transformers', 'PIL', 'av', 'vllm'} & sys.modules.keys())",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr


def test_report_revalidates_modified_schema() -> None:
    invalid = inspection().model_copy(update={"schema_version": "99.0"})
    with pytest.raises(ValueError, match="1.0"):
        render_report(invalid)


def test_report_input_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report, "MAX_REPORT_BYTES", 100)
    with pytest.raises(ValueError, match="report input limit"):
        render_report(inspection())


def variant(result: InspectionResult, **updates: object) -> InspectionResult:
    return result.model_copy(update={"run_id": uuid4(), **updates})


def test_identical_inputs_have_explicit_baseline_and_zero_delta() -> None:
    baseline = inspection()
    compared = compare_results([baseline, variant(baseline)])
    assert compared.baseline_run_id == baseline.run_id
    assert compared.comparable
    assert compared.differences == []
    html = render_report(compared)
    assert "Compatible baseline" in html
    assert "No effective configuration differences found" in html
    assert "GPU memory" in html
    assert "speedup" not in html.lower()


@pytest.mark.parametrize("field", ["prompt_sha256", "template_sha256"])
def test_different_prompts_or_templates_prevent_controlled_comparison(field: str) -> None:
    baseline = inspection()
    compared = compare_results([baseline, variant(baseline, **{field: "e" * 64})])
    assert not compared.comparable
    assert any(field in item for item in compared.incompatibilities)
    html = render_report(compared)
    assert "Incompatible baseline" in html
    assert "Interpret these runs separately" in html


def test_model_and_source_changes_are_not_silently_paired() -> None:
    baseline = inspection()
    changed = variant(
        baseline,
        processor=baseline.processor.model_copy(update={"revision": "new-revision"}),
        manifest=baseline.manifest.model_copy(update={"sha256": "f" * 64}),
    )
    compared = compare_results([baseline, changed])
    assert not compared.comparable
    assert {item.field for item in compared.differences} == {
        "processor.revision",
        "manifest.sha256",
    }
    assert all(item.category == "confounding" for item in compared.differences)


def test_sampling_and_resize_coupling_is_visible() -> None:
    baseline = inspection()
    changed = variant(
        baseline,
        requested_settings={"sampling": "uniform", "frames": 8},
        processed_width=128,
        grid_thw=[2, 4, 8],
    )
    compared = compare_results([baseline, changed])
    assert compared.comparable
    assert any(
        item.field == "requested.frames" and item.category == "intentional"
        for item in compared.differences
    )
    assert any("coupled sampling and resize" in item for item in compared.warnings)
    assert "coupled sampling and resize" in render_report(compared)


def test_runtime_difference_warns_without_invalidating_input_facts() -> None:
    baseline = inspection()
    changed = variant(
        baseline,
        processor=baseline.processor.model_copy(update={"runtime": {"platform": "another-cpu"}}),
    )
    compared = compare_results([baseline, changed])
    assert compared.comparable
    assert any("preparation timings may be confounded" in item for item in compared.warnings)


def test_processor_mismatch_prevents_a_trusted_comparison() -> None:
    baseline = inspection()
    changed = variant(
        baseline,
        compatibility=baseline.compatibility.model_copy(
            update={"processor_verification": "processor_mismatch"}
        ),
    )
    compared = compare_results([baseline, changed])
    assert not compared.comparable
    assert any("processor correctness mismatch" in issue for issue in compared.incompatibilities)


def test_incomplete_processor_provenance_is_explicit() -> None:
    baseline = inspection()
    changed = variant(
        baseline,
        processor=baseline.processor.model_copy(update={"artifact_sha256": {}}),
    )
    compared = compare_results([baseline, changed])
    assert not compared.comparable
    assert any("provenance is incomplete" in issue for issue in compared.incompatibilities)


def test_comparison_hides_sensitive_values_in_configuration_diffs() -> None:
    baseline = inspection().model_copy(update={"requested_settings": {"api_key": "SECRET_ONE"}})
    changed = variant(baseline, requested_settings={"api_key": "SECRET_TWO"})
    html = render_report(compare_results([baseline, changed]))
    assert "SECRET_ONE" not in html
    assert "SECRET_TWO" not in html


def test_edited_comparison_flag_cannot_hide_incompatibility() -> None:
    baseline = inspection()
    changed = variant(baseline, prompt_sha256="f" * 64)
    compared = compare_results([baseline, changed]).model_copy(
        update={"comparable": True, "incompatibilities": [], "differences": []}
    )
    assert "Incompatible baseline" in render_report(compared)


def test_changed_baseline_identity_is_rejected() -> None:
    baseline = inspection()
    changed = variant(baseline)
    compared = compare_results([baseline, changed]).model_copy(
        update={"baseline_run_id": changed.run_id}
    )
    with pytest.raises(ValueError, match="baseline"):
        render_report(compared)


def test_same_run_twice_is_rejected() -> None:
    baseline = inspection()
    with pytest.raises(ValueError, match="distinct run IDs"):
        compare_results([baseline, baseline])


@pytest.mark.parametrize("count", [0, 1, 9])
def test_comparison_size_is_bounded(count: int) -> None:
    with pytest.raises(ValueError, match="two and eight"):
        compare_results([variant(inspection()) for _ in range(count)])
