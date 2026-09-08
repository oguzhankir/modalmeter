"""Install each built artifact into a separate clean base environment and exercise it."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path) -> None:
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True, timeout=300)


def main() -> None:
    artifacts = sorted((ROOT / "dist").glob("*.whl")) + sorted((ROOT / "dist").glob("*.tar.gz"))
    if len(artifacts) != 2 or sum(p.suffix == ".whl" for p in artifacts) != 1:
        raise SystemExit(
            "Build exactly one wheel and one sdist in dist/ before running this check."
        )
    with tempfile.TemporaryDirectory(prefix="modalmeter-package-") as temporary:
        work = Path(temporary)
        constraints = work / "constraints.txt"
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
            run(
                [
                    str(python),
                    "-c",
                    """
import importlib.metadata as metadata
import importlib.util
from importlib.resources import files
import modalmeter
from modalmeter.schemas import EvidenceDocument
for name in ('torch', 'torchvision', 'transformers', 'PIL', 'av', 'vllm'):
    assert importlib.util.find_spec(name) is None, name
assert files('modalmeter').joinpath('py.typed').is_file()
assert metadata.version('modalmeter') == modalmeter.__version__
assert 'site-packages' in str(files('modalmeter'))
doc = EvidenceDocument.model_validate_json(
    '{"schema_version":"1.0","record_kind":"evidence","measurements":{}}'
)
assert doc.schema_version == '1.0'
print('PASS: installed package, version, py.typed, stored JSON; heavy dependencies absent')
""",
                ],
                work,
            )
            run(["uv", "pip", "check", "--python", str(python)], work)
            print(f"PASS: {artifact.name}", flush=True)


if __name__ == "__main__":
    main()
