# Agent Instructions for ModalMeter

## Product
ModalMeter is a Python library and CLI for inspecting multimodal inputs and
measuring their serving behavior. Read docs/vision.md, docs/roadmap.md,
docs/measurement-contract.md, docs/support-matrix.md, and
docs/implementation-state.md before changing behavior.

## Communication and execution
- Discuss work with the maintainer in Turkish.
- Write code, comments, documentation, CLI output, and commits in English.
- Work one milestone at a time unless the user explicitly authorizes a batch.
- Complete the milestone's concrete work and relevant checks before requesting
  milestone verification. Do not ask permission for each routine edit.
- Show actual output and limitations. Never report an unrun check as passed.
- Resume from implementation-state.md; re-read source instead of trusting a
  previous agent's summary alone.

## Evidence and correctness
- Separate observed, measured, derived, estimated, and unavailable data.
- Missing measurements are null with reasons, never zero.
- Processor correctness and backend parity are separate, versioned claims.
- Do not equate encoder patches, visual placeholders, and full prompt tokens.
- Do not equate video input with a sequence of independent image requests.
- Preserve sampling, timestamps, transforms, temporal padding, and provenance.
- SSE events are not tokens. Client timings are not kernel/stage timings.
- Device/server memory is not automatically per-request memory.
- Do not predict exact OOM, safe concurrency, speedups, or retained quality
  without an explicit validated method and workload.
- Re-check upstream source at installed versions. Record key choices in ADRs.

## Architecture
- Keep the CLI thin and use shared typed core functions for the Python API.
- Keep CPU inspection free of model weights, vLLM runtime, and GPU requirements.
- Lazy-load optional heavy dependencies; help and stored-report rendering must
  remain usable without the inspection extra.
- Prefer small concrete modules and one tested adapter over speculative
  abstraction or empty future packages.
- Do not add paid services, cloud dashboards, agents, or MCP to the MVP.

## Tests and reports
- Run relevant lint/type/tests and clean package smoke checks for the change.
- Keep default unit tests offline and distinguish processor/live GPU tests.
- Use independent reference behavior and small deterministic fixtures.
- Mock protocol tests do not validate a serving engine or GPU performance.
- Render HTML from real typed results; escape external text and work offline.
- Report visual QA as pending if the generated page cannot be inspected.
- Keep private media, model caches, run outputs, traces, and secrets out of Git.

## Git and completion
- Inspect Git status first and preserve unrelated changes.
- Use oguzhankir/<kebab-topic> feature branches; do not commit directly to main.
- Use the existing verified maintainer identity; never invent an email or alter
  global Git configuration. Follow required attribution rules of the environment.
- When creating a local commit, use an English message and git commit -s.
- Stage only reviewed task files. Do not force push, rewrite user history,
  publish, change visibility, or push without the applicable authorization.
- Update CHANGELOG.md and docs/implementation-state.md with actual changes,
  commands/results, skipped checks, blockers, and the exact next action.
- Never mark a milestone accepted before the owner verifies it.

## First steps after resuming
1. Read this file and the current implementation-state.md.
2. Inspect actual source, branch, worktree changes, and relevant upstream versions.
3. Work on the next authorized milestone and its acceptance criteria.
4. Show evidence, update continuation state, and respect the review boundary.

## Developer commands

Run from the repository root with uv 0.11.7 and Python 3.11/3.12. See
[local-development.md](docs/local-development.md) for verified native Mac paths
and the sandbox cache override. This table is the canonical command set.

| Purpose | Command | Scope |
| --- | --- | --- |
| Base environment | `uv sync --locked` | Locked contributor dependencies; no inspect extra |
| Format | `uv run --locked ruff format .` | Format Python source |
| Format check | `uv run --locked ruff format --check .` | CI formatting gate |
| Lint | `uv run --locked ruff check .` | Source, tests and probe scripts |
| Type check | `uv run --locked mypy` | Strict src/tests/scripts; feasibility probe excluded |
| Offline tests | `uv run --locked pytest` | Excludes processor/live groups |
| Help/version | `uv run --locked modalmeter --help` / `uv run --locked modalmeter --version` | Only implemented CLI surface |
| Package build | `uv build --no-sources` | Wheel and sdist, no publish |
| Clean package checks | `uv run --locked python scripts/package_smoke.py` | Independent wheel/sdist base installs; may download dependencies |
| Processor integration | `MODALMETER_TEST_PROCESSOR_DIR=/absolute/prepared/revision uv run --locked --extra inspect pytest -m processor` | Prepare explicitly first; see docs/testing.md; skips are not verification |
| M0 feasibility reproduction | See [probe instructions](docs/evidence/m0/README.md) | Explicit artifact download, then offline probe; not correctness coverage |

Inspection, report and comparison are implemented; use README.md for the working CPU quickstart.
HTTPX endpoint/protocol work remains M3; live validation remains M4.
