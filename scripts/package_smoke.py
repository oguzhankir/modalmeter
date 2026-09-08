"""Install each built artifact into a separate clean base environment and exercise it."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# This checker runs under each installed distribution's isolated interpreter,
# from a temporary directory. It cannot import the source checkout or user site.
BASE_CHECK_SCRIPT = r"""
import importlib.abc
import importlib.metadata as metadata
import importlib.util
import json
import sys
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

HEAVY = {'torch', 'torchvision', 'transformers', 'PIL', 'av', 'vllm', 'numpy'}
for name in HEAVY:
    assert importlib.util.find_spec(name) is None, name

class NoHeavyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in HEAVY:
            raise AssertionError('Base rendering attempted a heavy import: ' + fullname)

def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'urllib.Request'}:
        raise AssertionError('Base rendering attempted network access: ' + event)

sys.meta_path.insert(0, NoHeavyImports())
sys.addaudithook(no_network)

import modalmeter
assert metadata.version('modalmeter') == modalmeter.__version__
package = files('modalmeter')
assert Path(str(package)).resolve().is_relative_to(Path(sys.prefix).resolve())
assert package.joinpath('py.typed').is_file()
assert package.joinpath('templates/report.html').is_file()
manifest = json.loads(package.joinpath('data/processor-artifacts.json').read_text())
assert manifest['weight_files_downloaded'] == 0
assert len(manifest['artifacts']) == 8
assert manifest['revision'] == '89644892e4d85e24eaac8bacfd4f463576704203'

if sys.argv[1] == 'cli':
    # Load the installed console-script entry point, under the same import and
    # network guards as the API check. The actual executable is checked too.
    sys.argv = ['modalmeter', *sys.argv[2:]]
    entry = next(
        item for item in metadata.distribution('modalmeter').entry_points
        if item.group == 'console_scripts' and item.name == 'modalmeter'
    )
    entry.load()()
else:
    from modalmeter.schemas import ComparisonResult, EvidenceDocument, InspectionResult
    from modalmeter.report import render_report
    from modalmeter.storage import (
        compare_runs, load_result, write_comparison_run, write_inspection_run,
    )

    fixture, output = Path(sys.argv[2]), Path(sys.argv[3])
    evidence = EvidenceDocument.model_validate_json(
        '{"schema_version":"1.0","record_kind":"evidence","measurements":{}}'
    )
    assert evidence.schema_version == '1.0'
    image = InspectionResult.model_validate_json(fixture.read_text())
    assert image.manifest.kind == 'image'
    assert image.token_accounting.visual_placeholder_positions.value == 77
    assert image.unavailable_metrics['gpu_memory_bytes'].value is None
    write_inspection_run(image, output / 'image')

    # The first record is a byte-for-byte captured real synthetic-media run.
    # The second is explicitly a COPY for serialization/comparison smoke only;
    # it is not another inspection run or a new measurement.
    note = (
        'Package smoke fixture copy: two copies of one recorded image inspection; '
        'serialization/rendering coverage only, not an independent run or benchmark.'
    )
    copied_data = image.model_dump(mode='json')
    copied_data['run_id'] = str(uuid4())
    copied_data['warnings'] = [*copied_data['warnings'], note]
    copied = InspectionResult.model_validate(copied_data)
    write_inspection_run(copied, output / 'copy')
    comparison = compare_runs([output / 'image', output / 'copy'])
    assert comparison.comparable
    assert len(comparison.results) == 2
    assert note in comparison.results[1].warnings
    write_comparison_run(comparison, output / 'comparison')

    loaded_image = load_result(output / 'image')
    loaded_comparison = load_result(output / 'comparison')
    assert isinstance(loaded_image, InspectionResult)
    assert isinstance(loaded_comparison, ComparisonResult)
    assert loaded_image.token_accounting == image.token_accounting
    for item in (loaded_image, loaded_comparison):
        html = render_report(item)
        assert '<html' in html and '</html>' in html
        assert 'Unavailable' in html
        assert 'server_parity_unverified' in html
        assert '{%' not in html and '{{' not in html
    assert not HEAVY.intersection(sys.modules)
    print(
        'PASS: isolated installed package, version, py.typed, template, artifact '
        'allowlist, real stored image and labeled comparison-copy JSON/HTML; '
        'heavy imports and network blocked'
    )
"""


def run(args: list[str], cwd: Path) -> None:
    print("$ " + " ".join(args), flush=True)
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment.update(PYTHONNOUSERSITE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    subprocess.run(args, cwd=cwd, env=environment, check=True, timeout=300)


def main() -> None:
    artifacts = sorted((ROOT / "dist").glob("*.whl")) + sorted((ROOT / "dist").glob("*.tar.gz"))
    if len(artifacts) != 2 or sum(p.suffix == ".whl" for p in artifacts) != 1:
        raise SystemExit(
            "Build exactly one wheel and one sdist in dist/ before running this check."
        )
    with tempfile.TemporaryDirectory(prefix="modalmeter-package-") as temporary:
        work = Path(temporary)
        constraints = work / "constraints.txt"
        checker = work / "check_installed_base.py"
        checker.write_text(BASE_CHECK_SCRIPT, encoding="utf-8")
        fixture = work / "inspection-v1.json"
        shutil.copyfile(ROOT / "tests" / "fixtures" / "inspection-v1.json", fixture)
        run(
            [
                "uv",
                "export",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--no-hashes",
                "--output-file",
                str(constraints),
                "--quiet",
            ],
            ROOT,
        )
        for index, artifact in enumerate(artifacts):
            env = work / f"env-{index}"
            run(["uv", "venv", "--python", sys.executable, str(env)], work)
            binaries = env / ("Scripts" if os.name == "nt" else "bin")
            python = binaries / "python"
            run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    "--constraint",
                    str(constraints),
                    str(artifact),
                ],
                work,
            )
            run([str(binaries / "modalmeter"), "--help"], work)
            run([str(binaries / "modalmeter"), "--version"], work)
            output = work / f"outputs-{index}"
            run(
                [
                    str(python),
                    "-I",
                    str(checker),
                    "api",
                    str(fixture),
                    str(output),
                ],
                work,
            )
            for kind in ("image", "comparison"):
                cli_output = output / f"{kind}-cli.html"
                run(
                    [
                        str(python),
                        "-I",
                        str(checker),
                        "cli",
                        "report",
                        str(output / kind),
                        "--output",
                        str(cli_output),
                    ],
                    work,
                )
                assert cli_output.read_bytes() == (output / kind / "report.html").read_bytes()
            run(["uv", "pip", "check", "--python", str(python)], work)
            print(f"PASS: {artifact.name}", flush=True)


if __name__ == "__main__":
    main()
