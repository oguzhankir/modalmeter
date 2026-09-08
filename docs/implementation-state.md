# Implementation state

Current branch: `oguzhankir/cpu-inspection`. Baseline commit: `6c476af`.
Current local package: `0.1.0.dev0`. M0 is accepted by the owner's explicit request
to implement M1/M2; its original handoff is preserved in
[evidence/m0/handoff.md](evidence/m0/handoff.md).

PR follow-up, 2026-09-08: the owner explicitly requested a pull request to `main`
and instructed us not to start M3. This authorizes pushing the current feature
branch and opening the PR, without merging or publishing a package. The fetched
`main` still predates M0, so the PR includes the foundation, supplied logo and
M1/M2 implementation. Code remains at the validated implementation commit
`7101167`; this follow-up changes only continuation documentation. Review the PR
and await the owner's next instruction. Milestone acceptance is unchanged.

**M1 and M2: ready_for_owner_review, not accepted.** The owner authorized this
batch explicitly. At the implementation handoff, no push, publication, paid GPU,
endpoint request, model weight download or global configuration change occurred.
M3 has not been started; the later PR authorization above supersedes the previous
no-push boundary only for this feature branch and its PR to `main`.

## Implemented changes

- M1: pinned eight-artifact resolver/cache, bounded EXIF/RGB image handling,
  content identity, real native CPU processor, actual ID/attention-mask/patch
  accounting, independent reference tests, shared `inspect_media` API and CLI.
- M2: bounded two-pass PyAV scan/selection, native-default and uniform PTS modes,
  actual PTS versus processor labels, explicit single-frame repair/native padding,
  opt-in thumbnails, atomic stored runs, lightweight escaped HTML and comparison.
- Package: Jinja2 base rendering, template/allowlist/type-data packaging, strict
  schema readers, protected overwrite, consistent CLI exits and JSON stdout.
- Original MIT synthetic PNG/FFV1 examples and actual reports/evidence. Supplied
  logo remains in the README unchanged. [ADR 0003](decisions/0003-cpu-inspection.md)
  records native-call, sampling, timestamp, device and resource decisions.

## Actual validation

Environment: macOS 26.6.2 ARM64; base Python 3.12.11 and 3.11.15; inspect Python
3.12.11 with [recorded versions](evidence/m2/environment.json). Pinned uv executable
`/private/tmp/modalmeter-uv-tool/bin/uv` 0.11.7 and cache
`/private/tmp/modalmeter-uv-cache`. See [local development](local-development.md).

| Actual command/check | Result and evidence |
| --- | --- |
| `.venv/bin/python -m ruff format --check .` | 22 files formatted; [log](evidence/m2/ruff-format.txt) |
| `.venv/bin/python -m ruff check .` | Passed; [log](evidence/m2/ruff.txt) |
| `.venv/bin/python -m mypy` | 19 source files; [log](evidence/m2/mypy.txt) |
| `.venv/bin/python -m pytest -q` | 137 passed, 34 deselected; [log](evidence/m2/pytest-py312.txt) |
| `.venv-py311/bin/python -m pytest -q` | 137 passed, 34 deselected; [log](evidence/m2/pytest-py311.txt) |
| `MODALMETER_TEST_PROCESSOR_DIR=$PWD/.cache/modalmeter/89644892e4d85e24eaac8bacfd4f463576704203 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false .venv-spike/bin/python -m pytest -q -m processor` | 34 passed, 137 deselected; [log](evidence/m2/processor.txt) |
| Base CLI prepare, image/default/odd/single/VFR/video-budget inspect, compare and base report | All exit 0; [commands](evidence/m2/quickstart.txt); image offline rerun equal except UUID/time/timings |
| `uv build --no-sources` with pinned executable/cache/native 3.12 | Final wheel/sdist built after template adjustment; [log](evidence/m2/build.txt) |
| `python scripts/package_smoke.py` with `.venv` then `.venv-py311`, pinned uv on PATH | Final wheel and sdist each installed cleanly on both Python versions; heavy imports/network blocked during stored rendering; [3.12](evidence/m2/package-py312.txt), [3.11](evidence/m2/package-py311.txt) |
| Final template report/storage checks | 58 passed; [log](evidence/m2/final-report-tests.txt) |
| Browser QA of actual HTML | Passed at actual 390/1440 CSS px; [screenshots and method](evidence/m2/visual/README.md) |
| Wheel source/template/allowlist identity and packaged file inspection | Source bytes match checkout; no weights/private runs; [contents/hashes](evidence/m2/package-manifest.json) |

The 34-case processor selection is one shared suite, including 21 independent
reference cases plus media/guard regressions. Do not double-count it by modality.
Two upstream Typer/Click deprecation warnings remain; they did not fail checks.
Intermediate stale M0 assertions, an inconsistent missing-PTS fixture, mixed native
reference kwargs, sandbox dependency DNS, and browser CSP/minimum-width/lazy-image
issues were corrected. [M2 evidence](evidence/m2/README.md) records the limitations
and failed attempts instead of hiding them. Final supported checks are green.

## Results to review

1. [M1 image JSON](evidence/m1/image/inspection.json): grid [1,14,22], 308 observed
   patch rows, 77 visual placeholders, 91 complete prompt positions.
2. [Video timeline report](evidence/m2/video-odd/report.html): selected 3 / processed
   4 with an explicit final-frame repeat, actual source PTS and native labels.
3. [8 versus 16 frame comparison](evidence/m2/comparison/report.html): same total
   budget yields 64×32 versus 32×32 frames, 8 visual placeholders in both, complete
   prompt 52 versus 84. Coupled resize is visible; no latency/quality implication.
4. [Working README quickstart](../README.md) and [M1](evidence/m1/README.md)/
   [M2](evidence/m2/README.md) evidence indexes.

## Support and exact next action

CPU processor verification applies only to the exact local tuple in the
[support matrix](support-matrix.md); vLLM image/video parity is unverified.
No hosted CI, Linux inspect, Python 3.11 inspect-extra, live inference, GPU memory,
quality or speedup validation was performed. Missing PTS/FPS is unsupported;
source PTS and native ordinal/FPS labels intentionally differ for VFR. Decode
limits are cooperative; tensor limits are preflight allowances, not hard RSS caps.

No missing user input blocks M1/M2 review. Wait for owner verification. After
explicit continuation, M3 adds CPU-tested endpoint transport and HTTP/SSE protocol
measurement. M4 still needs an owner-provided endpoint/config; do not provision
hardware or infer live parity from mocks. Report the resulting local signed-off
commit hash in the handoff, avoiding a self-referential hash edit here.
