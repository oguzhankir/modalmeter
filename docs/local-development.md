# Local development

Observed 2026-09-08: macOS 26.6.2 (25G83), ARM64, Git 2.50.1 (Apple Git-155),
Initially uv was 0.11.7 and the shell's `/opt/miniconda3/bin/python3` was
Python 3.12.12 x86_64. During M0 those initial tool paths disappeared and global
uv became Homebrew 0.12.10. M0 did not modify global Python/uv/Git configuration.
Final validation uses native Homebrew Python 3.12.11 and an isolated native
Python 3.11.15; the system's universal Python 3.11.5 produced mixed-architecture
wheel failures and is not the verified contributor path.

Verified local base setup:

```bash
cd /Users/oguz/Desktop/modalmeter
export PATH="/private/tmp/modalmeter-uv-tool/bin:$PATH"
export UV_CACHE_DIR=/private/tmp/modalmeter-uv-cache
uv sync --locked --python /opt/homebrew/bin/python3.12
uv run --locked modalmeter --help
uv run --locked modalmeter --version
```

The isolated uv tool was created without changing the global installation:

```bash
cd /private/tmp
/opt/homebrew/bin/uv venv --python /opt/homebrew/bin/python3.12 /private/tmp/modalmeter-uv-tool
/opt/homebrew/bin/uv pip install --python /private/tmp/modalmeter-uv-tool/bin/python uv==0.11.7
```

Return to the checkout after setup. This temporary tool and cache can be removed
by the OS; recreate them when necessary. The project explicitly requires uv
0.11.7–0.11.x; global 0.12.10 intentionally fails that version gate.

The explicit cache avoids the current agent sandbox's blocked default uv cache.
It is temporary and may be deleted by the OS; this is not a project dependency.
First sync/build needs ordinary package downloads. Use [AGENTS.md](../AGENTS.md#developer-commands)
for the canonical lint/type/test/build commands.

The secondary base test environment uses a managed native interpreter installed
only under the temporary task directory (no global binary links):

```bash
UV_PYTHON_INSTALL_DIR=/private/tmp/modalmeter-python uv python install 3.11.15 --no-bin
```

Then:

```bash
UV_PYTHON=/private/tmp/modalmeter-python/cpython-3.11.15-macos-aarch64-none/bin/python3.11 UV_PROJECT_ENVIRONMENT=.venv-py311 uv sync --locked
UV_PYTHON=/private/tmp/modalmeter-python/cpython-3.11.15-macos-aarch64-none/bin/python3.11 UV_PROJECT_ENVIRONMENT=.venv-py311 uv run --locked pytest
```

Set `UV_PYTHON` for every secondary-environment command: `UV_PROJECT_ENVIRONMENT`
alone does not override `.python-version`. An initial 3.11 validation attempt
reselected the default Intel 3.12 and failed a sandboxed download; this was corrected
by explicitly setting the interpreter. Mixed-architecture wheels with the
universal interpreter subsequently required a fresh managed ARM64 environment.
See the preserved failure logs and final successful checks.

The M0 feasibility environment is deliberately separate from `.venv`:

```bash
UV_PROJECT_ENVIRONMENT=.venv-spike uv sync --locked --extra inspect --python /opt/homebrew/bin/python3.12
```

This installs Torch/torchvision, Transformers, Pillow and PyAV. The Torch wheel
alone was about 71 MiB compressed and PyAV about 20.5 MiB, excluding transitive
packages. PyAV bundles FFmpeg libraries on this tested wheel; it does not promise
a shell `ffmpeg` executable. The probe uses the PyAV API, no executable. uv selects
CPU Torch wheels on Linux via an explicit index; plain pip does not inherit that
uv setting. See the ADR before installing the extra on another platform.

Reproduce the [probe](evidence/m0/README.md) only with its listed small immutable
artifacts. There is no M0 media inspection command. Initial download access and
Git metadata writes required sandbox escalation; authorized local work proceeded
without changing global configuration or publishing anything.
