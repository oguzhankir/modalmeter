# Releasing

M0 is a local development foundation (`0.0.0.dev0`), not a public inspection
release. A release candidate must contain only implemented, verified commands.
M2 is the earliest inspection-only candidate; live benchmarking need not block it.
No publishing workflow or credentials are configured in M0.

1. Review the canonical roadmap, support tuples, changelog and owner acceptance.
2. Check the actual PyPI `modalmeter` project and PEP 503 normalized name before
   publication. Normalize by lowercasing and replacing runs of `-`, `_`, `.` with
   `-`; `modalmeter` normalizes to itself. A GitHub repository does not reserve it.
   A 404 is only a point-in-time observation, not a reservation or guaranteed
   publish permission. Name availability was not checked for M0 publication,
   because publication is not being prepared. Never silently rename on conflict.
3. Use `uv build --no-sources`, then the clean wheel/sdist smoke command in
   [AGENTS.md](../AGENTS.md#developer-commands). Install both independently and run
   every advertised quickstart. Verify package metadata, license, `py.typed`,
   templates/package data when present and supported Python versions.
4. Inspect archive members for secrets, private media, caches, weights, traces and
   large output. Review dependency/model/media license attribution separately.
   The existing project license is MIT; do not replace it with the new-project default.
5. Present actual evidence and skipped checks before requesting any remaining
   publication authorization. Prefer owner-configured trusted publishing and a
   manually gated workflow; never auto-publish on every push.

Tags, GitHub releases, pushes and package publication all require corresponding
authorization. Do not run `uv publish`, push a tag, change visibility, or imply the
package is on PyPI as part of a local build. Preserve existing cryptographic Git
signing settings; DCO `git commit -s` is a distinct requirement.
