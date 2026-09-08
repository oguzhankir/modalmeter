# Data contract

## Versioned records and availability

`InspectionConfig`, `InspectionResult`, `MediaManifest`, `ComparisonResult` and
`Measurement` are defined in `src/modalmeter/schemas.py`. The older standalone
`EvidenceDocument` remains readable as evidence, not an inspection. Current stored
records use explicit `schema_version="1.0"` and `record_kind`; loaders reject
missing identity, unknown versions (including unsupported minors), extra fields,
duplicate JSON keys and non-finite numbers. Nested manifests are validated too.
Future schema evolution requires explicit migration tests, never relabeling old
records. Models are frozen; nested containers are not deeply immutable, so output
and report boundaries revalidate records.

Measurements require finite strict numbers with unit, evidence kind, source,
scope and method. Unavailable values require null plus a nonblank reason; zero
remains an actual value. Durations use milliseconds, memory/file limits use bytes,
and source/processor timestamps use seconds. Nothing is called simply `tokens`.
Actual patch rows, active placeholder IDs and attention-mask length are observed;
grid/merge counts and nonvisual residual are derived. Isolated timestamp/user-text
positions and server usage remain unavailable when not proven.

## Identity, media and provenance

SHA-256 covers original file bytes, rechecked after decoding. Prompt and template
hashes cover UTF-8 text. Run IDs are UUIDs with UTC creation time, not content
hashes. Tool version, immutable model revision, adapter version, artifact hashes,
dependency versions, runtime and effective processor settings accompany results.

Manifests distinguish decoded count from reported container count, selected count
from processed count, and rational source PTS from ordinal/FPS processor times.
Each processed position maps to a selected source ordinal with an explicit
repeat/padding reason. Image PTS/FPS/duration are unavailable with modality reasons.
Missing video PTS/FPS is rejected rather than invented. Unknown stream duration
remains null even when an unrelated container duration exists.

Processor state is independently `not_run`, `processor_verified` or
`processor_mismatch`. Only the exact recorded local reference tuple is verified;
other runtimes remain candidates. Server parity is always unverified in M1/M2.
The [support matrix](support-matrix.md) and [ADR](decisions/0003-cpu-inspection.md)
state the scope and limitations.

## Persistence, privacy and comparison

An inspection directory contains `inspection.json`, `manifest.json`, `report.html`.
A comparison contains `comparison.json`, `report.html`. Reads/writes are bounded;
complete output is staged before publication. Existing outputs require explicit
`--overwrite`; unknown directory contents and symlinks are not discarded.
`storage.load_result`, `write_inspection_run`, `write_html_report`, and
`compare_runs` are the corresponding base-only APIs.

Results created by inspection use generic image/video display names and omit raw
prompt, filesystem paths, credentials and source media. Hashes can correlate
artifacts and are not anonymization. `--include-media` explicitly retains bounded
thumbnails; default rerender/compare omits them. HTML escapes external text and
redacts paths/sensitive URLs even from imported records. It uses embedded styles
and no remote fonts/scripts/CDNs. The same typed result drives JSON and HTML.

Comparison uses explicit run IDs and a chosen first baseline. Source, modality,
prompt/template, model/revision, adapter, dependencies and artifact identity must
agree before showing deltas. Requested sampling/frame/pixel differences are
intentional; effective grid, dimensions and frame mapping differences are visible.
Runtime/config differences are identified, and unknown or mismatching provenance
is not silently equated. Frame and resize changes together are labeled coupled.
Latency, GPU memory and quality remain null, even when input counts change.
