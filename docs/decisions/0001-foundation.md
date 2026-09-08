# ADR 0001: Lightweight Python foundation and existing license

Date: 2026-09-08. Status: chosen for M0; owner milestone acceptance is separate.

## Context and evidence

The checkout at `a954f0c` contained a placeholder README (`# vllm-doctor`) and an
MIT license with the owner's copyright. It had no package or existing AGENTS file.
The machine is ARM64 macOS but the default Conda Python is x86_64. Native Python
3.12.11 and 3.11.5 exist. The contract defaults to Apache-2.0 only for a new project
without an existing license; it explicitly preserves repository choices.

## Decision

Preserve LICENSE byte-for-byte and publish MIT package metadata. Replace the stale
placeholder title with the requested ModalMeter identity. Use native interpreters,
Python `>=3.11,<3.13`, `src/`, Hatchling 1.27.0, mypy strict, Ruff, pytest and uv
0.11.7 with a reviewed lock. Avoid asserting 3.13 compatibility. Use Typer/Rich for
the CLI and Pydantic for numeric evidence. Add HTTPX and direct Jinja2 dependencies
only with their real features. Ship `py.typed`.

Base published dependency bounds are deliberate major/minor boundaries:
Pydantic `>=2.12,<3`, Rich `>=14.2,<15`, Typer `>=0.21,<0.22`. Tests establish the
locked resolutions, not every release in these ranges. The optional inspection
tuple is exact-pinned for the initial spike; revisiting pins requires processor
regression evidence. On Linux, uv maps Torch/torchvision to the official CPU index;
plain pip extra installation may choose larger GPU-capable wheels and is not the
verified CPU-only contributor route.

## Consequences and verification

The base CLI has help/version only and rejects future commands. No platform or
model support is inferred from dependency resolution alone. Install the actual
wheel and sdist into separate base environments outside the source directory,
check package identity/data and absent heavy modules, then exercise the CLI and
stored evidence JSON. See [actual validation](../evidence/m0/README.md).

The [uv package guide](https://docs.astral.sh/uv/guides/package/) documents
`uv build`; `--no-sources` validates published build metadata independently of
development source mappings. Build/publish are distinct operations; no publication
is authorized. CI uses commit SHAs resolved from GitHub, recorded in
[source references](../evidence/m0/source-refs.json).

## Environment drift observed during validation

The initial Conda path and local uv executable disappeared during M0; the global
uv command became Homebrew 0.12.10. This work did not change global installations.
An isolated uv 0.11.7 tool under `/private/tmp/modalmeter-uv-tool` preserves the
verified command version. Universal Python 3.11.5 attempts encountered x86_64
wheels under an ARM64 runtime; the final 3.11 test target is a temporary managed
ARM64 Python 3.11.15, installed with no global binary links. The initial failures
remain in the evidence directory. Do not report those attempts as passed or
upgrade the project's tool version merely to hide the environment change.
