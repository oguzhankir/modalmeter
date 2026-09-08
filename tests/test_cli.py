import json
import subprocess
import sys
from pathlib import Path

import pytest
from click import unstyle
from test_report import inspection, variant
from typer.testing import CliRunner

from modalmeter import __version__
from modalmeter.cli import app
from modalmeter.errors import InspectionError, MissingExtra
from modalmeter.schemas import InspectionConfig, InspectionResult
from modalmeter.storage import load_result, write_inspection_run


@pytest.mark.parametrize("args", [[], ["--help"]])
@pytest.mark.parametrize("color", [False, True], ids=["plain", "color"])
def test_help_is_honest_and_successful(args: list[str], color: bool) -> None:
    result = CliRunner().invoke(
        app,
        args,
        env={
            "FORCE_COLOR": "1" if color else None,
            "NO_COLOR": None if color else "1",
            "TERM": "xterm-256color" if color else "dumb",
        },
        color=color,
    )
    assert result.exit_code == 0, result.output
    if color:
        assert "\x1b[" in result.output
    output = unstyle(result.output)
    assert "--version" in output
    for command in ("prepare", "inspect", "report", "compare"):
        assert command in output
    assert "not implemented" not in output


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"modalmeter {__version__}"


@pytest.mark.parametrize("command", ["benchmark", "sweep"])
def test_future_commands_are_not_advertised_as_working(command: str) -> None:
    result = CliRunner().invoke(app, [command])
    assert result.exit_code == 2


def test_help_does_not_import_heavy_dependencies() -> None:
    code = """
import sys
class BlockHeavy:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'torchvision', 'transformers', 'av', 'PIL', 'vllm'}:
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, BlockHeavy())
from modalmeter.cli import app
sys.argv = ['modalmeter', '--help']
app()
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("command", ["prepare", "inspect", "report", "compare"])
def test_implemented_command_help(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "options",
    [
        ["--sampling", "uniform"],
        ["--frames", "3"],
        ["--sampling", "unknown"],
        ["--sampling", "uniform", "--frames", "129"],
        ["--max-pixels", "0"],
    ],
)
def test_invalid_inspection_controls_fail_before_processor_import(
    tmp_path: Path, options: list[str]
) -> None:
    target = tmp_path / "run"
    result = CliRunner().invoke(app, ["inspect", "media.png", "--output", str(target), *options])
    assert result.exit_code == 2, result.output
    assert not target.exists()


def test_unsupported_model_is_actionable_without_loading_processor(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["inspect", "media.png", "--output", str(tmp_path / "run"), "--model", "unsupported"]
    )
    assert result.exit_code == 2, result.output
    assert "Supported processor:" in result.output
    assert "Traceback" not in result.output


def test_prepare_offline_missing_cache_is_actionable(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["prepare", "--offline", "--cache-dir", str(tmp_path / "cache")]
    )
    assert result.exit_code == 2, result.output
    assert "Processor artifacts are not cached" in result.output


def test_inspect_cli_uses_shared_api_and_exports_sanitized_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import modalmeter.inspect as inspection_module

    calls: list[InspectionConfig] = []

    def inspect_fixture(config: InspectionConfig) -> InspectionResult:
        calls.append(config)
        return inspection("image")

    monkeypatch.setattr(inspection_module, "inspect_media", inspect_fixture)
    prompt = tmp_path / "private-prompt.txt"
    prompt.write_text("PRIVATE PROMPT CONTENT")
    target = tmp_path / "run"
    result = CliRunner().invoke(
        app,
        [
            "inspect",
            "private-input.png",
            "--output",
            str(target),
            "--prompt-file",
            str(prompt),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0].prompt == "PRIVATE PROMPT CONTENT"
    assert calls[0].path == Path("private-input.png")
    data = json.loads(result.output)
    assert data["record_kind"] == "inspection"
    assert data["manifest"]["display_name"] == "image"
    assert "PRIVATE PROMPT CONTENT" not in result.output
    assert "private-input.png" not in result.output
    assert str(load_result(target).run_id) == data["run_id"]


@pytest.mark.parametrize(
    "failure,code",
    [
        (MissingExtra("Install modalmeter[inspect]."), 2),
        (InspectionError("Processor failed."), 1),
        (KeyboardInterrupt(), 130),
        (RuntimeError("SECRET_INPUT /Users/private/file"), 1),
    ],
)
def test_inspection_errors_have_stable_exit_codes_and_no_private_tracebacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException, code: int
) -> None:
    import modalmeter.inspect as inspection_module

    def fail(config: InspectionConfig) -> InspectionResult:
        raise failure

    monkeypatch.setattr(inspection_module, "inspect_media", fail)
    target = tmp_path / "run"
    result = CliRunner().invoke(app, ["inspect", "private.png", "--output", str(target)])
    assert result.exit_code == code, result.output
    assert "SECRET_INPUT" not in result.output
    assert "/Users/private" not in result.output
    assert "Traceback" not in result.output
    assert not target.exists()


def test_output_collision_is_checked_before_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import modalmeter.inspect as inspection_module

    def fail(config: InspectionConfig) -> InspectionResult:
        raise AssertionError("inspection should not run")

    monkeypatch.setattr(inspection_module, "inspect_media", fail)
    target = tmp_path / "run"
    target.mkdir()
    result = CliRunner().invoke(app, ["inspect", "private.png", "--output", str(target)])
    assert result.exit_code == 2, result.output
    assert "already exists" in result.output


def test_prompt_file_is_utf8_and_bounded(tmp_path: Path) -> None:
    prompt = tmp_path / "private.txt"
    prompt.write_bytes(b"\xff")
    result = CliRunner().invoke(
        app,
        ["inspect", "image.png", "--output", str(tmp_path / "run"), "--prompt-file", str(prompt)],
    )
    assert result.exit_code == 2
    assert "UTF-8" in result.output
    prompt.write_text("x" * 100)
    result = CliRunner().invoke(
        app,
        [
            "inspect",
            "image.png",
            "--output",
            str(tmp_path / "run"),
            "--prompt-file",
            str(prompt),
            "--max-prompt-bytes",
            "10",
        ],
    )
    assert result.exit_code == 2
    assert "byte limit" in result.output


def test_report_and_compare_cli_work_from_stored_data(tmp_path: Path) -> None:
    baseline = inspection()
    one, two = tmp_path / "one", tmp_path / "two"
    write_inspection_run(baseline, one)
    write_inspection_run(variant(baseline), two)
    html = tmp_path / "report.html"
    report_result = CliRunner().invoke(app, ["report", str(one), "--output", str(html)])
    assert report_result.exit_code == 0, report_result.output
    assert "ModalMeter" in html.read_text()
    output = tmp_path / "comparison"
    compared = CliRunner().invoke(app, ["compare", str(one), str(two), "--output", str(output)])
    assert compared.exit_code == 0, compared.output
    assert "baseline compatible" in compared.output
    assert (output / "comparison.json").exists()


def test_stored_report_command_blocks_all_heavy_imports_and_network(tmp_path: Path) -> None:
    source = tmp_path / "inspection.json"
    source.write_text(inspection().model_dump_json())
    target = tmp_path / "report.html"
    code = """
import sys
class BlockHeavy:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'torchvision', 'transformers', 'av', 'PIL', 'vllm'}:
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, BlockHeavy())
import socket
def blocked(*args, **kwargs):
    raise AssertionError('Network access is forbidden')
socket.create_connection = blocked
from modalmeter.cli import app
sys.argv = ['modalmeter', 'report', sys.argv[1], '--output', sys.argv[2]]
app()
"""
    process = subprocess.run(
        [sys.executable, "-c", code, str(source), str(target)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert target.exists()
