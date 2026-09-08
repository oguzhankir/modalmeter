"""Artifact transactions use synthetic records and temporary directories."""

import json
import os
from pathlib import Path

import pytest
from test_report import PIXEL_PNG, inspection, variant

from modalmeter import storage
from modalmeter.errors import InspectionError, InvalidInput
from modalmeter.report import compare_results, render_report
from modalmeter.schemas import ComparisonResult, InspectionResult
from modalmeter.storage import (
    compare_runs,
    load_result,
    sanitized_result,
    write_comparison_run,
    write_html_report,
    write_inspection_run,
)


def test_run_files_share_the_same_sanitized_result(tmp_path: Path) -> None:
    result = inspection()
    target = tmp_path / "run"
    write_inspection_run(result, target)
    assert {item.name for item in target.iterdir()} == {
        "inspection.json",
        "manifest.json",
        "report.html",
    }
    loaded = load_result(target)
    assert isinstance(loaded, InspectionResult)
    assert loaded == sanitized_result(result)
    assert loaded.manifest.display_name == "video"
    assert loaded.thumbnails == []
    assert json.loads((target / "manifest.json").read_text()) == loaded.manifest.model_dump(
        mode="json"
    )
    assert (target / "report.html").read_text() == render_report(loaded)
    assert result.manifest.display_name not in (target / "inspection.json").read_text()
    assert load_result(target / "inspection.json") == loaded


def test_opt_in_media_is_preserved_without_reprocessing(tmp_path: Path) -> None:
    target = tmp_path / "run"
    write_inspection_run(inspection(), target, include_media=True)
    loaded = load_result(target)
    assert isinstance(loaded, InspectionResult)
    assert loaded.thumbnails == [PIXEL_PNG] * 3
    assert loaded.manifest.privacy_mode == "media_included"
    assert PIXEL_PNG in (target / "report.html").read_text()


def test_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "run"
    result = inspection()
    write_inspection_run(result, target)
    original = (target / "inspection.json").read_bytes()
    with pytest.raises(InvalidInput, match="already exists"):
        write_inspection_run(variant(result), target)
    assert (target / "inspection.json").read_bytes() == original
    changed = variant(result)
    write_inspection_run(changed, target, overwrite=True)
    assert load_result(target).run_id == changed.run_id


def test_overwrite_refuses_unrelated_files(tmp_path: Path) -> None:
    target = tmp_path / "run"
    write_inspection_run(inspection(), target)
    unrelated = target / "owner-notes.txt"
    unrelated.write_text("preserve me")
    with pytest.raises(InvalidInput, match="unrelated"):
        write_inspection_run(inspection(), target, overwrite=True)
    assert unrelated.read_text() == "preserve me"


def test_overwrite_refuses_empty_unowned_directory(tmp_path: Path) -> None:
    target = tmp_path / "not-a-run"
    target.mkdir()
    with pytest.raises(InvalidInput, match="exactly one result"):
        write_inspection_run(inspection(), target, overwrite=True)
    assert list(target.iterdir()) == []


def test_staging_write_failure_leaves_previous_run_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "run"
    write_inspection_run(inspection(), target)
    before = {item.name: item.read_bytes() for item in target.iterdir()}
    original = storage._write_bytes

    def failing_write(path: Path, data: bytes) -> None:
        if path.name == "report.html":
            raise OSError("synthetic write failure")
        original(path, data)

    monkeypatch.setattr(storage, "_write_bytes", failing_write)
    with pytest.raises(InspectionError, match="previous artifacts were preserved"):
        write_inspection_run(variant(inspection()), target, overwrite=True)
    assert {item.name: item.read_bytes() for item in target.iterdir()} == before
    assert {item.name for item in tmp_path.iterdir()} == {"run"}


@pytest.mark.parametrize("interrupt", [False, True])
def test_publication_failure_restores_previous_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt: bool
) -> None:
    target = tmp_path / "run"
    original_result = inspection()
    write_inspection_run(original_result, target)
    original_replace = os.replace

    def fail_publish(source: Path, destination: Path) -> None:
        if source.name.startswith(".modalmeter-staging-"):
            if interrupt:
                raise KeyboardInterrupt()
            raise OSError("synthetic rename failure")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_publish)
    error = KeyboardInterrupt if interrupt else InspectionError
    with pytest.raises(error):
        write_inspection_run(variant(original_result), target, overwrite=True)
    assert load_result(target).run_id == original_result.run_id
    assert {item.name for item in tmp_path.iterdir()} == {"run"}


def test_failed_new_run_does_not_publish_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_publish(source: Path, destination: Path) -> None:
        raise OSError("synthetic rename failure")

    monkeypatch.setattr(os, "replace", fail_publish)
    with pytest.raises(InspectionError):
        write_inspection_run(inspection(), tmp_path / "run")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("identity", ["schema_version", "record_kind"])
@pytest.mark.parametrize("nested", [False, True])
def test_missing_identity_is_never_silently_defaulted(
    tmp_path: Path, identity: str, nested: bool
) -> None:
    data = inspection().model_dump(mode="json")
    record = data["manifest"] if nested else data
    record.pop(identity)
    source = tmp_path / "incomplete.json"
    source.write_text(json.dumps(data))
    with pytest.raises(InvalidInput, match="missing"):
        load_result(source)


@pytest.mark.parametrize("version", ["1.1", "2.0", "99.0"])
def test_unsupported_schema_version_is_rejected(tmp_path: Path, version: str) -> None:
    data = inspection().model_dump(mode="json")
    data["schema_version"] = version
    source = tmp_path / "unsupported.json"
    source.write_text(json.dumps(data))
    with pytest.raises(InvalidInput, match="schema_version"):
        load_result(source)


@pytest.mark.parametrize(
    "payload", ['{"a":1,"a":2}', '{"value":NaN}', '{"value":Infinity}', "[]", "{"]
)
def test_malformed_or_ambiguous_json_is_rejected(tmp_path: Path, payload: str) -> None:
    source = tmp_path / "bad.json"
    source.write_text(payload)
    with pytest.raises(InvalidInput):
        load_result(source)


def test_loader_bounds_input_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "large.json"
    source.write_text(inspection().model_dump_json())
    monkeypatch.setattr(storage, "MAX_RESULT_BYTES", 10)
    with pytest.raises(InvalidInput, match="input limit"):
        load_result(source)


def test_symlink_inputs_and_outputs_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(inspection().model_dump_json())
    linked = tmp_path / "link.json"
    linked.symlink_to(source)
    with pytest.raises(InvalidInput, match="symbolic"):
        load_result(linked)
    output = tmp_path / "output"
    output.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(InvalidInput, match="symbolic"):
        write_inspection_run(inspection(), output, overwrite=True)


def test_comparison_can_load_and_render_without_processor(tmp_path: Path) -> None:
    original = inspection()
    one, two = tmp_path / "one", tmp_path / "two"
    write_inspection_run(original, one)
    write_inspection_run(variant(original), two)
    compared = compare_runs([one, two / "inspection.json"])
    output = tmp_path / "comparison"
    write_comparison_run(compared, output)
    loaded = load_result(output)
    assert isinstance(loaded, ComparisonResult)
    assert loaded.baseline_run_id == original.run_id
    assert loaded.comparable
    assert {item.name for item in output.iterdir()} == {"comparison.json", "report.html"}
    with pytest.raises(InvalidInput, match="inspection records"):
        compare_runs([one, output])


def test_nested_comparison_identity_is_required(tmp_path: Path) -> None:
    original = inspection()
    data = compare_results([original, variant(original)]).model_dump(mode="json")
    data["results"][1]["manifest"].pop("record_kind")
    source = tmp_path / "comparison.json"
    source.write_text(json.dumps(data))
    with pytest.raises(InvalidInput, match="record_kind"):
        load_result(source)


def test_sanitization_cannot_upgrade_an_incompatible_comparison(tmp_path: Path) -> None:
    baseline = inspection().model_copy(update={"requested_settings": {"api_key": "PRIVATE_ONE"}})
    changed = variant(baseline, requested_settings={"api_key": "PRIVATE_TWO"})
    result = compare_results([baseline, changed])
    assert not result.comparable
    target = tmp_path / "comparison"
    write_comparison_run(result, target)
    loaded = load_result(target)
    assert isinstance(loaded, ComparisonResult)
    assert not loaded.comparable
    html = (target / "report.html").read_text()
    assert "Incompatible baseline" in html
    assert "requested.api_key" in html
    assert "PRIVATE_ONE" not in html
    assert "PRIVATE_TWO" not in html


def test_single_html_atomic_overwrite_policy(tmp_path: Path) -> None:
    target = tmp_path / "report.html"
    write_html_report(inspection(), target)
    before = target.read_bytes()
    with pytest.raises(InvalidInput, match="already exists"):
        write_html_report(inspection("image"), target)
    assert target.read_bytes() == before
    write_html_report(inspection("image"), target, overwrite=True)
    assert "Your image" in target.read_text()
    assert not list(tmp_path.glob(".modalmeter-report-*"))


def test_single_html_write_failure_preserves_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "report.html"
    target.write_text("preserve prior content")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("synthetic failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(InspectionError):
        write_html_report(inspection(), target, overwrite=True)
    assert target.read_text() == "preserve prior content"
    assert {item.name for item in tmp_path.iterdir()} == {"report.html"}
