# M0 evidence

All files here describe local M0 foundation/feasibility work on 2026-09-08.
No model inference, private media, endpoint benchmark, GPU measurement, or
processor/server parity validation occurred. The generated probe frames and
contract JSON are synthetic. See the [support matrix](../../support-matrix.md).

## Evidence index

- [Environment](environment.json): baseline commit, branch, OS/interpreters,
  pinned tool version, environment changes, exact contract hash and preserved license.
- [Python 3.12 checks](checks-py312.txt) and [Python 3.11 checks](checks-py311.txt):
  actual format/lint/type/test and CLI output, each with its exit code.
- [Build](build.txt): wheel and sdist output; the
  [sandboxed metadata refresh failure](build-network-error.txt) was resolved with
  authorized dependency access before the final build.
- [Python 3.12 package smoke](package-smoke-py312.txt) and
  [Python 3.11 package smoke](package-smoke-py311.txt): separate clean installs of
  each distribution, help/version, JSON load, type marker and absent heavy modules.
- [Archive contents](package-contents.json): actual file sizes, SHA-256 and members;
  license metadata and absence of private media/weights/caches reviewed locally.
- [Processor artifacts](processor-artifacts.json): exact eight-file allowlist,
  immutable URLs, byte lengths and SHA-256. Total 11,499,725 bytes, zero weight files.
- [Artifact verification](artifact-verification.txt): local size/hash checks.
- [Source refs](source-refs.json), [installed source checks](installed-source-check.json):
  verified GitHub SHAs and four processor source files matching the installed wheel.
- [Probe output](spike-result.json): observed native processor loading, synthetic
  video metadata/grid/prompt behavior and PyAV FFV1 encode/decode. Not accounting
  correctness or parity evidence. A cached rerun produced identical JSON.
- [Initial processor error](spike-initial-error.txt): the real metadata/tensor
  failure; the resolution and limitations are in [ADR 0002](../../decisions/0002-processor-path.md).
- [Initial Python selection error](checks-py311-initial-error.txt),
  [architecture download error](checks-py311-architecture-error.txt), and
  [mixed-wheel error](checks-py311-mixed-wheels-error.txt): failed attempts retained
  as evidence. Final checks use an isolated ARM64 Python/uv environment.

The distributions remain in ignored `dist/` locally; they are not committed or
published. Their recorded hashes identify what was tested. Hosted CI, image
reference tests, complete video cases, report visual QA, and live GPU checks
are not run. Default pytest does not download anything. Typer emits two upstream
Click deprecation warnings; they are visible in the logs and are not suppressed.

## Reproduce the feasibility probe

Use uv 0.11.7 and native Python 3.12. The local-development document explains the
isolated uv tool needed after this machine's global environment changed.

```bash
UV_PROJECT_ENVIRONMENT=.venv-spike uv sync --locked --extra inspect --python /opt/homebrew/bin/python3.12
python3 docs/evidence/m0/prepare_spike.py --download --output /private/tmp/modalmeter-m0-processor
.venv-spike/bin/python docs/evidence/m0/spike.py --processor-dir /private/tmp/modalmeter-m0-processor
```

The preparation helper is explicitly M0-only. It downloads only recorded files,
checks byte length/hash and reuses exact existing files; it does not resolve an
arbitrary model or implement the M1 artifact resolver. The probe itself sets
Hugging Face/Transformers offline modes, checks those hashes and loads with
`local_files_only=True`, `trust_remote_code=False`. Repeat the last command with
no network to reproduce the observation. No external ffmpeg binary is used.

The first failed experiment can be reproduced by adding `return_metadata=True`
to the combined processor call in a disposable copy of the probe. Do not mutate
the working probe or production source to preserve the failed behavior. The
successful probe separately observes video metadata before tensor assembly;
production single-pass processing remains an M1/M2 design and test obligation.

Terminal transcripts preserve original whitespace. The copied implementation
contract also preserves Markdown hard-break spaces. A full staged Git whitespace
check flags these byte-preserved artifacts; source/config/documentation outside
those raw artifacts passes the scoped whitespace check. No test output was altered
to conceal a failure.
