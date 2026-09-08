# Product vision

This is the product direction, not a list of implemented features. See the
[roadmap](roadmap.md) for acceptance gates and the [README](../README.md) for working commands.

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
