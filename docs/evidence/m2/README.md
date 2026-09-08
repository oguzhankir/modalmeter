# M2 video, report and comparison evidence

Actual local CPU work on 2026-09-08, ModalMeter 0.1.0.dev0. The owner authorized
M1/M2 together. Both implementations await owner review; M3 was not started.

## Actual outputs

| Case | Selected / processed | Grid | Visual placeholders | Complete prompt |
| --- | --- | --- | --- | --- |
| [Native default video](video-default/report.html) | 6 / 6 | [3,4,6] | 18 | 54 |
| [Uniform odd selection](video-odd/report.html) | 3 / 4 | [2,4,6] | 12 | 40 |
| [Single-frame repair](video-single/report.html) | 1 / 2 | [1,4,6] | 6 | 26 |
| [VFR / nonzero origin](video-vfr/report.html) | 3 / 4 | [2,4,6] | 12 | 40 |
| [8 frames, budget 24576](frames-8/report.html) | 8 / 8 | [4,2,4] | 8 | 52 |
| [16 frames, budget 24576](frames-16/report.html) | 16 / 16 | [8,2,2] | 8 | 84 |

The [comparison](comparison/report.html) shows 64 × 32 versus 32 × 32 processed
frames and equal visual counts: a coupled frame/resize change. Extra timestamps
and boundaries account for different complete prompt counts. It does not measure
latency, GPU memory or answer quality. JSON/manifests are beside each report.
Thumbnails here are explicitly included original MIT synthetic pixels.

VFR selected source PTS are 2.0, 3.1, 3.9 seconds, while processor ordinal/FPS
values are 0.0, 1.2, 1.6. Native grouped labels are `<0.6 seconds>` and
`<1.6 seconds>`. These are separate observations, not a claim of timestamp/server
parity. A single selected frame is explicitly replicated before native resize;
odd counts otherwise use native final-frame padding. Missing PTS/FPS and invalid
metadata are rejected; unknown stream duration remains null with a reason.

## Validation record

- [Quickstart](quickstart.txt): real CLI generation/inspection/compare, base-only
  report and comparison rerender, JSON-only stdout and offline rerun equality.
- [Environment](environment.json): exact native Mac CPU dependency tuple.
- [Processor](processor.txt): **34 passed**, 137 deselected, no hidden downloads.
  This includes 21 independent processor reference cases and media/guard tests.
- [Offline Python 3.12](pytest-py312.txt), [Python 3.11](pytest-py311.txt):
  **137 passed each**, 34 deselected. Two upstream Typer/Click deprecation warnings.
- [Ruff format](ruff-format.txt), [Ruff](ruff.txt), [strict mypy](mypy.txt): passed.
- [Build](build.txt), [clean wheel/sdist Python 3.12](package-py312.txt),
  [Python 3.11](package-py311.txt): actual package evidence, not hosted CI.
- [Final report/storage checks](final-report-tests.txt): 58 passed after the visual adjustment.
- [Packaged contents and SHA-256](package-manifest.json), [actual fixture provenance](fixture-provenance.json).
- [Source references and choices](../../decisions/0003-cpu-inspection.md).

Package checks block heavy imports and network access during real stored-image
and explicitly labeled comparison-copy rendering. The comparison copy is only a
serialization smoke fixture, not another measured run. Actual independent video
runs above establish the end-to-end comparison workflow.

## Failed attempts, corrections and scope

An intermediate default test run found obsolete M0 help assertions and a report
fixture with inconsistent missing PTS. Tests were updated to the implemented CLI
and coherent metadata. The independent pixel-budget reference initially mixed
flat/nested native kwargs; its controls were corrected, not production counts.
A sandboxed Python 3.11 MarkupSafe fetch failed DNS and succeeded with authorized
network access. Full final tests passed after these corrections.

Initial headless Chrome could capture desktop HTML after sandbox escalation.
The report CSP correctly blocked temporary inline QA instrumentation; a temporary
copy was used for preliminary measurements, leaving real report CSP intact.
The window-size flag requested 390 but Chrome used a 500 CSS-pixel minimum, so
those captures did not establish 390-pixel QA. Final direct browser metrics and
screenshots passed at actual 390 and 1440 CSS pixels; see [visual QA](visual/README.md).
Comparison field columns and
long frame-mapping values were improved after visual review.

No hosted CI, Linux inspect run, Python 3.11 inspect-extra run, live serving
endpoint, GPU telemetry, package publication or Git push was performed. Decoder
time and tensor limits are cooperative/admission constraints rather than hard
native execution/RSS caps. See [support matrix](../../support-matrix.md).
