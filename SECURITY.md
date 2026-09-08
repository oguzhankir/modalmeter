# Security

ModalMeter is pre-release foundation code; no stable security-maintained release
is designated. Never put authorization headers, URL credentials/query tokens,
private endpoint identifiers, private media, raw prompts/outputs, model weights,
or local secrets in Git, public issues, logs or release artifacts.

M0 does not contact an inference endpoint. The feasibility probe uses a reviewed
processor-only artifact allowlist, immutable revision, local-only load, and
`trust_remote_code=False`. Future inspectors must bound file/pixel/frame/tensor
work and use local inputs. Future clients and reports must redact sensitive fields,
escape external HTML text, and make media inclusion explicit. Those future
safeguards are implementation gates, not existing features.

For a nonsensitive reproducible issue, use the repository's
[issue route](https://github.com/oguzhankir/modalmeter/issues) with a synthetic
fixture and redacted versions/error. For a sensitive vulnerability, first request
a private reporting route from the maintainer without revealing exploit details
or affected data in a public issue. A private security advisory route or contact
email has not been verified; this document does not claim one exists. If the
repository's Security tab offers a verified private-report option later, use it
and update this policy. Do not upload confidential material to test a route.
