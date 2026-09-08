"""M0 feasibility probe only. Not an inspector, benchmark, or parity test."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import tempfile
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import av  # noqa: E402
import numpy as np  # noqa: E402
from transformers import AutoProcessor  # noqa: E402
from transformers.video_utils import VideoMetadata  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--processor-dir", type=Path, required=True)
args = parser.parse_args()
manifest = json.loads(Path(__file__).with_name("processor-artifacts.json").read_text())
for artifact in manifest["artifacts"]:
    content = (args.processor_dir / artifact["file"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == artifact["sha256"]

processor = AutoProcessor.from_pretrained(
    args.processor_dir, local_files_only=True, trust_remote_code=False
)
selected_indices = [1, 5, 9]
video = np.zeros((3, 64, 64, 3), dtype=np.uint8)
for index in range(3):
    video[index, :, :, index] = 64 * (index + 1)
metadata = VideoMetadata(total_num_frames=12, fps=2.0, frames_indices=selected_indices.copy())
video_only = processor.video_processor(
    videos=[video],
    video_metadata=[copy.deepcopy(metadata)],
    do_sample_frames=False,
    return_metadata=True,
)
preserved_indices = list(video_only["video_metadata"][0].frames_indices)
processed = processor(
    text=["<|vision_start|><|video_pad|><|vision_end|>"],
    videos=[video],
    video_metadata=[metadata],
    do_sample_frames=False,
    return_tensors="pt",
)

with tempfile.TemporaryDirectory(prefix="modalmeter-codec-") as temporary:
    media = Path(temporary) / "synthetic.mkv"
    with av.open(str(media), "w") as container:
        stream = container.add_stream("ffv1", rate=2)
        stream.width, stream.height, stream.pix_fmt = 64, 64, "bgr0"
        for array in video:
            for packet in stream.encode(av.VideoFrame.from_ndarray(array, format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(media)) as container:
        frames = list(container.decode(video=0))
        pts = [str(frame.pts * frame.time_base) for frame in frames]
        pixels_equal = all(
            np.array_equal(frame.to_ndarray(format="rgb24"), array)
            for frame, array in zip(frames, video, strict=True)
        )

result = {
    "purpose": "M0 feasibility only; synthetic inputs, no model weights or inference",
    "platform": {
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    },
    "versions": {
        name: importlib.metadata.version(name)
        for name in [
            "transformers",
            "torch",
            "torchvision",
            "av",
            "pillow",
            "numpy",
            "huggingface-hub",
            "tokenizers",
        ]
    },
    "model_revision": manifest["revision"],
    "processor_class": type(processor).__name__,
    "image_processor_class": type(processor.image_processor).__name__,
    "video_processor_class": type(processor.video_processor).__name__,
    "video_size": processor.video_processor.size,
    "video_defaults": {
        name: getattr(processor.video_processor, name)
        for name in [
            "fps",
            "min_frames",
            "max_frames",
            "do_sample_frames",
            "patch_size",
            "temporal_patch_size",
            "merge_size",
        ]
    },
    "selected_source_indices": selected_indices,
    "indices_after_video_preprocessing": preserved_indices,
    "metadata_indices_after_prompt_expansion": list(metadata.frames_indices),
    "video_grid_thw_observed": processed["video_grid_thw"].tolist(),
    "expanded_prompt_observed": processor.tokenizer.decode(processed["input_ids"][0]),
    "pyav_roundtrip": {
        "codec": "ffv1",
        "frames": len(frames),
        "pts_seconds_rational": pts,
        "pixels_equal": pixels_equal,
    },
    "ffmpeg_libraries": {key: list(value) for key, value in av.library_versions.items()},
    "processor_verification": "not_run",
    "server_parity": "server_parity_unverified",
}
print(json.dumps(result, indent=2, allow_nan=False))
