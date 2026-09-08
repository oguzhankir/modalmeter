import subprocess
import sys

import pytest
from typer.testing import CliRunner

from modalmeter import __version__
from modalmeter.cli import app


@pytest.mark.parametrize("args", [[], ["--help"]])
def test_help_is_honest_and_successful(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "--version" in result.output
    assert "not implemented" in result.output


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"modalmeter {__version__}"


@pytest.mark.parametrize("command", ["inspect", "benchmark", "sweep", "report", "compare"])
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
