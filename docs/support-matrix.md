# Support matrix

Canonical capability matrix, checked 2026-09-08. A local passing check is not owner
acceptance or hosted CI evidence. [Roadmap](roadmap.md) tracks review status.

| Capability | OS / architecture / Python | Versions or identity | Evidence |
| --- | --- | --- | --- |
| Base CLI, JSON, reports/comparison, offline contracts | macOS 26.6.2 / ARM64 / 3.12.11 | ModalMeter 0.1.0.dev0, locked base deps | 137 offline tests; M2 logs |
| Same base workflow | macOS 26.6.2 / ARM64 / 3.11.15 | Same package/lock | 137 offline tests; M2 logs |
| Wheel/sdist base install | Same two native Python versions | Templates, allowlist, py.typed, actual stored result rendering | Clean package logs in M2 evidence |
| Qwen3-VL image inspection | macOS 26.6.2 / ARM64 / 3.12.11 | Exact tuple below; qwen3-vl-native/1 | processor_verified; independent image boundaries/IDs/mask/resize tests |
| Qwen3-VL video inspection + PyAV | Same native 3.12 tuple | Exact tuple below; staged selection + native processing | processor_verified; independent default/uniform/odd/single/noninteger/VFR/repeated-PTS/resize cases |
| Video source timestamp fidelity | Exact tuple above | Actual PTS separately from native ordinal/FPS labels | Distinction verified; native prompt labels do not reproduce VFR/nonzero source PTS |
| Base CI | Linux 3.11/3.12, macOS 3.12 runner | Existing SHA-pinned workflow | Hosted runs tracked on [PR #1](https://github.com/oguzhankir/modalmeter/pull/1/checks); first ANSI-sensitive help assertion fixed with plain/color regression cases |
| Inspect extra on Linux, Python 3.11, other Mac releases | Candidate environments | Locked resolution only | Not executed; no automatic verified label |
| vLLM image parity | No supplied endpoint | Engine/hardware/config unknown | server_parity_unverified |
| vLLM video parity | No supplied endpoint | Engine/transport/config unknown | server_parity_unverified |
| Endpoint benchmarking, telemetry, stage profiling | Future M3–M6 | No implementation yet | No latency, GPU memory, quality or speedup claim |

Model: `Qwen/Qwen3-VL-2B-Instruct`, revision
`89644892e4d85e24eaac8bacfd4f463576704203`. Exact processor tuple:
Transformers 4.57.6, Torch 2.9.1, torchvision 0.24.1, Pillow 12.0.0,
PyAV 16.1.0, NumPy 2.5.3, tokenizers 0.22.2, huggingface-hub 0.36.2.
Complete inventory: [environment.json](evidence/m2/environment.json); contributor
resolution: `uv.lock`. The final explicit cached processor selection runs **34
cases** total (21 independent processor reference cases plus media and adapter
regressions); these are one suite, not two modality totals to add together.

A mismatch preserves the disagreement. Verification is an adapter/reference-suite
claim for this exact OS/Python/dependency tuple, supplemented by each run's actual
grid/tensor/ID consistency check; it is not a guarantee for arbitrary inputs.
Single-frame video requires a recorded repair. Resource limits and unsupported
metadata outcomes are in [ADR 0003](decisions/0003-cpu-inspection.md).
