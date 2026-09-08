# ADR 0003: Bounded CPU inspection and single-pass video processing

Date: 2026-09-08. Status: implemented; reference evidence in
[M1](../evidence/m1/) and [M2](../evidence/m2/). Supersedes the M0 diagnostic
metadata workaround in [ADR 0002](0002-processor-path.md), not its pinned tuple.

## Evidence and decision

The installed Transformers 4.57.6 source was re-read at commit
`753d61104116eefc8ffc977327b441ee0c8d599f`. The
[combined processor](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/models/qwen3_vl/processing_qwen3_vl.py)
passes `return_tensors` to the final BatchFeature. M0's `return_metadata=True`
plus `return_tensors="pt"` attempted to tensorize VideoMetadata and failed.
**Use `return_metadata=True, return_tensors=None`**: actual pixel/grid tensors,
Python input-ID/attention-mask lists and VideoMetadata survive in the same call.
No second processor call, patched function, or private hook is necessary.
Tests independently compare native outputs and instrument invocation counts.

Use the exact eight processor/tokenizer/config/template artifacts at
Qwen/Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`.
Verify sizes and SHA-256 before loading with `local_files_only=True` and
`trust_remote_code=False`. Do not use model/weight APIs or hub snapshots.

PyAV scans one decoded frame at a time, preserving rational PTS and actual frame
count, then decodes again to materialize selected RGB frames. Native
`sample_frames` owns model-default index selection; uniform mode chooses nearest
rational PTS targets between first and last presentation times, ties earlier,
and de-duplicates repeated nearest matches. Requested counts are budgets, not
promises of unique frames. Missing/nonmonotonic PTS or invalid/missing nominal FPS
is rejected; the native implicit 24 FPS fallback is never used.

The native [video resize and padding path](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/models/qwen3_vl/video_processing_qwen3_vl.py)
rejects fewer than two frames before its padding code. For one selected frame,
explicitly replicate it to two input frames and label this adapter repair in the
manifest. For odd counts of three or more, let native processing repeat the final
frame. Verify returned metadata and temporal grid against the recorded mapping.
Call native processing once with `do_sample_frames=False`. Native processing owns
all model resize/rescale/normalize/patch operations; thumbnails are independent.
Use a local CPU device context so a caller's Torch default device cannot redirect
inspection to a GPU. No global device setting changes.

Native video prompt labels use source ordinal / nominal FPS, group pair averages,
and one-decimal formatting. Preserve these separately from actual PTS, including
nonzero origins and VFR. Local CPU reference agreement does not establish timestamp
fidelity or any serving parity. Reserved tokenizer markers and native temporary
`<|placeholder|>` are rejected in user prompts to prevent accidental expansion.

Read emitted patch-tensor row counts and exact active placeholder IDs as observed
facts. Derive the independent grid/merge formula and compare all three. Sum the
attention mask for complete non-padding prompt length. The residual includes chat
structure and timestamps; isolated user-text/timestamp positions remain unavailable.

## Resource and output constraints

Defaults: 256 MiB source, 16,777,216 pixels per decoded frame, 128 selected frames,
10,000 scanned frames, 256 MiB retained decode workspace, 30 seconds cooperative
decode time, 256 MiB predicted processor working tensors, 16 KiB UTF-8 prompt.
The tensor preflight uses the native resize function, a fourfold original-input
workspace and a fourfold float32 transformed-tensor allowance. This catches large
source copies even when output resolution is small. It is a conservative admission
budget, **not measured process RSS, a hard allocator cap, or GPU memory prediction**.
Native codec calls/buffers and runtime overhead can exceed these allowances;
timeouts are checked between frames and cannot interrupt a blocked native call.

`pixel_budget` overrides the processor's maximum pixel setting: image area versus
video temporal-area budget. Frame-count changes can therefore also change resize.
Reports show requested/effective differences and identify the coupled change.

Use Pydantic versioned records, bounded atomic run writes, and base-only Jinja2
rendering with autoescape. Default artifacts omit raw prompt/path/media; opt-in
thumbnails are bounded raster data URIs. Comparisons preserve incompatibilities
and suppress deltas when source, prompt or processor identity differs. No server
requests, model output, inferred quality or performance claims are introduced.
