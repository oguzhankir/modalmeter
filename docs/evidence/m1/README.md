# M1 image inspection evidence

Actual local CPU work on 2026-09-08, ModalMeter 0.1.0.dev0. M1 is ready for owner
review, not accepted. M0's original evidence remains in its separate directory.

- [Image inspection.json](image/inspection.json), [manifest](image/manifest.json),
  [HTML](image/report.html): original generated RGB PNG, 160 × 96 source pixels,
  352 × 224 processed pixels, grid `[1,14,22]`, 308 actual patch rows,
  **77 actual visual placeholders, 91 non-padding prompt positions**.
- [prepare.json](prepare.json): actual base CLI preparation, exactly eight verified
  processor artifacts totaling 11,499,725 bytes; zero weights. The cache is ignored
  under `.cache/modalmeter/<immutable revision>`.
- [Processor test notes](processor-tests.txt): initial independent cases and the
  additional pixel-budget invocation finding. Final expanded shared run:
  [34 passed](../m2/processor.txt), including image/video/media/guard tests.
- [Offline 3.12](../m2/pytest-py312.txt), [offline 3.11](../m2/pytest-py311.txt):
  137 passed each. [Ruff](../m2/ruff.txt), [format](../m2/ruff-format.txt),
  [mypy](../m2/mypy.txt), [build](../m2/build.txt), and clean package logs in M2.

Actual reproduction (run from the checkout; environment setup in local-development):

```bash
.venv/bin/modalmeter prepare --cache-dir .cache/modalmeter
.venv-spike/bin/python examples/generate_fixtures.py --output runs/synthetic-media
.venv-spike/bin/modalmeter inspect runs/synthetic-media/synthetic-image.png \
  --cache-dir .cache/modalmeter --offline --output runs/image-check --json
```

The exact end-to-end command record is [quickstart.txt](../m2/quickstart.txt).
A second offline run was compared structurally: every field except run UUID,
creation time and measured preparation timings was equal. Machine-readable stdout
parsed as exactly one JSON record. Counts are observed from actual processor
outputs; no model generation, endpoint request, GPU or model weights were used.

The image boundary/reference cases include tiny dimensions, ratios up to 200,
rejection above 200, actual attention-mask padding and explicit pixel-budget
resize. EXIF/RGB, corrupt/oversized inputs, resource preflight and reserved
placeholder strings have separate regressions. `processor_verified` applies to
the [exact recorded tuple](../../support-matrix.md); server parity is unverified.
