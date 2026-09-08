# Research and feasibility record

Checked 2026-09-08 against primary sources and installed artifacts. This is an M0
feasibility record, not processor correctness or performance validation. Source
permalinks below identify reviewed code; moving documentation pages are labeled
as such. Exact GitHub refs are also [machine-readable](evidence/m0/source-refs.json).

## Initial checkpoint and actual configuration

The [model API](https://huggingface.co/api/models/Qwen/Qwen3-VL-2B-Instruct) returned
public=true in the sense `private=false`, `gated=false`, revision
`89644892e4d85e24eaac8bacfd4f463576704203`. The
[model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/tree/89644892e4d85e24eaac8bacfd4f463576704203)
identifies the requested checkpoint, with Apache-2.0 model metadata. No checkpoint
substitution or weight download occurred. The stale card advice about an unreleased
4.57.0 is superseded for this experiment by the installed released 4.57.6 evidence.

[Image config](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/preprocessor_config.json)
uses the Qwen2VL fast image processor, patch=16, temporal patch=2, merge=2,
mean/std=0.5, pixel bounds 65536 and 16777216.
[Video config](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/video_preprocessor_config.json)
uses Qwen3VLVideoProcessor, the same patch/merge settings, and pixel bounds 4096
and 25165824. Effective settings must come from the loaded artifact plus source
defaults, not generic class constants alone.

Only eight explicitly named config/tokenizer/template artifacts (about 11.5 MB
combined, decimal) were fetched. [Artifact manifest](evidence/m0/processor-artifacts.json)
records each URL, byte length and SHA-256. Safetensors may be installed as a Python
dependency; that does not mean a safetensors weight file was downloaded. No model
class was constructed. The probe loads local artifacts with remote code disabled.

## Selected released path

Exact feasibility tuple: Transformers 4.57.6, Torch 2.9.1, torchvision 0.24.1,
Pillow 12.0.0, PyAV 16.1.0. PyPI version-specific metadata verified each release;
all declare Python minima compatible with 3.11/3.12. This does not establish all
platform wheels or justify a minimum-supported-version claim.

- [Transformers release metadata](https://pypi.org/pypi/transformers/4.57.6/json)
- [Torch release metadata](https://pypi.org/pypi/torch/2.9.1/json)
- [torchvision compatibility table at v0.24.1](https://github.com/pytorch/vision/blob/v0.24.1/README.md)
- [PyAV release metadata](https://pypi.org/pypi/av/16.1.0/json)
- [Pillow release metadata](https://pypi.org/pypi/pillow/12.0.0/json)

We deliberately investigated the released 4.57 maintenance path, not an unpinned
Git branch. Current PyPI metadata also listed newer Transformers/Torch majors;
those were not installed or verified and carry no support claim here. Exact
transitive locks and actual runtime versions are preserved with the probe.

Reviewed Transformers v4.57.6 resolves to commit
`753d61104116eefc8ffc977327b441ee0c8d599f`:

| Source | Finding and implication |
| --- | --- |
| [Combined processor](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/models/qwen3_vl/processing_qwen3_vl.py#L160) | Expands image grid product / merge squared and video temporal groups; final IDs must independently validate accounting in M1/M2. Metadata is popped only when return_metadata keyword is absent. |
| [Timestamp expansion](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/models/qwen3_vl/processing_qwen3_vl.py#L314) | Uses index/fps and grouped timestamps, duplicates trailing indices in-place. This is not decoded VFR PTS. |
| [Native video processor](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/models/qwen3_vl/video_processing_qwen3_vl.py#L86) | Default fps=2, min=4, max=768; array sampling uses rounded linspace. Resize couples temporal count and total pixels; odd temporal inputs repeat the last frame. |
| [Video preprocessing boundary](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/video_processing_utils.py#L287) | Array video plus explicit metadata supports disabled sampling. Image-list behavior differs; do not assume list semantics. Requires vision/torchvision. |
| [Video metadata](https://github.com/huggingface/transformers/blob/753d61104116eefc8ffc977327b441ee0c8d599f/src/transformers/video_utils.py#L80) | Metadata timestamps derive from indices/fps. Built-in PyAV helper uses container frame count/FPS; use separate decoded-PTS provenance instead of treating that metadata as decoded truth. |

Four downloaded source files were byte-identical to installed wheel sources;
[hash comparisons](evidence/m0/installed-source-check.json) preserve this check.
The [Qwen official helper documentation](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/README.md#new-qwen-vl-utils-usage)
warns that helper-resized inputs require `do_resize=False` in the processor. We
choose one native processing path to avoid independent sampling/resizing chains.

[PyAV installation documentation](https://pyav.org/docs/stable/overview/installation.html)
(moving stable, checked today) describes binary wheels linked against FFmpeg for
macOS/Linux/Windows. Local PyAV FFV1 roundtrip succeeded with three exact RGB frames
and PTS 0, 1/2, 1 seconds. The probe's FFmpeg library versions are recorded; it uses
no shell executable. Linux/Python 3.11 inspection feasibility remains unexecuted.

The initial metadata/tensor call failed, then the separately retained metadata
path succeeded. [ADR 0002](decisions/0002-processor-path.md) contains the exact
resolution and restrictions. No source was patched and no acceptance criterion
was weakened. A feasibility observation remains below processor verification.

## Related tools and overlap

These are source-based scope comparisons, not claims of measured superiority,
uniqueness, popularity, or product quality.

| Primary source snapshot | Existing scope | ModalMeter implication |
| --- | --- | --- |
| [GuideLLM](https://github.com/vllm-project/guidellm/blob/fc2dbe9edd4f7f1a4e9ccd752f6f43591adbcb73/README.md) | Endpoint workloads, multimodal inputs, real/synthetic datasets, concurrency/rate profiles and reports | Significant benchmark/report overlap. Focus on per-media provenance and controlled input comparisons; consider output import later rather than rebuilding its full load generator. |
| [vLLM Doctor](https://github.com/vllm-doctor/vllm-doctor/blob/a96df3f1acea75ca6c59be9622019cb5f97804bd/README.md) | Live vLLM/Prometheus metric diagnosis and explicit rules for server symptoms | Telemetry-rule overlap. ModalMeter's initial artifact is an individual input and its processing decisions. |
| [AIConfigurator](https://github.com/ai-dynamo/aiconfigurator/blob/77fd0773407b3683d8a671fe24a30a7110651b64/README.md) | Performance models from collected operation data, search over serving configurations; snapshot describes migration to AISimulate | Do not claim universal GPU configuration prediction. Any estimate differs from direct request measurement and needs its own validity domain. |

## vLLM integration research, not a pinned backend claim

Checked moving stable/latest docs on 2026-09-08; no vLLM runtime was installed and
no endpoint version is known. Recheck the actual installed server release before
implementation and live validation; these pages do not reserve a supported tuple.

- [Multimodal inputs](https://docs.vllm.ai/en/stable/features/multimodal_inputs/)
  describes pre-extracted `data:video/jpeg;base64,...` video transport with
  `media_io_kwargs` metadata and separate video controls. M3/M4 must verify it
  against a real release, preserve timestamps and account for JPEG pixel changes.
- [Per-request metrics](https://docs.vllm.ai/en/stable/features/per_request_metrics/)
  describes the opt-in flag, statistics prerequisite, potential CPU overhead and
  attribution restrictions for multiple sequences. Treat missing metrics as
  unavailable and keep server fields separate from client timing.
- [Native benchmark CLI](https://docs.vllm.ai/en/latest/benchmarking/cli/) already
  offers endpoint and multimodal benchmark workflows. Prefer integration over
  copying an entire benchmarking framework.
- [Official profiling](https://docs.vllm.ai/en/latest/contributing/profiling/)
  distinguishes profiling tools and overhead; richer Torch profiler settings are
  not an uninstrumented performance baseline. Stage profiling is deferred to M6.

## Build/CI sources and open questions

The [uv package guide](https://docs.astral.sh/uv/guides/package/) and
[uv CI guide](https://docs.astral.sh/uv/guides/integration/github/) are moving docs;
actual local execution uses uv 0.11.7. Actions were resolved through the GitHub
commit API, not invented: checkout v4.2.2 and setup-uv v7, exact SHAs in the workflow
and source-refs JSON. GitHub-hosted execution is still pending authorization to push.

Before M1: independently test image orientation, boundaries, ID-based visual
positions and attention-mask lengths; design the production artifact allowlist.
Before M2: verify bounded default/uniform selection, actual PTS vs processor labels,
short/VFR/nonzero-origin inputs and single-pass metadata capture. Before M3/M4:
resolve server transport/release, usage and parity instrumentation. Before publishing:
check PyPI name availability, dependency/media licenses and package contents again.
