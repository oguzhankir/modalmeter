# Support matrix

This is the canonical capability matrix. A candidate or feasibility observation
is not a supported processor/backend claim. Milestone status lives in the
[roadmap](roadmap.md); concrete check output lives in [M0 evidence](evidence/m0/README.md).

| Capability | OS / architecture / Python | Versions or identity | Evidence level |
| --- | --- | --- | --- |
| Base help/version, evidence JSON, offline tests | macOS 26.6.2 / ARM64 / 3.12.11 | ModalMeter 0.0.0.dev0; locked base deps | Local checks; see logs |
| Base help/version, evidence JSON, offline tests | macOS 26.6.2 / ARM64 / 3.11.15 | Same package and lock | Local checks; see logs |
| Base CI | Linux / runner architecture / 3.11, 3.12; macOS runner / 3.12 | SHA-pinned workflow, uv 0.11.7 | Configured; hosted execution not run |
| Qwen3-VL image processor | macOS ARM64 / 3.12.11 | Model revision and tuple below | Loads in feasibility probe; no image correctness test or adapter; candidate |
| Qwen3-VL video processor + PyAV | macOS ARM64 / 3.12.11 | Model revision and tuple below | Synthetic feasibility only; candidate; not processor_verified |
| Inspection extra on Linux or Python 3.11 | Candidate CPU environment | Locked dependency resolution | Not executed; candidate |
| vLLM image parity | No supplied endpoint | Engine/hardware/config unknown | server_parity_unverified |
| vLLM video parity | No supplied endpoint | Engine/transport/config unknown | server_parity_unverified |
| HTML report, benchmark, telemetry, stage profiling | None | Deferred features | Not implemented |

Initial model: `Qwen/Qwen3-VL-2B-Instruct` at
`89644892e4d85e24eaac8bacfd4f463576704203` (public, ungated at check time).
Feasibility tuple: Transformers 4.57.6, Torch 2.9.1, torchvision 0.24.1,
Pillow 12.0.0, PyAV 16.1.0, NumPy 2.5.3, huggingface-hub 0.36.2,
tokenizers 0.22.2. Adapter version: unavailable (no adapter exists). Complete
resolved dependencies are in `uv.lock`; base/spike runtime inventories accompany
the evidence. Do not extrapolate to another checkpoint, release, OS or modality.

Track processor verification independently of server parity. A mismatch must
retain the observed disagreement, not be downgraded to unverified. Passing image
parity cannot upgrade video; server mismatch cannot erase a valid CPU check.
VFR/PTS and metadata/tensor constraints are documented in
[ADR 0002](decisions/0002-processor-path.md).
