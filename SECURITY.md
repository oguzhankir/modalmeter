# Security

ModalMeter is pre-release CPU inspection code; no stable security-maintained release
is designated. Never put authorization headers, URL credentials/query tokens,
private endpoint identifiers, private media, raw prompts/outputs, model weights,
or local secrets in Git, public issues, logs or release artifacts.

M1/M2 does not contact an inference endpoint. The inspector verifies a fixed eight-file
processor allowlist at an immutable revision and loads with `trust_remote_code=False`.
It bounds local file/pixel/frame/tensor workloads and rejects invalid metadata.
Decode deadlines are cooperative, not hard interruption of a native codec call;
tensor budgets are preflight allowances, not a process memory sandbox.

Stored reports autoescape external text, redact sensitive fields and omit media by
default. Embedded thumbnails require explicit inclusion. Content hashes can still
correlate runs and are not anonymization. Output writes are bounded and protect
unrelated directories. Use synthetic data when sharing issue evidence. Future
endpoint clients require their own credential, transport and redaction review.

For a nonsensitive reproducible issue, use the repository's
[issue route](https://github.com/oguzhankir/modalmeter/issues) with a synthetic
fixture and redacted versions/error. For a sensitive vulnerability, first request
a private reporting route from the maintainer without revealing exploit details
or affected data in a public issue. A private security advisory route or contact
email has not been verified; this document does not claim one exists. If the
repository's Security tab offers a verified private-report option later, use it
and update this policy. Do not upload confidential material to test a route.
