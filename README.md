<p align="center">
  <img src="docs/assets/modalmeter-logo.png" alt="ModalMeter logo" width="360">
</p>

# ModalMeter

**Profile multimodal inference. Understand visual tokens, latency, and GPU memory.**

ModalMeter now inspects local images and short videos with a real Qwen3-VL CPU
processor, records exactly which frames and prompt positions it produced, and
creates portable offline reports. Version `0.1.0.dev0` implements M1/M2 for owner
review. Endpoint benchmarking, GPU memory and answer quality are not measured yet.

## CPU quickstart

Use uv 0.11.7–0.11.x and native Python 3.11/3.12. See the
[support matrix](docs/support-matrix.md) for the actually tested tuple and
[local setup](docs/local-development.md) for this Mac's interpreter/cache paths.

```bash
uv sync --locked --extra inspect
uv run --locked --extra inspect modalmeter prepare --cache-dir .cache/modalmeter
uv run --locked --extra inspect python examples/generate_fixtures.py --output runs/synthetic-media

uv run --locked --extra inspect modalmeter inspect runs/synthetic-media/synthetic-image.png \
  --cache-dir .cache/modalmeter --offline --output runs/image

uv run --locked --extra inspect modalmeter inspect runs/synthetic-media/synthetic-video.mkv \
  --sampling uniform --frames 3 --cache-dir .cache/modalmeter --offline \
  --include-media --output runs/video

uv run --locked modalmeter report runs/video --output report.html
```

Each inspection writes `inspection.json`, `manifest.json`, and `report.html`.
Open HTML directly in a browser. Stored reports work with the base package alone;
no processor download or inspect extra is needed to render/compare them. Default
exports omit raw prompt, filenames, local paths and media. `--include-media` must
be explicit both when collecting thumbnails and when rendering them. Supply your
own UTF-8 prompt with `--prompt-file`; its text is never retained. Existing outputs
require `--overwrite`, and directories containing unrelated files are protected.

The inspect extra includes substantial Torch/torchvision and PyAV dependencies.
The explicit prepare step downloads **eight processor artifacts, 11,499,725 bytes,
zero model weights**, at an immutable revision. It does not require CUDA, vLLM,
a GPU, a shell FFmpeg executable, or a serving endpoint on the tested Mac.

## A reproducible frame/resize trade-off

The generated 16-frame fixture exposes a real processing decision:

```bash
uv run --locked --extra inspect modalmeter inspect runs/synthetic-media/coupled-budget-video.mkv \
  --sampling uniform --frames 8 --pixel-budget 24576 \
  --cache-dir .cache/modalmeter --offline --output runs/frames-8
uv run --locked --extra inspect modalmeter inspect runs/synthetic-media/coupled-budget-video.mkv \
  --sampling uniform --frames 16 --pixel-budget 24576 \
  --cache-dir .cache/modalmeter --offline --output runs/frames-16
uv run --locked modalmeter compare runs/frames-8 runs/frames-16 --output runs/comparison
```

| Actual CPU result | 8 selected frames | 16 selected frames |
| --- | --- | --- |
| Processed frame dimensions | 64 × 32 | 32 × 32 |
| Visual embedding placeholder positions | 8 | 8 |

A fixed total video pixel budget couples frame count and resize. More frames do
not necessarily mean more visual positions. Prompt overhead can still change;
the report separates it. This is input evidence, with no speed or quality claim.

Open the actual [comparison HTML](docs/evidence/m2/comparison/report.html),
[video report](docs/evidence/m2/video-odd/report.html), or
[image JSON](docs/evidence/m1/image/inspection.json). Generated media is original
MIT test content; [fixture provenance](examples/README.md) explains exact pixels
and timestamps. [M1 evidence](docs/evidence/m1/README.md) and
[M2 evidence](docs/evidence/m2/README.md) contain actual commands and checks.

## Python API

```python
from pathlib import Path
from modalmeter.inspect import inspect_media
from modalmeter.schemas import InspectionConfig
from modalmeter.storage import write_inspection_run, compare_runs
from modalmeter.report import render_report

result = inspect_media(InspectionConfig(
    path=Path("runs/synthetic-media/synthetic-image.png"),
    cache_dir=Path(".cache/modalmeter"), offline=True,
))
write_inspection_run(result, "runs/python-image")
html = render_report(result)
```

## Limits and next steps

Only `Qwen/Qwen3-VL-2B-Instruct` at the recorded revision is accepted. Local CPU
reference verification is separate from **unverified server parity**. Actual
video PTS is separate from native ordinal/FPS timestamp labels; single-frame
videos use an explicitly recorded repair. Missing PTS/FPS fails clearly. Decoder
time and tensor budgets are admission safeguards, not hard native allocator/time
caps. See [ADR 0003](docs/decisions/0003-cpu-inspection.md) for exact constraints.

M3 will add endpoint protocol measurement after owner verification. Nothing is
published or pushed automatically. The [roadmap](docs/roadmap.md) records review
status and later hardware gates.

- [Vision](docs/vision.md), [architecture](docs/architecture.md), [data contract](docs/data-contract.md)
- [Measurement contract](docs/measurement-contract.md), [sources](docs/research.md)
- [Continuation state](docs/implementation-state.md), [contributing](CONTRIBUTING.md)
- [Security](SECURITY.md), [release gates](docs/releasing.md), [implementation contract](docs/implementation-instructions.md)

The existing [MIT license](LICENSE) is preserved. Model and dependency licenses
remain separate. The supplied ModalMeter logo is retained unchanged.
