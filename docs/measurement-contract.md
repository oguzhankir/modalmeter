# Measurement contract

This contract governs all future inspection and benchmark results. M0 implements
only numeric evidence primitives in [schemas.py](../src/modalmeter/schemas.py);
no runtime inference measurements exist yet.

Store durations in milliseconds (`ms`), memory in bytes, decoded media timestamps
as rational seconds (`pts * time_base`), and raw client event offsets as integer
nanoseconds from a run-local monotonic origin. Convert nanoseconds to milliseconds
by dividing by 1,000,000. Wall-clock UTC identifies the run and never supplies a
duration. Render MiB = bytes / 2^20 and GiB = bytes / 2^30. Every numeric quantity
must name its semantic unit and scope; negative configuration/comparison deltas
are permitted, but later absolute duration/count schemas must reject negatives.

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
