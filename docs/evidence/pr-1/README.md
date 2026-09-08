# PR #1 follow-up evidence

The owner requested a PR to `main` and explicitly prohibited M3 continuation.
[PR #1](https://github.com/oguzhankir/modalmeter/pull/1) contains the foundation,
logo and M1/M2 implementation. No merge or publication is authorized.

The [first pull-request workflow](https://github.com/oguzhankir/modalmeter/actions/runs/34209473811)
failed two help-content assertions on Linux and macOS: ANSI styling interrupted
`--version` in raw terminal output. Reproduction removed the local `NO_COLOR`
setting and forced color. The fix uses Click's public `unstyle` helper for visible
text and adds explicit plain/color cases; the colored case checks that actual
ANSI output was exercised. All existing content assertions remain unchanged.

Actual post-fix local commands:

```bash
env -u NO_COLOR TERM=xterm-256color FORCE_COLOR=1 .venv/bin/python -m pytest -q
env -u NO_COLOR TERM=xterm-256color FORCE_COLOR=1 .venv-py311/bin/python -m pytest -q
.venv/bin/python -m ruff check tests/test_cli.py
.venv/bin/python -m ruff format --check tests/test_cli.py
.venv/bin/python -m mypy tests/test_cli.py
```

Both full default suites passed: **139 passed, 34 deselected**; see
[Python 3.12](pytest-py312.txt) and [Python 3.11](pytest-py311.txt). Scoped CLI tests
passed all 28 cases, with 4 plain/color help cases. Ruff and mypy passed. Two
upstream Typer/Click deprecation warnings remain. Production code, processor
results, and M3 scope are unchanged; the prior processor/package evidence remains
an implementation-handoff record rather than evidence from a rerun in this task.

The corrected revision's hosted lint/type/test/build/package outcomes are tracked
in [PR checks](https://github.com/oguzhankir/modalmeter/pull/1/checks). Check those
statuses directly; the failed initial run above is preserved, not relabeled.
