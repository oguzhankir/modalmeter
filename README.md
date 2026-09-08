<p align="center">
  <img src="docs/assets/modalmeter-logo.png" alt="ModalMeter logo" width="360">
</p>

# ModalMeter

**Profile multimodal inference. Understand visual tokens, latency, and GPU memory.**

ModalMeter aims to connect the frames and pixels a vision-language model receives
to evidence about its serving behavior. It is for engineers investigating image
and short-video workloads, initially Qwen3-VL with a separately validated vLLM path.

This checkout is the **M0 foundation**, version `0.0.0.dev0`, not an inspection
release. Implemented: CLI help/version, typed numeric evidence records, offline
contract tests, and package checks. `inspect`, `report`, `compare`, `benchmark`, and
`sweep` are planned and are not commands yet. There are no benchmark claims.

## Working quickstart

From this checkout with uv 0.11.7 and native Python 3.11 or 3.12:

```bash
uv sync --locked
uv run --locked modalmeter --help
uv run --locked modalmeter --version
uv run --locked pytest
```

Version output: `modalmeter 0.0.0.dev0`. The base package installs no PyTorch,
Transformers, video decoder, vLLM or CUDA dependency. For this Mac's interpreter
selection and sandbox cache location, use [local development](docs/local-development.md).
The optional `[inspect]` dependencies are for the recorded feasibility probe;
installing the extra does not add a working inspector. It includes substantial
PyTorch/torchvision and video-library downloads.

## Evidence and limits

See the [support matrix](docs/support-matrix.md) for tested environments and
explicitly unverified candidates. The [M0 evidence](docs/evidence/m0/README.md)
contains the synthetic processor feasibility result and actual validation logs.
The [golden evidence JSON](tests/fixtures/evidence-v1.json) can be read offline;
it is a schema example, not a media inspection or performance result. A rendered
offline demo will arrive with M2. No HTML demo is implemented in M0.

There is no supported model adapter or live backend yet. No weights or GPU are
needed for the current commands. CPU processor feasibility does not establish
token-accounting correctness, video timestamp parity, or server behavior.

## Project documents

- [Vision](docs/vision.md), [architecture](docs/architecture.md), [roadmap](docs/roadmap.md)
- [Measurement contract](docs/measurement-contract.md), [data contract](docs/data-contract.md)
- [Research and sources](docs/research.md), [decisions](docs/decisions/0002-processor-path.md)
- [Continuation state and review boundary](docs/implementation-state.md)
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md), [release gates](docs/releasing.md)
- [Preserved implementation contract](docs/implementation-instructions.md)

The repository's existing [MIT license](LICENSE) is preserved. Model, dependency,
and future media licenses remain separate.
