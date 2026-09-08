# Implementation roadmap

Canonical milestone status, as of 2026-09-08. A passing implementation check is not
owner acceptance. Allowed states: `planned`, `in_progress`,
`implemented_validation_pending`, `blocked`, `ready_for_owner_review`, `accepted`.

| Milestone | Dependency | Status | Gate |
| --- | --- | --- | --- |
| M0 Foundation and feasibility | Local CPU checkout | accepted | Actual checks and owner review |
| M1 Image inspection | Accepted M0 + explicit continuation | ready_for_owner_review | Reference processor counts and offline rerun |
| M2 Video and reports | M1 implementation + authorized M1/M2 batch | ready_for_owner_review | PTS/sampling edges, portable report and visual QA |
| M3 Endpoint protocol | Accepted M2 | planned | Deterministic real HTTP/SSE mock tests |
| M4 Live comparisons | Accepted M3 + owner endpoint/GPU | planned | Actual backend/media parity and controlled evidence |
| M5 Telemetry | Validated backend + real metrics source | planned | Units, scope and real capture |
| M6 Profiling/extensions | Trustworthy workflow and demonstrated need | planned | Versioned real validation and overhead baseline |

No endpoint, GPU access, or GPU budget was supplied. Live hardware gates are
unavailable, not passed; this does not block M0–M2. M3 CPU protocol review can be
accepted separately from live behavior, which remains validation pending until M4.
The next candidate release after M2 is inspection-only 0.1; after M4, endpoint 0.2.
Publication requires separate authorization. See [continuation state](implementation-state.md).

### M0 — Repository foundation, technical spike, and implementation documents

**Goal:** establish a concrete, reviewable contract and a runnable minimal package; do not implement the full inspector yet.

Tasks:

1. Inspect the checkout, existing instructions, Git status/remote/history, local identity, OS/architecture, available Python/uv, and existing dependencies. Preserve the owner's changes. If the repo has evolved, adapt this plan to actual files rather than overwriting them.
2. Work on an `oguzhankir/<kebab-topic>` branch. Start with `oguzhankir/modalmeter-foundation` if it does not already exist; resume the existing task branch when appropriate. Handle an empty repository without inventing a main-branch history or creating meaningless bootstrap commits.
3. Verify the initial model ID, inspect processor configuration/source, resolve a compatible released dependency tuple, and choose the canonical processing/decoder path in an ADR. A small discarded or clearly labeled spike is acceptable; do not claim processor correctness until M1/M2 tests pass.
4. Create the documents in section 3.3 with substantive project-specific content. A planned feature must be labeled planned. Mark untested support-matrix entries as candidates, not supported.
5. Bootstrap the package and CLI with real `--help` and `--version`, typed schema foundations, minimal contributor commands, and CPU CI. No pretend `inspect`, `benchmark`, or `sweep` commands returning hard-coded success.
6. Build a wheel/sdist and prove a clean base installation can invoke help without the optional inspection dependencies.
7. Update the changelog and continuation record with actual commands and outputs.

**Evidence to show:** checked-out branch, relevant environment versions, created files, source-backed ADR choice, CLI help/version output, package build/smoke-test output, and an honest support matrix. Finish M0 and wait for owner verification.

### M1 — Real image inspection and verified token accounting

**Goal:** process one supported image on CPU with real processor evidence and a stable JSON result.

Tasks:

1. Implement artifact resolution by an explicit processor/tokenizer/config/chat-template allowlist at an immutable model revision. Load with remote custom-code execution disabled by default. Keep all weight/model generation APIs out of this path.
2. Implement local image validation, a small configurable resource limit, EXIF orientation/color-mode handling, hashing, and manifest generation. Record transformations. Do not silently apply unrelated image enhancement.
3. Implement the initial model adapter and prompt/template processing with stable typed outputs. Distinguish actual placeholder counts, grid-derived counts, and complete prompt length.
4. Add image inspection CLI/API, atomic JSON writes, offline cache behavior, and actionable missing-extra/unsupported-model errors.
5. Validate against the unmodified pinned reference processor, with fixtures not constructed solely from the implementation's formula.

**Acceptance:** an actual synthetic image and several dimension/aspect-ratio boundary cases produce independently checked counts; invalid/corrupt input fails clearly; no weights are downloaded; no GPU is required; an offline cached rerun succeeds; base help remains lightweight. Provide a real result JSON and the exact reproduction command. `server_parity_unverified` is expected.

### M2 — Video inspection, timeline, and portable report

**Goal:** deliver the first distinctive user workflow: inspect a video and understand the frames/token accounting.

Tasks:

1. Implement deterministic video manifest extraction and the supported sampling modes without hidden double sampling/resizing.
2. Record decoded presentation timestamps separately from any index/FPS-derived processor timestamps and grouped prompt timestamp labels. For VFR, preserve the distinction or explicitly restrict parity claims.
3. Handle temporal padding and requested/effective counts correctly. Bound decoded-frame memory, input size, and inspection workload; do not decode an unbounded long video into a Python list by default. Prefer bounded decode/selection or a documented staged strategy.
4. Implement the offline report and inspection-only comparison. Include optional timestamped thumbnails, clearly labeled unavailable runtime metrics, effective settings, and processor/version provenance.
5. Generate small deterministic video fixtures with known frame IDs, dimensions, duration, and licensing/provenance. Keep private user media outside Git.
6. Add a working CPU quickstart and verify the HTML with actual output.

**Acceptance:** normal short video, odd selected-frame count, very short video, repeated/padded frames, noninteger FPS, VFR/missing metadata, corrupt video, and an overlarge frame request have tested outcomes. Grid/token counts match the reference for supported cases. Stored artifacts rerender without downloading a processor. A new user can complete the CPU quickstart without CUDA/model weights.

This is the candidate **0.1 inspection release**. Prepare release artifacts if requested; do not publish automatically. A CPU-only release may truthfully ship with vLLM server parity pending and with live benchmarking absent.

### M3 — Endpoint benchmark implementation and CPU protocol verification

**Goal:** implement a correct endpoint client independently of whether a GPU is available today.

Tasks:

1. Implement one verified vLLM-compatible streaming chat transport, including explicit model alias versus processor identity.
2. Add a robust SSE parser, monotonic timing, usage accounting, warmup exclusion, timeout/cancellation handling, explicit concurrency cap, and a default no-retry policy.
3. Use a simple closed-loop request-count workload initially. Do not call its concurrency a requests-per-second arrival rate. Defer open-loop traffic generation and distributed load to future integration.
4. Persist every request attempt and its outcome, with redacted metadata. Raw response/output retention is opt-in; normalized timing/usage records are mandatory.
5. Compute aggregate statistics from measured samples, include sample counts, preserve failures, and implement a missing-usage policy.
6. Capability-detect optional server per-request metrics if the pinned deployment supports them; they remain separate from client timings.

**CPU protocol acceptance:** a local deterministic mock SSE server covers role-only/empty events, multiple tokens per chunk, usage-only tail, missing usage, split UTF-8/event boundaries, reasoning before content, one-token/empty output, timeout, cancellation, HTTP failure, midstream disconnect, and optional server metrics present/null. Test actual bounded concurrency and aggregate denominator handling.

Mocks establish parser and measurement arithmetic behavior. They do not establish vLLM correctness, video parity, GPU measurements, or a production speedup. Show mock evidence labeled as such. Without a live endpoint, status is `implemented_validation_pending` for live behavior; the owner may accept CPU implementation review while M4 remains a distinct gate.

### M4 — Live vLLM validation and controlled comparisons

**Goal:** prove one real measured workflow on a recorded backend/model tuple.

Prerequisites: owner-provided endpoint/GPU access, a known serving configuration, approved media, and any necessary existing budget authorization. If absent, finish the local deliverables and provide an exact runbook plus the minimum missing inputs. Never replace this gate with mock data or rent hardware automatically.

Tasks:

1. Record hardware, driver/CUDA where accessible, vLLM version, model and processor revisions, dtype/quantization, parallelism, context/output limits, relevant multimodal settings, caches, pruning, and startup command/config. Unknown settings must remain unknown.
2. Run a real small image request and then a supported video request. Validate usage, content timing, request artifacts, and errors against raw server evidence.
3. Verify video transport and media metadata. For pre-extracted frame transport, account for any JPEG re-encoding by inspecting decoded transmitted pixels, or explicitly record that pixel parity is not established.
4. Establish processor/server parity to the extent the evidence permits. If exact internal metadata is inaccessible, record parity as unverified and offer an explicit opt-in validation harness on the serving host. Do not install a persistent invasive hook merely to obtain a badge.
5. Implement a controlled requested-frame-count comparison only after proving the server honors that control. Keep prompt, output settings, server config, and concurrency fixed, and report actual output lengths. Diff effective resize/grid values too; if the processor changes them as frame count changes, label the coupled effect rather than attributing it solely to frame count.
6. Produce one shareable real comparison and a reproducible experiment recipe. Add a validated command to docs only after executing it.

**Acceptance:** actual request records, durations, usage, effective input differences, version/config provenance, and an HTML comparison exist. Any speedup is derived from the shown baseline and experiment. Do not require an improvement as a passing condition: an honest result showing no improvement can validate the tool. A bad experimental result must not be edited into a successful marketing claim.

This is the candidate **0.2 endpoint measurement release**, subject to release gates and user authorization.

### M5 — Optional server/device telemetry and scoped diagnostics

**Goal:** add useful memory/cache/queue context without false per-request attribution.

Tasks:

- Ingest explicitly configured metrics or a local import; handle missing series, label sets, counter resets, histogram buckets, and server restarts.
- Support capability-detected server per-request metrics as a separate observation source when available.
- Add a serving-host device/process memory collector only when the environment provides one; a client laptop cannot observe a remote GPU through its own NVML instance.
- Keep vLLM KV-cache utilization, device-used bytes, process-used bytes, and allocator allocated/reserved bytes distinct.
- Add a small set of source-backed rules: unsupported/ignored media control, excessive sampled input relative to an explicit budget, observed preemption/cache pressure, incompatible comparisons, and incomplete telemetry. A finding must explain its evidence and suggest a controlled next experiment.

**Acceptance:** unit fixtures plus at least one real telemetry capture establish units/scope. Missing telemetry does not break normal benchmarking. Rules explain the evidence and never fabricate absent metrics. Device sampling reports a sampled maximum and interval, not a guaranteed instantaneous peak.

### M6 — Opt-in stage profiling and broader support

**Goal:** investigate deeper bottlenecks only after the basic measurement workflow is trustworthy.

First validate official vLLM profiling integration points. Design an opt-in experiment that separates host preprocessing, vision encoding, and language-model stages where supported. Record instrumentation overhead with a matching uninstrumented baseline. CUDA execution is asynchronous; Python wall time around a kernel enqueue is not its execution duration. Overlapping stages are not additive shares of end-to-end time.

Keep this an optional, version-gated integration. Prefer trace import or official hooks to monkey-patching engine internals. Do not maintain a vLLM fork just to satisfy an early roadmap promise.

After meaningful evidence and user demand, consider another model adapter, another server backend, GuideLLM result import/integration, richer sweeps, task-specific quality evaluation, or empirically calibrated memory estimates. MCP/agent skills and CI regression comparisons are distribution/workflow extensions after the core API is stable.

**Acceptance:** each extension has its own capability contract, real validation, version support, limits, and maintenance justification. A later phase is not a reason to add generic abstractions now.
