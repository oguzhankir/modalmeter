# Testing

Use the canonical commands in [AGENTS.md](../AGENTS.md#developer-commands).
Default pytest is offline and excludes `processor`/`live`. The processor group
requires an explicitly prepared, exact eight-file artifact directory. It never
implicitly downloads: absent `MODALMETER_TEST_PROCESSOR_DIR` causes skips, which
must not be described as processor validation.

| Group | Current evidence | Limit |
| --- | --- | --- |
| Offline contracts | Schemas, malformed records, artifact integrity, CLI exits/import boundary, bounded sampling, report privacy/comparison, atomic persistence | No reference processor claim |
| Processor integration | Actual image boundaries, attention-mask padding, native reference grids/IDs, video selection/padding, VFR/nonzero/repeated PTS, pixel budgets, invocation count and CPU guards | Exact pinned tuple; no serving parity |
| Package smoke | Separate clean wheel/sdist installs, help/version, package data, stored inspection/compare HTML, missing heavy dependencies, dependency consistency | Base package only |
| Protocol | M3 planned | Future HTTP/SSE tests will not prove GPU behavior |
| Live parity | M4 planned | Needs owner endpoint/config; no live test performed |

Prepare explicitly, then run the offline processor group:

```bash
uv sync --locked --extra inspect
uv run --locked --extra inspect modalmeter prepare --cache-dir .cache/modalmeter
MODALMETER_TEST_PROCESSOR_DIR="$PWD/.cache/modalmeter/89644892e4d85e24eaac8bacfd4f463576704203" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  uv run --locked --extra inspect pytest -m processor
```

Reference tests verify independently hardcoded artifact hashes and use unmodified
AutoProcessor objects. Synthetic FFV1 media has known original RGB frame IDs and
rational PTS, independently decoded against the generator provenance. A standalone
M0 probe is historical feasibility, not acceptance coverage. See [examples](../examples/README.md)
for MIT fixture provenance. No weights/private media are tracked.

Hosted base CI targets Linux Python 3.11/3.12 and macOS 3.12 with read-only
permissions and SHA-pinned actions. Hosted execution has not run without an
authorized push. No GPU or publish job exists. Package smoke may fetch locked
base/build dependencies; ordinary tests do not need network. Final local evidence,
including actual counts and visual QA, lives in [M1](evidence/m1/) and [M2](evidence/m2/).
