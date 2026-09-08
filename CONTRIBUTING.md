# Contributing

Read [AGENTS.md](AGENTS.md), the [vision](docs/vision.md),
[measurement contract](docs/measurement-contract.md), and current
[implementation state](docs/implementation-state.md) before changing behavior.
Use English for code, comments, docs, errors and commits; discuss milestone review
with the maintainer in Turkish. Work one authorized milestone at a time.

Use Python 3.11/3.12 and uv 0.11.7. [AGENTS.md](AGENTS.md#developer-commands) holds
the canonical command table. [Local development](docs/local-development.md) records
the actual Mac interpreter and environment setup. Keep `uv.lock` in review when
dependencies change; do not silently introduce Git-main dependencies. The base
environment is enough for M0. Inspect-extra downloads are explicit and separate.

[Testing](docs/testing.md) explains what offline, processor, protocol and live tests
prove. Never download model artifacts from a default unit test. A new adapter must
have a source-backed capability contract, a pinned model/dependency tuple, independent
processor comparisons and modality-specific status. Server transport and model
processing are separate adapters; mocked endpoints cannot establish parity.

Use `oguzhankir/<kebab-topic>` feature branches and preserve unrelated changes.
Review the diff, run relevant checks, update CHANGELOG and implementation-state,
then stage only task files. Include the concrete problem, result, evidence and
limits in a PR. Do not push, publish, or change visibility without authorization.
Owner verification is a gate, not something inferred from passing tests.

Contributions require the [Developer Certificate of Origin 1.1](https://developercertificate.org/).
Use your already configured real identity and `git commit -s` to certify your right
to contribute. DCO sign-off is separate from cryptographic signing. Do not invent
an email or change global configuration to get past a missing identity. Preserve
license and media attribution; synthetic fixtures must describe their origin.
