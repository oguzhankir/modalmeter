# Synthetic CPU examples

The [fixture generator](generate_fixtures.py) creates original deterministic RGB
pixels and lossless FFV1 videos using the inspection extra. No model, weights,
GPU, external media, or FFmpeg executable is required to generate these fixtures.
Run from the repository root after installing the inspection extra:

```bash
uv run --locked --extra inspect python examples/generate_fixtures.py \
  --output runs/synthetic-media
```

Follow the implemented inspection and report commands in the [root
quickstart](../README.md). Generated media and run outputs remain in the ignored
`runs/` directory. They represent test inputs, never serving measurements or
model answers.

| Generated file | Known input behavior |
| --- | --- |
| `synthetic-image.png` | RGB PNG, 160 × 96 pixels |
| `synthetic-video.mkv` | Six distinct 96 × 64 frames at 2 FPS, PTS 0 to 2.5 seconds |
| `coupled-budget-video.mkv` | Sixteen frames at 4 FPS for comparing 8 and 16 selected frames with a fixed total pixel budget |
| `single-frame.mkv` | One frame; exercises the explicitly recorded short-video repair |
| `noninteger-fps.mkv` | Five frames at 2.5 FPS, PTS 0 to 1.6 seconds |
| `vfr-offset.mkv` | Five frames at PTS 2.00, 2.12, 2.53, 3.10, 3.90 seconds; nominal FPS 2.5 |
| `fixture-provenance.json` | Original file hashes, dimensions, ordinals, known PTS, and RGB pixel hashes |

The generator and its original algorithmic media use this repository's MIT
license. Pixels and presentation times are deterministic. Matroska container
metadata can vary across encoder runs, so file hashes are captured from each
actual generated file. Processor tests independently decode the fixtures and
compare exact RGB hashes and rational timestamps to the manifest.

The VFR example intentionally distinguishes actual presentation timestamps from
the pinned processor's ordinal/FPS timestamps. Its locally verified token counts
do not establish timestamp or serving parity. The single-frame example requires
a documented duplicate before the pinned processor's resize path; it is not an
unmodified native single-frame processing claim.

No private owner media is included. The older [M0 feasibility
probe](../docs/evidence/m0/README.md) remains historical evidence, separate from
the M1/M2 reference acceptance tests.
