# ADR 0002: Native Transformers processing with explicit PyAV media provenance

Date: 2026-09-08. Status: chosen for M0 feasibility; M1/M2 verification pending.

## Context and sources

The requested public, ungated model `Qwen/Qwen3-VL-2B-Instruct` resolves to
`89644892e4d85e24eaac8bacfd4f463576704203`. Its card still recommends Git main and
calls 4.57.0 unreleased; that historical advice is not today's compatibility rule.
Released Transformers 4.57.6 loads the pinned processor on this Mac without model
weights. Exact artifact hashes and source permalinks are in the
[research record](../research.md) and [probe evidence](../evidence/m0/README.md).

The selected tuple is Transformers 4.57.6, Torch 2.9.1, torchvision 0.24.1,
Pillow 12.0.0, PyAV 16.1.0 (exact transitive versions in `uv.lock`). We select a
released 4.57 maintenance baseline whose code was inspected, not the newest major
release or a minimum-version claim. Both image-fast and video processing require
torchvision/Torch. The native video processor accepts explicit array videos and
VideoMetadata and has `do_sample_frames=False`. Qwen's helper also performs resize;
its README requires disabling the processor resize to avoid doing it twice.

## Decision

Use the native `Qwen3VLProcessor`, `Qwen2VLImageProcessorFast`, and
`Qwen3VLVideoProcessor` with a separate PyAV decode/manifest layer. Do not depend
on qwen-vl-utils or TorchCodec in this first path. Keep all model weights and model
forward/generate calls out. Allowlist only processor/tokenizer/config/template
artifacts at an immutable revision, load locally with remote code disabled.

For planned `uniform`, select frames once by a documented deterministic PTS
policy, preserve source ordinal/actual rational PTS, and pass an array video with
explicit metadata and `do_sample_frames=False`. Native processing owns resizing,
normalization, temporal padding and grids. Do not feed a helper-resized video into
another resizing path. M2 must define and test ties, unknown metadata and limits.

For planned `model-default`, use this exact native processor's sampling function
and effective settings, preferably selecting its indices against a decoded
metadata pass before bounded frame materialization. Do not call our uniform policy
model-default. The source defaults are fps=2, min_frames=4, max_frames=768, patch=16,
temporal patch=2 and merge=2. The pinned artifact overrides video size to
shortest_edge=4096 and longest_edge=25165824; those are pixel budgets used by the
resize algorithm, not literal side lengths. A frame-count change can change resize.
M2 must verify the full path and record requested/selected/processed counts.

## Executable contradiction and resolution

The first probe called the combined processor with `return_metadata=True` and
`return_tensors="pt"`. It failed trying to convert VideoMetadata into a tensor,
then emitted a misleading padding error. The
[actual traceback](../evidence/m0/spike-initial-error.txt) is preserved. This is not
an invitation to enable arbitrary padding or modify upstream code.

The successful probe obtains metadata separately from the video processor without
a tensor return type, then omits `return_metadata` entirely in the combined
processor's tensor-producing call. The combined source removes the metadata key
only when this keyword is absent; even `return_metadata=False` is not equivalent.
That M0 probe runs video processing twice to inspect the behavior; **production
must not adopt the duplicate work**. Preserve a deep-copied input manifest and
obtain required observations around one verified processing path in M1/M2.

For three synthetic frames at source indices [1,5,9], sampling disabled preserves
those indices through video preprocessing. Prompt expansion mutates the passed
metadata indices to [1,5,9,9], so deep-copy provenance before the call. The observed
grid is [2,4,4]. This is a smoke observation, not independently verified accounting.

## Timestamp and parity limits

The release computes timestamps as index/fps, groups pairs, averages first/last,
and formats labels to one decimal place. It does not accept actual irregular PTS
as an authoritative prompt-timestamp field. The observed labels are 1.5 and 4.5
seconds for this synthetic index metadata. Preserve decoded PTS separately from
processor index/FPS values and displayed group labels. Do not falsify metadata to
claim exact VFR/nonzero-origin timestamp equivalence. M2 must either prove a
supported convention for each case or explicitly restrict the claim.

PyAV 16.1.0 successfully encoded/decoded three FFV1 synthetic frames with equal
pixels and rational PTS 0, 1/2, 1 seconds using bundled FFmpeg libraries. This does
not establish arbitrary codec/VFR support. No shell ffmpeg executable is required
by the probe. PyAV is chosen for CPU/macOS/Linux wheel availability and access to
PTS; Linux execution remains pending CI/integration.

No model adapter, complete manifest, token accounting test, image/video inspection
API, or server adapter is implemented. Processor status remains `not_run` for
correctness acceptance; server parity remains `server_parity_unverified` separately
for image and video. vLLM transport, timestamps, pruning and pixel equivalence must
be checked against the actual endpoint release in M3/M4.
