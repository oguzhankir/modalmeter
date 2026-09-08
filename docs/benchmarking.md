# Benchmarking methodology

No benchmark command, transport, latency measurement, telemetry or live endpoint
validation is implemented in M0. Everything below is an M3/M4 implementation
contract. Current runnable commands are limited to the README foundation quickstart.

Use a closed-loop request-count workload initially; concurrency is not an arrival
rate. Require `n=1`, explicit local model identity vs server alias, bounded output,
streaming usage when supported, no implicit retries, and one persisted record per
attempt. Record requested/effective generation options; a common maximum output
length does not imply equal generated lengths. A partial run must preserve evidence
and return a documented nonzero status.

For timing boundaries and whole-run throughput denominators, use the canonical
[measurement contract](measurement-contract.md). Protocol EOF without the expected
completion is incomplete. A mock validates parsing/arithmetic, never GPU performance.

### 8.2 Cache and load controls

Default to `cache_policy=as_configured`. Record which settings are observed, owner-supplied, or unknown. Distinguish startup/compilation coldness, request-cache coldness, and a warmed repeated prompt/media workload.

Identical warmup requests can prime prefix and multimodal caches. Randomizing text does not prove media caches are cold. Never silently reset caches or change a serving process. Dedicated controlled-server recipes may disable/reconfigure reuse only when explicitly authorized for that experiment.

Use a recorded scenario-order seed where interleaving is appropriate; avoid comparing all baseline requests during one load condition against all candidate requests during another without noting the confounder. Record background-load uncertainty, connection reuse, request payload sizes, and client location as relevant. If two requested frame/pixel settings resolve to the same effective processor input, explain that they are not distinct experiments.

Small runs should show raw samples and robust summaries. Do not advertise reliable tail percentiles from a handful of requests. Document the percentile estimator and sample count whenever percentiles are shown. Statistical intervals, if added, must identify the method and remain conditional on the experimental design.

### 8.3 Optional current vLLM capabilities

Primary-source checks at the date of this instruction found an optional per-request-metrics feature and pre-extracted video-frame transport. Verify these in the release actually used; do not require current `main` behavior.

For compatible deployments, `--enable-per-request-metrics` can expose a server `metrics` record, including timing/queue fields. Streaming retrieval depends on final usage reporting. Preserve raw server names and their documented timing boundaries under `server_request_metrics`; these do not replace client observations or supply a complete vision-stage breakdown. Treat null/absent records as unavailable. Collecting them may add overhead. [Official per-request metrics](https://docs.vllm.ai/en/stable/features/per_request_metrics/)

The documented pre-extracted frame path uses `data:video/jpeg;base64,...` and video metadata in `media_io_kwargs`. Implement it only against a verified adapter/version and preserve temporal metadata. [Official multimodal inputs](https://docs.vllm.ai/en/stable/features/multimodal_inputs/)

## Live validation runbook gate (M4)

Before sending media, obtain an owner-provided existing endpoint, server startup
configuration, engine and model revisions, and approved media. Request the credential
variable name, never a secret in chat. Record unknown server settings explicitly.
First validate one image, then video. Pre-extracted transport needs temporal metadata
and transmitted-pixel accounting (including JPEG changes). Aggregate prompt equality
alone cannot establish media/token parity. Encoded-video transport may resample;
independent images do not substitute for video.

Enable a frame-count experiment only after proving the tuple honors the control.
Hold concurrency, prompt and output settings fixed; diff effective dimensions,
grids, selected frames and pruning. A shared total-pixel budget can couple frame
count and resize. Preserve failures and raw samples; an improvement is not required
for a valid experiment. No endpoint recipe is claimed executed in M0.
