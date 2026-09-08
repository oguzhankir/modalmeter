# ModalMeter — Local Coding Agent Implementation Instructions

Document date: 2026-09-08  
Repository: https://github.com/oguzhankir/modalmeter  
Project name: **ModalMeter**  
Python distribution, import package, and CLI target name: **`modalmeter`**  
Status: implementation specification; examples below describe intended interfaces, not an existing released package.

## 0. Your assignment and execution contract

You are the implementation agent working in the user's local checkout. Build ModalMeter as a maintainable open-source Python library and CLI. Establish its product vision, technical contracts, repository documentation, contributor instructions, implementation roadmap, tests, and release process, then implement it in verified milestones.

Do the work. Do not respond with only a plan or ask the user to implement the proposed files. Do not build the entire roadmap in one unreviewed pass.

**Default execution mode: one milestone per user verification.** Complete the current milestone, show actual evidence, update the continuation record, and wait for the user's verification before advancing. The first run executes **M0 only**. After the user says to continue, resume the next ready milestone. Within a milestone, perform routine reads, edits, dependency setup, and relevant tests autonomously. Ask only about a genuine blocker or a decision the user must make. If the user later explicitly authorizes several milestones in one pass, respect that authorization while recording the evidence for each milestone.

Use Turkish for conversation with the maintainer. Use English for all code, identifiers, comments, documentation, error messages, CLI output, issue/PR text, and commit messages.

This document is a specification, not a claim that the chosen libraries or APIs currently behave in a particular way. Re-read official upstream documentation and source at the versions you actually install. Resolve contradictions using executable evidence and record the resolution in an ADR. Never silently weaken an acceptance criterion to obtain a green status.

### 0.1 Owner-supplied inputs and defaults

The owner can paste the following at the start. Missing optional inputs must not block M0 or CPU-only milestones.

```yaml
repository_url: https://github.com/oguzhankir/modalmeter
local_repo_path: "<absolute local checkout path, or use the current repo>"
execution_mode: milestone_review
target_milestone: M0
sample_media_path: null
sample_media_publishable: false
preferred_initial_model: Qwen/Qwen3-VL-2B-Instruct
vllm_base_url: null
vllm_metrics_url: null
vllm_api_key_env: MODALMETER_API_KEY
gpu_access: none
gpu_budget: 0
git_push_authorized: false
package_publish_authorized: false
```

The model identifier is a starting choice to verify, not permission to silently substitute a different checkpoint. Resolve and record its exact revision before processor integration. If the identifier is unavailable, gated, or unsupported by a compatible released dependency set, explain the specific conflict and recommend the smallest appropriate Qwen3-VL alternative. Do not download model weights during CPU inspection.

Required initially: a writable checkout, local command execution, and access to ordinary dependency/source downloads. Discover the OS, CPU architecture, Python, uv, and Git yourself. Do not ask the owner for versions you can inspect. A real video is optional: create small deterministic synthetic fixtures if none is supplied.

Later, for live validation, request an existing compatible vLLM endpoint or an owner-provided GPU environment and its startup configuration. Request the variable name containing a credential, never that the owner paste a secret into a chat or tracked file. Do not provision paid hardware, expose a service publicly, upload private videos to a third party, publish packages, change repo visibility, or push without corresponding authorization.

## 1. Product charter

### 1.1 Promise

**Profile multimodal inference. Understand visual tokens, latency, and GPU memory.**

ModalMeter helps an engineer inspect what a vision-language model receives and measure how input preparation and serving configuration affect an actual workload. Its initial audience is engineers serving Qwen-family VLMs with vLLM, especially image and short-video applications.

The concrete workflow is:

1. Inspect a local image or video using a supported model's real processing path.
2. See the selected frames, timestamps, transformed dimensions, and clearly defined token accounting.
3. Run a controlled request against an existing serving endpoint.
4. Compare frame, resolution, and workload variants with the original configuration preserved.
5. Share an offline report with reproducible settings and evidence labels.

### 1.2 Initial scope and differentiation hypothesis

The hypothesis is that connecting **media selection and preprocessing** to **observed serving cost** provides a useful workflow beyond a token calculator, generic benchmark runner, or metrics dashboard. Validate this hypothesis with working examples and external users; do not present market uniqueness or GitHub popularity as established facts.

Inspect current primary sources for related tools and document overlap fairly:

- GuideLLM provides endpoint benchmarking, including multimodal workloads. Reuse or import its outputs later where appropriate; do not rebuild its complete load-testing framework.
- vLLM Doctor diagnoses server symptoms using metrics. ModalMeter's initial focus is individual media inputs and controlled comparisons.
- AIConfigurator explores serving configurations using performance models. ModalMeter does not initially attempt universal GPU configuration prediction.
- Native vLLM benchmarking and profiling already exist. Prefer official integration points over copied internals or a private engine fork.

### 1.3 Non-goals for the first public release

- Universal VLM support or a generic agent framework.
- Automatic production tuning, Kubernetes operators, model hosting, auth, billing, or a cloud dashboard.
- A new video understanding model or a summarization-quality benchmark.
- Exact OOM prediction or a universal safe-concurrency number from model configuration alone.
- Unmeasured percentage speedups, automatically inferred answer quality, or per-request GPU memory attribution from server-wide memory readings.
- An LLM-generated diagnostic narrative as the core product. Initial findings must come from explicit rules and evidence.
- A mandatory vLLM/CUDA installation on the user's laptop.
- MCP, coding-agent skills, SGLang, cloud GPU price comparison, or Rust acceleration in the MVP.

### 1.4 Success criteria

The first useful CPU release must let a new user inspect a supported image/video, understand the processing decisions, and open an offline report without model weights or a GPU. CPU-only does not mean dependency-free: disclose any PyTorch and video-library installation costs.

The next release must compare measured endpoint behavior while preserving the exact request and environmental context. A compelling demo is one reproducible case in which the report exposes a meaningful frame/token/latency trade-off. Label synthetic fixtures and simulated outputs. Never invent benchmark numbers to improve a demo.

## 2. Evidence and measurement rules — non-negotiable

### 2.1 Evidence types and compatibility status

Represent the following separately in JSON and in the UI:

| Evidence kind | Meaning |
| --- | --- |
| `observed` | Read directly from a source artifact, processor output, server response, or telemetry source. |
| `measured` | Collected by a defined measurement procedure, with units, clock/source, and scope. |
| `derived` | Computed from identified observations using a documented formula. |
| `estimated` | Model-based approximation with assumptions and a stated validity domain. |
| `unavailable` | Not captured or not supported; record a reason. Never substitute zero. |

Processor compatibility is another dimension. Record processor verification separately from server parity. Use states equivalent to `processor_verified`, `server_parity_unverified`, `server_parity_verified`, and `server_parity_mismatch`, including the tested version tuple and media modality. A failed comparison must preserve the observed disagreement; it is not merely unverified. A server mismatch does not erase a valid CPU processor check. A passing image parity test does not establish video parity. A passing test for one checkpoint/version/configuration does not establish support for the whole family.

Every recommendation must have a stable rule identifier, observed evidence, preconditions, a proposed experiment, and a limitation. Rules should recommend testing a change, not promise a percentage improvement. Do not render heuristic confidence values as calibrated probabilities.

### 2.2 Token accounting

Never expose one ambiguous field named only `tokens`. Distinguish, where available:

- Text/chat-template/structural token positions.
- Vision encoder patch/grid positions before spatial merging.
- Visual embedding placeholder positions consumed by the language model after processing/merging.
- Video timestamp and frame-boundary tokens.
- The complete non-padding processed prompt length, using the attention mask when present rather than padded tensor width.
- Server-reported prompt and completion usage.
- Differences caused by pruning, alternate processor settings, or an unverified transport path.

For initial Qwen3-VL support, inspect the real `image_grid_thw` / `video_grid_thw`, processor configuration, and produced input IDs. A formula derived from grid dimensions and merge size is useful only when validated against the real pinned processor output. Count exact known token IDs/positions, not string occurrences of placeholder text. Report boundary/timestamp overhead separately when the adapter can prove its accounting. Unsupported accounting must remain unavailable or explicitly partial.

Do not assume a fixed visual-token count per frame, use one patch formula for all model families, or silently confuse pre-merge vision positions with decoder sequence positions. The nonvisual prompt residual includes template/timestamp/structural overhead and must not be labeled user-text tokens. A purely analytical formula must never be labeled a runtime measurement.

### 2.3 Video handling and CPU/server parity

Keep a reproducible media manifest containing source content hash, source metadata, selected frame identities, actual presentation timestamps, sampling policy, transformed dimensions, and temporal padding/duplication decisions. Support variable-frame-rate and nonzero timestamp origins deliberately. If the source frame count is not reliable, say so instead of treating container metadata as decoded truth.

Avoid a hidden second sampling step. Verify whether the selected upstream processor accepts raw video, pre-sampled frames, and explicit video metadata. In a pre-sampled path, use the upstream mechanism that actually disables additional sampling. Record the decoder and all relevant dependency versions. Never assume that a Python list of frames is interpreted as a video by every API.

Initially provide two explicit modes:

- `model-default`: use the pinned model processing path's documented default policy, with all effective settings reported.
- `uniform`: select a requested frame budget using a specified deterministic timestamp policy and give those selections to a verified supported processor path. Report requested versus actual selected/processed counts.

Choose whether the implementation uses a helper such as qwen-vl-utils or the native Transformers video processor after a source-backed spike. Establish one authoritative path in an ADR. Do not chain two independently sampling/resizing implementations and call the result canonical.

Some vLLM adapters construct model-specific prompts and video timestamps themselves. They can also prune visual embeddings. Therefore, local Hugging Face processing is not automatically proof of vLLM processing parity.

Define the live transport in a separate adapter. Verify the actual server payload format for the pinned release. If sending the original encoded video lets the server choose different frames, report that path as unverified and do not advertise a controlled frame-count experiment. Do not substitute multiple independent images for a video and describe the two workloads as equivalent. Full parity requires evidence about the selected/processed media and token semantics, not merely equal aggregate prompt lengths.

### 2.4 Latency, throughput, memory, and quality

- Use a monotonic high-resolution client clock for durations; wall-clock time is for run identification.
- Define time to first content from the start of the HTTP operation to the first qualifying generated content event. Separate media decoding, preprocessing, payload encoding, and total workflow time.
- Role-only events, empty deltas, and metadata events are not generated content. Preserve reasoning and answer content distinctions when present.
- Streaming chunks are not necessarily tokens. Stream chunk gaps are not true token-level ITL. A chunk can contain multiple tokens.
- Use server-reported usage where available. A local tokenizer fallback must be separately labeled and record the tokenizer revision; never estimate token count from characters and present it as exact.
- Endpoint timings cannot by themselves separate vision encoder, queue, prefill, and decode execution time.
- Server memory metrics are scoped to a device/process/worker and interval. They are not automatically the memory used by one request. Sampling can miss a peak.
- KV-cache pressure can cause queuing/preemption/recomputation instead of immediate OOM. Concurrency, scheduler limits, context/output lengths, and latency objectives must be part of a capacity claim.
- Reducing frames or resolution can remove information. Show the trade-off; make no automatic quality-preservation claim without a relevant task-level evaluation.

## 3. Architecture and repository structure

### 3.1 Stack decisions

Use Python with a `src/` layout, `pyproject.toml`, uv for reproducible contributor environments, a committed `uv.lock`, pytest, Ruff, and a type checker. Start with Python 3.11 and 3.12 as the tested target range unless the dependency spike provides a concrete reason to change it. Pick and document one build backend and one type checker; Hatchling and mypy are reasonable defaults.

Use Typer for CLI parsing, Rich for human terminal output, Pydantic for typed/versioned data contracts, and HTTPX for the later async endpoint client. Use escaped HTML templates, such as Jinja2 with autoescaping, for offline reports. Keep these dependencies purposeful. Do not introduce a web backend, React application, database, job queue, or plugin framework for a local report generator.

Isolate heavy dependencies behind extras and lazy imports. A suggested boundary is `modalmeter[inspect]` for Transformers, a CPU-compatible tensor backend, Pillow, and the selected video decoder. The base package must support `--help`, `--version`, reading existing result JSON, and rendering existing reports without importing vLLM/CUDA or downloading a model. Test that boundary in a clean environment. Do not claim zero PyTorch dependency for the inspect extra unless the real processor path proves it.

Initially use a decoder with supported wheels on macOS and Linux, such as PyAV, if it satisfies upstream timestamp requirements. Do not force a CUDA-based decoder onto the CPU workflow. Record any FFmpeg executable requirement explicitly; do not assume a PyAV installation also installs a shell `ffmpeg` binary.

Dependency versions must be selected by the implementation spike. Use a compatible released combination, exact revisions for reproducible experiments, and deliberate published dependency bounds. Do not use unpinned Git main dependencies to make tests pass silently. If an unreleased fix is essential, stop calling the release-ready path stable and document the blocker.

### 3.2 Boundaries

| Area | Responsibility |
| --- | --- |
| `schemas` | Versioned input, inspection, measurement, comparison, and provenance records. |
| `media` | Local file validation, metadata, hashing, decoding, sampling, thumbnails. |
| `adapters` | Model-specific processing and separately defined backend request capabilities. |
| `inspect` | Coordinate media manifest and processor evidence without loading model weights. |
| `benchmark` | HTTP streaming, workload control, timing, usage accounting, run persistence. |
| `telemetry` | Optional server/per-request/device observations with explicit scope. |
| `analysis` | Derived metrics, comparability checks, evidence-based rules. |
| `report` | Deterministic JSON export and portable HTML rendering. |
| `cli` | Thin argument parsing and presentation around the Python API. |

Represent these as simple modules first. Split packages when real code warrants it. Do not create dozens of empty files or pretend deferred modules are implemented.

The processor adapter should expose capabilities, load the allowed processor/config artifacts, process a known media manifest, and return evidence plus effective configuration. The server adapter should state its supported modalities, accepted media transport, streaming/usage capabilities, and parity status. Keep these adapters separate so a model family does not become inseparable from one server engine.

### 3.3 Required repository files

Create documentation in M0; create implementation files only as their milestones require them.

| File/path | Required contents |
| --- | --- |
| `README.md` | Honest status, concrete problem, implemented quickstart only, current support, offline demo link/artifact instructions, limits, roadmap links. |
| `AGENTS.md` | Project-specific operating contract based on section 10. |
| `CONTRIBUTING.md` | Environment setup, relevant test groups, adapters, DCO, branch/PR workflow. |
| `CHANGELOG.md` | `Unreleased` with actual changes only; update every milestone. |
| `LICENSE` | Apache-2.0 by default for a new project, unless the owner or existing repo says otherwise; preserve dependency/media licenses. |
| `SECURITY.md` | Secret/report handling and supported reporting route; do not invent a contact email or claim private reporting is enabled without verification. |
| `.gitignore` | Environments, secrets, model caches, private media, reports, transient runs, build artifacts; retain curated fixtures deliberately. |
| `.env.example` | Names and harmless placeholders only; no real tokens or endpoints. |
| `docs/vision.md` | Target users, promise, use cases, non-goals, differentiation hypothesis. |
| `docs/architecture.md` | Boundaries, data flow, import/dependency boundaries, extension strategy. |
| `docs/roadmap.md` | Milestones, dependencies, acceptance gates, actual status, blocked hardware checks. |
| `docs/measurement-contract.md` | Exact definitions, evidence, clocks, scope, missing-value behavior, caveats. |
| `docs/data-contract.md` | Versioned schemas, examples, units, hash/identity rules, privacy and compatibility. |
| `docs/support-matrix.md` | Tested model revision/dependency/backend/OS tuples and modality-specific verification levels. |
| `docs/research.md` | Primary sources, checked dates/revisions, findings, competitive overlap and unresolved questions. |
| `docs/testing.md` | Offline/unit/processor/live-GPU groups and what each actually establishes. |
| `docs/local-development.md` | Exact verified setup and first commands for the owner's environment. |
| `docs/benchmarking.md` | Implemented methodology, warmup/cache policy, transport, throughput and latency semantics. Initially mark future sections planned. |
| `docs/releasing.md` | Build verification, package-name checks, release gates, explicit publication authorization. |
| `docs/decisions/` | Short ADRs with context, evidence, decision, consequences, verification. |
| `docs/implementation-state.md` | Current milestone, changes, commands/results, blockers, user verification status, exact next action. |
| `docs/implementation-instructions.md` | Preserve this specification or an explicitly linked copy as the implementation contract. |
| `examples/` | Runnable examples added with the feature they exercise; synthetic/publicly licensed media provenance. |
| `tests/` | Behavioral tests and small deterministic fixtures. |
| `.github/workflows/ci.yml` | Minimal-permission CPU checks, packaging tests, optional explicit integration jobs. |
| `.github/ISSUE_TEMPLATE/` | Focused bug report and adapter/support request, including versions and redacted evidence. |
| `.github/pull_request_template.md` | Problem, change, evidence, limits, DCO checklist. |

Use Markdown and compact Mermaid where useful; do not spend the first milestones building a documentation website. Avoid duplicating the same status table across files. Link to the canonical contract instead.

## 4. Public interfaces to implement incrementally

These examples are target syntax. Verify flag naming against the actual implementation. README commands must work at the milestone at which they are advertised.

### 4.1 Inspect

```bash
uv run modalmeter inspect ./sample.jpg \
  --model Qwen/Qwen3-VL-2B-Instruct \
  --output ./runs/image-inspect

uv run modalmeter inspect ./sample.mp4 \
  --model Qwen/Qwen3-VL-2B-Instruct \
  --sampling uniform \
  --frames 16 \
  --output ./runs/video-inspect
```

Allow a model revision and a prompt supplied via `--prompt-file` without requiring shell quoting of large text. Support model-default sampling without `--frames`. Reject ambiguous combinations, such as model-default plus an incompatible explicit frame policy. Give clear errors for an unsupported adapter rather than calculating a generic answer.

An inspection run directory should contain machine-readable `manifest.json` and `inspection.json`, an HTML report when implemented, and optionally bounded thumbnails. Write files atomically. Refuse accidental overwrites unless an explicit overwrite flag is used. Support reading an existing cached processor in offline mode. Do not download all files in a model repository merely to obtain its processor.

### 4.2 Report and comparison

```bash
uv run modalmeter report ./runs/video-inspect --output ./report.html

uv run modalmeter compare \
  ./runs/frames-8 ./runs/frames-16 \
  --output ./comparison
```

Comparison must validate schema versions and identify controlled versus uncontrolled differences. An inspection-only comparison may compare input facts and derived token counts; latency and memory remain unavailable. Do not require a model download just to render stored results.

### 4.3 Endpoint benchmark, later milestone

```bash
uv run modalmeter benchmark ./sample.mp4 \
  --model Qwen/Qwen3-VL-2B-Instruct \
  --base-url http://localhost:8000/v1 \
  --warmup 2 \
  --requests 10 \
  --concurrency 1 \
  --max-output-tokens 128 \
  --output ./runs/baseline
```

The endpoint may serve an alias; support explicit separation between server model name and local processor identity. Cap output length and use deterministic generation settings where supported. Report requested and effective settings. Do not imply identical output lengths just because the maximum is identical.

Require `n=1` in the initial endpoint adapter and reject multi-completion requests. Request streaming usage where supported, with `stream_options.include_usage=true`. Multiple completion sequences require a separate timing/usage contract and are outside the initial benchmark scope.

The example repetition counts above are ergonomic defaults for a quick check, not a statistically sufficient benchmark prescription. Allow larger explicitly configured runs and display actual sample counts.

### 4.4 Controlled sweep, later milestone

```bash
uv run modalmeter sweep ./sample.mp4 \
  --model Qwen/Qwen3-VL-2B-Instruct \
  --base-url http://localhost:8000/v1 \
  --frames 8,16,32 \
  --concurrency 1,2 \
  --output ./runs/sweep
```

Only expose frame controls for a backend/model tuple that demonstrably honors them. The primary first experiment changes one factor at a time with concurrency fixed. Multi-axis sweeps are later. Persist every attempted variant, including failures, and make a partially completed run resumable without silently mixing environments.

Distinguish one requested control from one effective factor: a model's total-video pixel budget can make a frame-count change also change per-frame resize. Compare actual selected frames, processed dimensions, grids, and tokens for every variant. Claim an isolated frame-count effect only if the per-frame transform is verified fixed; otherwise label the result a coupled frame/resize experiment.

### 4.5 Python API and CLI behavior

Provide a small typed Python API such as `inspect_media(config)`, `render_report(result)`, `compare_runs(paths)`, and later `benchmark(config)`. Avoid global mutable state. CLI and API must call the same core functions.

Use consistent exit codes: `0` for success, `2` for invalid arguments/unsupported input, `1` for execution failure, and `130` for a handled user interruption when the platform permits. A detected performance warning is data, not automatically a process error. For a partly failed benchmark, produce the evidence artifact and return a documented nonzero status. Machine-readable stdout must contain only JSON when requested; send logs/progress to stderr. No NaN or Infinity in JSON.

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

## 6. HTML report requirements

Create a self-contained, offline report with embedded styles and no third-party tracking, fonts, scripts, or CDN requirement. Use responsive HTML, readable typography, accessible contrast, and concise labels. Interactivity is optional and should be minimal: sortable comparisons, expanding evidence, or switching raw/derived views is enough.

An inspection report should include:

1. A top summary with model, modality, evidence level, selected/processed frame count, and clearly named visual-token count.
2. A timeline/contact sheet displaying frame timestamps, requested sampling, and padding/duplication indicators. Respect image aspect ratios; do not imply exact framing through distorted thumbnails.
3. Original versus processed dimensions and token accounting with definitions.
4. Effective settings, version tuple, processing provenance, and limitations.
5. Reproduction instructions that work for local mode; a sanitized shareable mode must explain which local paths/configuration the recipient must supply.

A benchmark report adds measured latency distributions, sample counts, failures, output-length information, throughput definitions, and any telemetry scope. A comparison report adds a configuration diff and observed deltas. An unavailable encoder measurement must remain visibly unavailable; do not infer it from TTFT.

Private media must stay out of tracked examples and release artifacts. Offer an explicit media-inclusion option for shareable reports; sanitized reports omit thumbnails, raw prompt/output text, absolute paths, credentials, and sensitive URLs by default. A local report may include thumbnails when explicitly requested. Escape filenames, prompts, server errors, and all external text to prevent HTML/script injection.

Render JSON and HTML from the same typed result. Verify a real report visually at a desktop width and a narrow width when browser/screenshot tooling is available. Inspect long names, no-video/image-only output, missing metrics, and failed requests. Do not mark visual QA passed if you could not open the result; report the limitation and provide the file for review.

## 7. Milestone roadmap and acceptance gates

Use the statuses `planned`, `in_progress`, `implemented_validation_pending`, `blocked`, `ready_for_owner_review`, and `accepted`. `accepted` means the implementation evidence exists and the owner has verified the milestone. Do not equate written code with verified behavior.

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

## 8. Benchmark methodology details

### 8.1 Required timing definitions

Define client request start as the timestamp immediately before invoking HTTPX `stream`/`send`, after acquiring the application concurrency limiter. This boundary includes connection-pool waiting, DNS/connection setup when needed, and payload upload; it is not an observed network-wire dispatch time. Distinguish it from separately instrumented transport events if those are added later. Store raw relative monotonic timestamps sufficient to derive and audit:

| Metric | Definition |
| --- | --- |
| `client_queue_ms` | Request eligible to send to client request start after the application limiter. |
| `time_to_first_output_ms` | Client request start to first nonempty supported generation delta; record channel. |
| `time_to_first_content_ms` | Client request start to first nonempty user-visible text content delta. |
| `e2e_client_ms` | Client request start to valid protocol completion. |
| `stream_chunk_gaps_ms` | Gaps between qualifying generated deltas; not token-level ITL. |
| `workflow_ms` | Explicit outer boundary including preparation when measured. |

Also record response-header arrival, last generated output, usage arrival, and protocol completion when available. An EOF without the expected valid completion is a failed/incomplete request, not a successful short response.

If adding amortized client TPOT, document the exact interval and whether response-tail overhead is included; require a corresponding authoritative output count greater than one. Otherwise return unavailable. Do not mix reasoning and content-only time boundaries with an output count covering both channels.

Use one whole-run measurement window from the first measured client request start to the last measured request terminal event, including failure/timeout waiting time. Exclude warmup requests from aggregates. Report successful requests per second over that window. Full-run output-token throughput requires authoritative usage for every successful request; otherwise report it as unavailable or explicitly partial with coverage. Do not average individual request token rates and call the result system throughput.

### 8.2 Cache and load controls

Default to `cache_policy=as_configured`. Record which settings are observed, owner-supplied, or unknown. Distinguish startup/compilation coldness, request-cache coldness, and a warmed repeated prompt/media workload.

Identical warmup requests can prime prefix and multimodal caches. Randomizing text does not prove media caches are cold. Never silently reset caches or change a serving process. Dedicated controlled-server recipes may disable/reconfigure reuse only when explicitly authorized for that experiment.

Use a recorded scenario-order seed where interleaving is appropriate; avoid comparing all baseline requests during one load condition against all candidate requests during another without noting the confounder. Record background-load uncertainty, connection reuse, request payload sizes, and client location as relevant. If two requested frame/pixel settings resolve to the same effective processor input, explain that they are not distinct experiments.

Small runs should show raw samples and robust summaries. Do not advertise reliable tail percentiles from a handful of requests. Document the percentile estimator and sample count whenever percentiles are shown. Statistical intervals, if added, must identify the method and remain conditional on the experimental design.

### 8.3 Optional current vLLM capabilities

Primary-source checks at the date of this instruction found an optional per-request-metrics feature and pre-extracted video-frame transport. Verify these in the release actually used; do not require current `main` behavior.

For compatible deployments, `--enable-per-request-metrics` can expose a server `metrics` record, including timing/queue fields. Streaming retrieval depends on final usage reporting. Preserve raw server names and their documented timing boundaries under `server_request_metrics`; these do not replace client observations or supply a complete vision-stage breakdown. Treat null/absent records as unavailable. Collecting them may add overhead. [Official per-request metrics](https://docs.vllm.ai/en/stable/features/per_request_metrics/)

The documented pre-extracted frame path uses `data:video/jpeg;base64,...` and video metadata in `media_io_kwargs`. Implement it only against a verified adapter/version and preserve temporal metadata. [Official multimodal inputs](https://docs.vllm.ai/en/stable/features/multimodal_inputs/)

## 9. Testing, resource handling, CI, and release discipline

### 9.1 Meaningful test groups

| Group | What it proves | Default requirement |
| --- | --- | --- |
| Unit/contract | Units, schemas, error behavior, accounting, comparability, redaction. | Fast and offline. |
| Processor integration | Actual supported processor behavior on curated media. | CPU; pinned cached artifacts, explicitly enabled download step. |
| CLI/package smoke | Real installed wheel/sdist, extras boundaries, help and implemented commands. | Clean environments. |
| Protocol | Real HTTP/SSE interaction against deterministic local mock server. | CPU; does not establish GPU validity. |
| Live backend parity | Known actual vLLM request/processing tuple. | Owner-provided endpoint; mandatory for corresponding verified claims. |
| Telemetry/profiling | Real source/units/scope/overhead. | Optional hardware gate tied to the advertised capability. |

Do not add tests asserting that a README contains a heading or that a helper returns its own formula. Test externally meaningful behavior. Use deterministic small fixtures and document origins. Keep model weights, large video datasets, private videos, and large traces out of Git.

Unit tests must not download assets. Separate artifact preparation from cached processor tests. The default CI should be executable on ordinary hosted CPU runners with minimal permissions. Use Linux as the primary baseline and add a macOS CPU smoke job where available and affordable; claim support only for environments actually tested. Pin external GitHub Actions to verified commit SHAs with readable version comments. Do not invent SHAs. Avoid privileged pull-request execution and automatic paid GPU jobs.

Use coverage as a diagnostic, not an arbitrary completion target. Relevant tests, a reproducible experiment, and preserved evidence matter more than a headline percentage.

### 9.2 Practical safeguards

Implement explicit resource limits for file size, decoded pixels/frames, tensor budgets, subprocess runtime, HTTP timeout, and report size. Defaults should support short demos on a normal laptop and fail with actionable guidance for oversized inputs. Do not silently truncate a workload and report it as complete.

No shell interpolation of media filenames or prompt content. Handle subprocesses with argument arrays. Avoid fetching arbitrary remote media in the initial inspector; local inputs are sufficient. Processor downloads must exclude weights and remote executable code by default. Redact authorization headers, credentials in URLs, query tokens, and sensitive raw payloads from ordinary logs and reports.

### 9.3 Release process

Prepare release candidates only for implemented and validated features. Check the actual PyPI name and naming-normalization collisions before publication; a GitHub repo does not reserve a distribution name. If the name is unavailable, report the conflict instead of silently selecting another package name.

Before a release: validate changelog/status, build wheel and sdist, install both into clean environments, run the implemented quickstart, verify package data/templates/type information, review license/media attribution, and verify no secrets/private artifacts are included. Present the evidence before asking for any still-required publication authorization.

Prefer trusted publishing when the owner configures it. A release workflow should be manually gated and not auto-publish on every push. Do not issue `uv publish`, create a public GitHub release, push a tag, change visibility, or contact people without relevant authorization. Package a truthful inspection-only release if that is the validated scope; do not block it on an optional future profiler.

## 10. Required root AGENTS.md content

Create a root `AGENTS.md` using the following baseline. Adapt verified project commands and file links after the skeleton exists, but preserve the substantive rules. If an existing AGENTS.md is present, merge carefully and surface conflicts rather than replacing it wholesale.

```markdown
# Agent Instructions for ModalMeter

## Product
ModalMeter is a Python library and CLI for inspecting multimodal inputs and
measuring their serving behavior. Read docs/vision.md, docs/roadmap.md,
docs/measurement-contract.md, docs/support-matrix.md, and
docs/implementation-state.md before changing behavior.

## Communication and execution
- Discuss work with the maintainer in Turkish.
- Write code, comments, documentation, CLI output, and commits in English.
- Work one milestone at a time unless the user explicitly authorizes a batch.
- Complete the milestone's concrete work and relevant checks before requesting
  milestone verification. Do not ask permission for each routine edit.
- Show actual output and limitations. Never report an unrun check as passed.
- Resume from implementation-state.md; re-read source instead of trusting a
  previous agent's summary alone.

## Evidence and correctness
- Separate observed, measured, derived, estimated, and unavailable data.
- Missing measurements are null with reasons, never zero.
- Processor correctness and backend parity are separate, versioned claims.
- Do not equate encoder patches, visual placeholders, and full prompt tokens.
- Do not equate video input with a sequence of independent image requests.
- Preserve sampling, timestamps, transforms, temporal padding, and provenance.
- SSE events are not tokens. Client timings are not kernel/stage timings.
- Device/server memory is not automatically per-request memory.
- Do not predict exact OOM, safe concurrency, speedups, or retained quality
  without an explicit validated method and workload.
- Re-check upstream source at installed versions. Record key choices in ADRs.

## Architecture
- Keep the CLI thin and use shared typed core functions for the Python API.
- Keep CPU inspection free of model weights, vLLM runtime, and GPU requirements.
- Lazy-load optional heavy dependencies; help and stored-report rendering must
  remain usable without the inspection extra.
- Prefer small concrete modules and one tested adapter over speculative
  abstraction or empty future packages.
- Do not add paid services, cloud dashboards, agents, or MCP to the MVP.

## Tests and reports
- Run relevant lint/type/tests and clean package smoke checks for the change.
- Keep default unit tests offline and distinguish processor/live GPU tests.
- Use independent reference behavior and small deterministic fixtures.
- Mock protocol tests do not validate a serving engine or GPU performance.
- Render HTML from real typed results; escape external text and work offline.
- Report visual QA as pending if the generated page cannot be inspected.
- Keep private media, model caches, run outputs, traces, and secrets out of Git.

## Git and completion
- Inspect Git status first and preserve unrelated changes.
- Use oguzhankir/<kebab-topic> feature branches; do not commit directly to main.
- Use the existing verified maintainer identity; never invent an email or alter
  global Git configuration. Follow required attribution rules of the environment.
- When creating a local commit, use an English message and git commit -s.
- Stage only reviewed task files. Do not force push, rewrite user history,
  publish, change visibility, or push without the applicable authorization.
- Update CHANGELOG.md and docs/implementation-state.md with actual changes,
  commands/results, skipped checks, blockers, and the exact next action.
- Never mark a milestone accepted before the owner verifies it.

## First steps after resuming
1. Read this file and the current implementation-state.md.
2. Inspect actual source, branch, worktree changes, and relevant upstream versions.
3. Work on the next authorized milestone and its acceptance criteria.
4. Show evidence, update continuation state, and respect the review boundary.
```

Add a short verified command table to AGENTS.md after commands exist, covering environment setup, formatting/lint, type checking, offline tests, processor integration, and package builds. Keep one canonical set of developer commands; update it when the build configuration changes.

## 11. Git, continuation, and milestone handoff

Local commits are appropriate after a coherent milestone if the verified local Git identity is present and local instructions permit them. Use the maintainer's already configured identity; do not guess an email from a username. If identity is missing, complete the work and checks first, then report the exact missing setting. Do not create unsigned-by-policy or falsely attributed history as a shortcut. DCO sign-off uses `git commit -s`; cryptographic signing is a separate existing local setting to respect.

No GitHub push is authorized by this instruction's default input block. A later explicit owner instruction can authorize it. Preserve repo privacy and do not publish a release implicitly.

After each milestone, update `docs/implementation-state.md` with:

- Current branch and milestone status.
- What changed and why, linking to real files.
- Exact validation commands, environment, outcome, and concise relevant output.
- Failed/skipped/not-run checks and their implications.
- Processor/server verification levels and where evidence is stored.
- Blockers and the minimum missing user input, if any.
- What the owner should inspect and the exact next action after verification.

Avoid a self-referential commit-hash update cycle: record the baseline commit in the state file and report the newly created milestone commit hash in the handoff after committing.

The milestone handoff to the owner should be concise Turkish: outcome, artifact/command output, material limits, and what to verify. Do not paste every log. Do not leave a failing check hidden behind a completed checkbox. If an environment limitation prevents one hardware check, distinguish finished local work from the pending validation and continue only within the currently authorized milestone.

## 12. Primary-source starting points

These include sources used for this instruction and additional upstream entry points for M0. They are not immutable snapshots. During M0, capture exact versions, model revisions and source permalinks for the code paths actually used, and put substantive findings in `docs/research.md`. A README containing historical installation advice is not proof of today's minimum compatible version.

| Source | Why to inspect it |
| --- | --- |
| [Qwen3-VL-2B-Instruct model](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) | Initial checkpoint identity, artifacts, model card, license. |
| [Official Qwen3-VL repository](https://github.com/QwenLM/Qwen3-VL) | Supported usage and helper pipeline semantics. |
| [Qwen3-VL processor source](https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_vl/processing_qwen3_vl.py) | Actual prompt expansion, token placeholders, timestamp behavior. |
| [Qwen3-VL video processor source](https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3_vl/video_processing_qwen3_vl.py) | Sampling/resizing/patchification and evolving defaults. |
| [Hugging Face artifact download guide](https://huggingface.co/docs/huggingface_hub/guides/download) | Immutable revisions and selective artifact downloads. |
| [TorchCodec repository](https://github.com/meta-pytorch/torchcodec) | Decoder/PyTorch/Python compatibility if chosen. |
| [PyAV documentation](https://pyav.org/docs/stable/) | Decoder API, timestamps, installation if chosen. |
| [vLLM multimodal inputs](https://docs.vllm.ai/en/stable/features/multimodal_inputs/) | Real video payloads, metadata and model-specific controls. |
| [vLLM Qwen3-VL implementation](https://docs.vllm.ai/en/latest/api/vllm/model_executor/models/qwen3_vl/) | Server processing and prompt replacement behavior. |
| [vLLM benchmark CLI](https://docs.vllm.ai/en/latest/benchmarking/cli/) | Existing benchmark behavior and metric boundaries. |
| [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/) | Streaming, usage and supported endpoint parameters. |
| [vLLM per-request metrics](https://docs.vllm.ai/en/stable/features/per_request_metrics/) | Optional server timing observations and prerequisites. |
| [vLLM production metrics](https://docs.vllm.ai/en/stable/usage/metrics/) | Metric names, types, units and scope. |
| [vLLM optimization](https://docs.vllm.ai/en/latest/configuration/optimization/) | Scheduling, preemption and tuning trade-offs. |
| [vLLM profiling](https://docs.vllm.ai/en/latest/contributing/profiling/) | Official instrumentation workflow and overhead. |
| [vLLM prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) | Request-cache confounders. |
| [PyTorch CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html) | Asynchronous execution and allocator memory distinctions. |
| [NVML device queries](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html) | Device/process telemetry scope. |
| [GuideLLM](https://github.com/vllm-project/guidellm) | Existing benchmark functionality and possible later integration. |
| [vLLM Doctor](https://github.com/vllm-doctor/vllm-doctor) | Existing diagnostic workflow and overlap. |
| [AIConfigurator](https://github.com/ai-dynamo/aiconfigurator) | Existing performance/configuration optimization scope. |
| [uv packaging](https://docs.astral.sh/uv/guides/package/) | Build/install/publish mechanics. |
| [uv GitHub Actions integration](https://docs.astral.sh/uv/guides/integration/github/) | Reproducible CI and later release setup. |

## 13. Begin now

Execute **M0** in the actual local checkout. Create the concrete documents, minimal package, source-backed decisions, relevant validation evidence, and continuation record described above. Do not stop at proposing a directory tree. Do not advance into M1 until the owner verifies M0, unless the owner explicitly changes the execution mode.
