# Data contract

## Implemented M0 foundation

`EvidenceDocument` is a small standalone record with `schema_version="1.0"`,
`record_kind="evidence"`, and a named `measurements` mapping. It is not an
inspection result. `Measurement` requires a finite strict integer/float or null,
a nonblank unit/source/scope/method, an `EvidenceKind`, and an optional reason.
Booleans and numeric strings are rejected. `unavailable` requires null and a
nonblank reason; all other evidence kinds require a value and prohibit a missing
reason. Extra fields and unsupported versions (including unrecognized minor
versions) are rejected. Version and record kind must be present on input; missing
identity fields are never silently filled in during loading. Model fields are frozen;
nested mappings are not promised
to be deeply immutable. Consumers validate on each load.

The [golden JSON](../tests/fixtures/evidence-v1.json) is synthetic and contains an
unavailable encoder duration, not fabricated inference. The fixture has no media
or third-party content. Read it with `EvidenceDocument.model_validate_json(text)`;
serialize with `model_dump_json()`. No disk-writing or report API exists in M0.

Versions are strings. Future additive minor versions require explicit consumer
support and migration tests. Breaking changes require a new major version;
never relabel old records in place or silently coerce unknown fields away.

## Planned inspection and benchmark records (M1 onward)

Use separate processor verification and server parity fields keyed by modality,
model/revision, dependency tuple, adapter version, and effective configuration.
Before a successful check, processor state is `not_run`; afterwards it may be
`processor_verified` or `processor_mismatch`. Server states are
`server_parity_unverified`, `server_parity_verified`, or `server_parity_mismatch`.
Preserve a mismatch and its evidence; an image result never upgrades video status.
These compatibility models are design commitments, not M0 Python interfaces.

Use SHA-256 over original file bytes for source identity. Display names must be
sanitized basenames, never identities. Frame identity combines source hash,
decoded ordinal, rational PTS/time base, and duplication origin; a selected frame
can have multiple processed positions. Hash transformed/transmitted pixels
separately when their equality matters. Hash prompt/template UTF-8 bytes and
canonical request/config JSON (sorted keys, compact separators, no NaN/Infinity,
UTF-8) with a named canonicalization version. Record the readable config diff,
not just its hash. Run/request IDs are UUIDs and are not content hashes.

A private full request must not be embedded in a sanitized fingerprint artifact.
Sanitized exports omit absolute paths, sensitive URLs, authorization, raw text,
and media by default. Hashes can still correlate artifacts; document that risk.
Media inclusion is explicit opt-in. Unknown server settings remain unknown.

## 5. Data contracts and provenance

Design a small versioned schema before implementation. Keep irrelevant subrecords optional and typed; do not build a universal observability schema.

Minimum inspection fields:

- Schema version, tool version/commit when available, run ID, creation time, run kind and completion status.
- Input kind, media hash, sanitized display name, source dimensions/duration, metadata reliability, privacy mode.
- Requested/effective sampling policy; requested/selected/processed frame counts; selected timestamps and duplication/padding mapping.
- Processor model ID, immutable revision, adapter version, Transformers/helper/decoder versions, resolved processor settings.
- Media-specific grid outputs and visual-token accounting with units, evidence type, and derivation reference.
- Prompt/template identity or hash, complete non-padding processed prompt length if available, and whether raw prompt text is retained.
- Processing durations if actually measured, hardware/runtime description limited to what is relevant, and clear warnings.
- Compatibility level and the exact evidence establishing it.

Minimum benchmark additions:

- Endpoint transport and sanitized identifier; model alias and actual engine/model revisions only if known.
- Requested/effective generation configuration, text prompt identity, media hash, request-shape hash, run order, cache/warmup policy, concurrency and load mode.
- One record for every attempted request: request ID, warmup/measured classification, queue-to-dispatch time when applicable, timings, usage, stop reason, HTTP/stream errors, completion status.
- Sample counts for every statistic; success/error counts; declared denominator for throughput; explicit warmup exclusion.
- Server/per-request/device metrics with exact source, labels, time window, scope, sampling interval, reset/missing-data handling, and attribution limitations.
- Environment/config fingerprint plus an `unknown` state for inaccessible server settings.

A small measurement record may use `value`, `unit`, `evidence_kind`, `source`, `scope`, `method`, and `unavailable_reason`. Do not burden every static string with the same wrapper. Standardize bytes for stored memory; render MiB/GiB with correct binary conversion. Use one stored duration unit consistently and document display conversion.

Use `null` with an explanation for unavailable metrics. Separate zero from missing. Define schema migration policy: a consumer must reject unsupported major schema versions cleanly; older valid records should not be silently interpreted as a newer schema. Keep tiny curated golden schema examples, not giant serialized tensor fixtures.

Comparison should report a compatible baseline, intentionally changed fields, unknown environment fields, and potentially confounding differences. A hash alone is not an explanation: show a readable configuration diff. Never silently pair unrelated requests by list position.
