# Testing

Use the canonical commands in [AGENTS.md](../AGENTS.md#developer-commands).
The default pytest selection excludes `processor` and `live`; neither group has
tests yet. Selecting an empty group is not integration evidence and exits 5.
Do not treat the M0 standalone probe as M1/M2 processor correctness coverage.

| Group | Present scope | What it cannot establish |
| --- | --- | --- |
| Offline unit/contract | CLI help/version/invalid future command, blocked heavy imports, finite numeric evidence, zero vs missing, provenance, JSON roundtrip and unsupported schema rejection | Model token accounting or media correctness |
| Package smoke | Each actual wheel/sdist installed into its own temporary base venv; installed identity, entry point, `py.typed`, JSON load, no heavy dependency, dependency consistency | Processor or GPU support |
| Processor | M1/M2 planned: independent pinned reference output, bounded synthetic fixtures, cached offline rerun | Server parity |
| Protocol | M3 planned: local real HTTP/SSE mock server, failure handling, timing and bounded concurrency | A real vLLM engine or GPU measurements |
| Live parity | M4 planned: actual endpoint/model/config/media tuple | Untested modalities, releases or other machines |
| Telemetry/profiling | M5/M6 planned: real source/scope/units and instrumentation overhead | Guaranteed peaks or universal capacity |

CI config runs base CPU checks on Linux Python 3.11/3.12 and a macOS 3.12 job
with read-only contents permission and verified SHA-pinned actions. It has not run
on GitHub until an authorized push/workflow run occurs. No GPU job, publication,
secret-dependent PR workflow or processor download runs by default.

The M0 evidence fixture is authored for this project under its MIT license and
contains no media. The feasibility probe generates three solid-color frames in
memory and a temporary lossless FFV1 video; neither private media nor weights are
used. Future fixtures must cover image aspect/size boundaries and video odd/short,
padding, noninteger FPS, VFR/nonzero origin, missing metadata, corruption and
resource-limit outcomes. Tests must use observable reference behavior, not merely
repeat the same implementation formula. Keep huge tensors/caches outside Git.

Package smoke uses locked base dependency constraints but allows build-system
downloads to install the sdist. Ordinary pytest runs need no network. Coverage is
a diagnostic; no arbitrary percentage gate substitutes for meaningful behavior.
