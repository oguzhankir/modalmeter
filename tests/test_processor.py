"""Explicit, offline acceptance against the unmodified pinned CPU processor.

Set MODALMETER_TEST_PROCESSOR_DIR to the verified eight-file artifact directory.
These tests never fetch artifacts and do not validate any serving backend.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.metadata
import importlib.util
import os
import re
import socket
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from modalmeter.schemas import InspectionConfig, InspectionResult, TokenAccounting

pytestmark = pytest.mark.processor

_generator_spec = importlib.util.spec_from_file_location(
    "modalmeter_fixture_generator", Path(__file__).parents[1] / "examples" / "generate_fixtures.py"
)
assert _generator_spec is not None and _generator_spec.loader is not None
_generator = importlib.util.module_from_spec(_generator_spec)
_generator_spec.loader.exec_module(_generator)
frame_rgb = _generator.frame_rgb
generate = _generator.generate
write_image = _generator.write_image
write_video = _generator.write_video

# Independent artifact identities reviewed in M0, deliberately not imported from
# the resolver under test. The test input is an immutable released processor.
REFERENCE_HASHES = {
    "config.json": "bec4b3d446efa05807365c9e1cec03ac590836879d02f3a6da879971154bdd3b",
    "preprocessor_config.json": "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516",
    "video_preprocessor_config.json": (
        "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13"
    ),
    "tokenizer_config.json": "c2da771801886ad9ae98181793ffd3dfb7f1af30f6f7c6a4e15d7dbba52e2399",
    "tokenizer.json": "a5d85b6dcc535e6b93115a9ef287e6132fdbf30270da6218194ba742261173c7",
    "chat_template.json": "6f8a6a55027e3da5160105556cda5dd69f6423f1c32645f6730d32de7773d0c4",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
    "merges.txt": "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
}


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cache miss is a failure/skip, never implicit test network access."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Processor acceptance tests must not open network connections.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="session")
def processor_dir() -> Path:
    configured = os.environ.get("MODALMETER_TEST_PROCESSOR_DIR")
    if not configured:
        pytest.skip("Set MODALMETER_TEST_PROCESSOR_DIR to an explicitly prepared offline cache.")
    directory = Path(configured)
    for name, expected in REFERENCE_HASHES.items():
        assert (directory / name).is_file(), f"Missing cached reference artifact: {name}"
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected
    return directory


@pytest.fixture(scope="session")
def reference(processor_dir: Path) -> Any:
    assert importlib.metadata.version("transformers") == "4.57.6"
    assert importlib.metadata.version("torch").split("+")[0] == "2.9.1"
    transformers = importlib.import_module("transformers")
    return transformers.AutoProcessor.from_pretrained(
        str(processor_dir), local_files_only=True, trust_remote_code=False
    )


def reference_prompt(processor: Any, modality: str, prompt: str = "Describe this media.") -> str:
    text: str = processor.apply_chat_template(
        [{"role": "user", "content": [{"type": modality}, {"type": "text", "text": prompt}]}],
        tokenize=False,
        add_generation_prompt=True,
    )
    return text


def inspect(path: Path, processor_dir: Path, **kwargs: Any) -> InspectionResult:
    from modalmeter.inspect import inspect_media

    return inspect_media(
        InspectionConfig(path=path, processor_dir=processor_dir, offline=True, **kwargs)
    )


def assert_token_evidence(accounting: TokenAccounting, expected: Any, reference: Any) -> None:
    """Check actual token IDs/mask/tensor rows, not a copy of resize formulas."""
    ids = expected["input_ids"][0]
    mask = expected["attention_mask"][0]
    placeholder_id = accounting.placeholder_token_id
    positions = [
        index
        for index, (token_id, keep) in enumerate(zip(ids.tolist(), mask.tolist(), strict=True))
        if token_id == placeholder_id and keep
    ]
    assert accounting.observed_placeholder_indices == positions
    assert accounting.visual_placeholder_positions.value == len(positions)
    assert accounting.grid_derived_visual_positions.value == len(positions)
    assert accounting.grid_matches_placeholders
    assert accounting.nonpadding_prompt_positions.value == int(mask.sum().item())
    assert accounting.nonvisual_prompt_positions.value == int(mask.sum().item()) - len(positions)
    boundary_ids = (reference.vision_start_token_id, reference.vision_end_token_id)
    assert accounting.vision_boundary_positions.value == sum(
        token_id in boundary_ids and bool(keep)
        for token_id, keep in zip(ids.tolist(), mask.tolist(), strict=True)
    )
    assert accounting.server_prompt_usage.value is None
    assert accounting.server_prompt_usage.unavailable_reason
    assert accounting.server_completion_usage.value is None
    assert accounting.user_text_positions.value is None


@pytest.mark.parametrize(
    ("width", "height"),
    [(1, 1), (31, 31), (32, 33), (65, 63), (1024, 32), (6400, 32)],
)
def test_image_boundaries_match_actual_reference_output(
    tmp_path: Path, processor_dir: Path, reference: Any, width: int, height: int
) -> None:
    path = tmp_path / "synthetic.png"
    write_image(path, width, height)
    image_module = importlib.import_module("PIL.Image")
    with image_module.open(path) as image:
        expected = reference(
            images=[image.convert("RGB")],
            text=[reference_prompt(reference, "image")],
            return_tensors="pt",
        )
    actual = inspect(path, processor_dir)
    assert actual.grid_thw == expected["image_grid_thw"][0].tolist()
    assert actual.token_accounting.encoder_grid_positions.value == expected["pixel_values"].shape[0]
    assert expected["pixel_values"].device.type == "cpu"
    assert_token_evidence(actual.token_accounting, expected, reference)
    assert actual.manifest.source_width == width
    assert actual.manifest.source_height == height
    assert actual.manifest.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual.compatibility.server_parity == "server_parity_unverified"


def test_image_unsupported_aspect_has_reference_and_adapter_error(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    image_module = importlib.import_module("PIL.Image")
    path = tmp_path / "aspect-too-wide.png"
    write_image(path, width=6401, height=32)
    with image_module.open(path) as image, pytest.raises(ValueError, match="aspect ratio"):
        reference(images=[image], text=[reference_prompt(reference, "image")], return_tensors="pt")
    with pytest.raises((ValueError, RuntimeError), match="aspect"):
        inspect(path, processor_dir)


def test_image_pixel_budget_downscale_matches_native_reference(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    path = tmp_path / "image-budget.png"
    write_image(path, width=512, height=384)
    image_module = importlib.import_module("PIL.Image")
    with image_module.open(path) as image:
        expected = reference(
            images=[image],
            text=[reference_prompt(reference, "image")],
            images_kwargs={"size": {"shortest_edge": 65536, "longest_edge": 65536}},
            return_tensors="pt",
        )
    actual = inspect(path, processor_dir, pixel_budget=65536)
    assert actual.grid_thw == expected["image_grid_thw"][0].tolist()
    assert actual.processed_width < actual.manifest.source_width
    assert actual.processed_height < actual.manifest.source_height
    assert actual.processor.effective_settings["size"] == {
        "shortest_edge": 65536,
        "longest_edge": 65536,
    }
    assert_token_evidence(actual.token_accounting, expected, reference)


def test_nonpadding_length_uses_attention_mask_on_real_padded_output(reference: Any) -> None:
    from modalmeter.adapters import account_tokens

    image_module = importlib.import_module("PIL.Image")
    expected = reference(
        images=[image_module.fromarray(frame_rgb(0))],
        text=[reference_prompt(reference, "image")],
        return_tensors="pt",
        padding="max_length",
        max_length=512,
    )
    assert expected["input_ids"].shape[1] == 512
    assert int(expected["attention_mask"].sum().item()) < 512
    actual = account_tokens(reference, expected, "image")
    assert_token_evidence(actual, expected, reference)


@pytest.mark.parametrize("frames", [2, 3, 6])
def test_uniform_video_reference_preserves_selected_indices_and_native_padding(
    tmp_path: Path, processor_dir: Path, reference: Any, frames: int
) -> None:
    path = tmp_path / "short.mkv"
    pts = (0, 500, 1000, 1500, 2000, 2500)
    write_video(path, pts=pts)
    actual = inspect(path, processor_dir, sampling="uniform", frames=frames)
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    indices = [frame.ordinal for frame in actual.manifest.selected_frames]
    assert indices == {2: [0, 5], 3: [0, 2, 5], 6: [0, 1, 2, 3, 4, 5]}[frames]
    metadata = video_utils.VideoMetadata(
        total_num_frames=len(pts), fps=2.0, frames_indices=indices.copy()
    )
    expected = reference(
        videos=[np.stack([frame_rgb(index) for index in indices])],
        text=[reference_prompt(reference, "video")],
        video_metadata=[metadata],
        do_sample_frames=False,
        return_tensors="pt",
    )
    assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
    assert (
        actual.token_accounting.encoder_grid_positions.value
        == expected["pixel_values_videos"].shape[0]
    )
    assert expected["pixel_values_videos"].device.type == "cpu"
    assert_token_evidence(actual.token_accounting, expected, reference)
    assert actual.manifest.selected_frame_count == frames
    assert actual.manifest.processed_frame_count == len(metadata.frames_indices)
    assert [frame.source_ordinal for frame in actual.manifest.processed_frames] == list(
        metadata.frames_indices
    )
    assert [frame.ordinal for frame in actual.manifest.selected_frames] == indices
    assert actual.manifest.processed_frames[-1].duplicated is (frames % 2 == 1)
    if frames % 2:
        assert actual.manifest.processed_frames[-1].duplication_reason
    decoded = reference.tokenizer.decode(expected["input_ids"][0])
    labels = re.findall(r"<\d+(?:\.\d+)? seconds>", decoded)
    assert actual.group_timestamp_labels == labels


def test_model_default_matches_native_sampling_on_complete_video(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    path = tmp_path / "model-default.mkv"
    pts = tuple(index * 400 for index in range(10))
    write_video(path, pts=pts, rate=Fraction(5, 2))
    actual = inspect(path, processor_dir)
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    metadata = video_utils.VideoMetadata(total_num_frames=10, fps=2.5)
    independently_selected = reference.video_processor.sample_frames(
        copy.deepcopy(metadata)
    ).tolist()
    expected = reference(
        videos=[np.stack([frame_rgb(index) for index in range(10)])],
        text=[reference_prompt(reference, "video")],
        video_metadata=[metadata],
        do_sample_frames=True,
        return_tensors="pt",
    )
    assert [frame.ordinal for frame in actual.manifest.selected_frames] == independently_selected
    assert actual.manifest.average_fps == 2.5
    assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
    assert_token_evidence(actual.token_accounting, expected, reference)


def test_video_fixed_total_pixel_budget_changes_per_frame_resize(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    """More frames can yield the same visual count by shrinking every frame."""
    path = tmp_path / "coupled-frame-budget.mkv"
    write_video(path, pts=tuple(index * 250 for index in range(16)), rate=Fraction(4))
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    results = []
    for frame_count in (8, 16):
        indices = [0, 2, 4, 6, 9, 11, 13, 15] if frame_count == 8 else list(range(16))
        expected = reference(
            videos=[np.stack([frame_rgb(index) for index in indices])],
            text=[reference_prompt(reference, "video")],
            # Upstream nested video kwargs must carry every video control;
            # mixing a nested size with flat metadata silently loses the latter.
            videos_kwargs={
                "size": {"shortest_edge": 4096, "longest_edge": 24576},
                "video_metadata": [
                    video_utils.VideoMetadata(
                        total_num_frames=16, fps=4.0, frames_indices=indices.copy()
                    )
                ],
                "do_sample_frames": False,
            },
            return_tensors="pt",
        )
        actual = inspect(
            path, processor_dir, sampling="uniform", frames=frame_count, pixel_budget=24576
        )
        assert [frame.ordinal for frame in actual.manifest.selected_frames] == indices
        assert actual.manifest.selected_frame_count == frame_count
        assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
        assert_token_evidence(actual.token_accounting, expected, reference)
        results.append(actual)
    assert [(item.processed_width, item.processed_height) for item in results] == [
        (64, 32),
        (32, 32),
    ]
    assert [item.token_accounting.visual_placeholder_positions.value for item in results] == [8, 8]
    assert (
        results[0].token_accounting.nonpadding_prompt_positions.value
        != results[1].token_accounting.nonpadding_prompt_positions.value
    )


@pytest.mark.parametrize(("sampling", "frames"), [("model-default", None), ("uniform", 3)])
def test_video_inspection_samples_and_preprocesses_once(
    tmp_path: Path,
    processor_dir: Path,
    reference: Any,
    monkeypatch: pytest.MonkeyPatch,
    sampling: str,
    frames: int | None,
) -> None:
    """Instrument the native entry points to detect hidden duplicate work."""
    path = tmp_path / "single-pass.mkv"
    write_video(path, pts=(0, 500, 1000, 1500, 2000, 2500))
    processor_type = type(reference.video_processor)
    native_sample = processor_type.sample_frames
    native_preprocess = processor_type._preprocess
    sample_calls: list[None] = []
    preprocess_calls: list[None] = []

    def sample_once(self: Any, *args: Any, **kwargs: Any) -> Any:
        sample_calls.append(None)
        return native_sample(self, *args, **kwargs)

    def preprocess_once(self: Any, *args: Any, **kwargs: Any) -> Any:
        preprocess_calls.append(None)
        return native_preprocess(self, *args, **kwargs)

    monkeypatch.setattr(processor_type, "sample_frames", sample_once)
    monkeypatch.setattr(processor_type, "_preprocess", preprocess_once)
    inspect(path, processor_dir, sampling=sampling, frames=frames)
    assert len(sample_calls) == (1 if sampling == "model-default" else 0)
    assert len(preprocess_calls) == 1


def test_single_frame_repair_is_explicit_and_matches_repaired_reference(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    path = tmp_path / "single.mkv"
    write_video(path, pts=(0,))
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    frame = frame_rgb(0)
    with pytest.raises(ValueError, match="temporal_factor"):
        reference(
            videos=[np.stack([frame])],
            text=[reference_prompt(reference, "video")],
            video_metadata=[
                video_utils.VideoMetadata(total_num_frames=1, fps=2, frames_indices=[0])
            ],
            do_sample_frames=False,
            return_tensors="pt",
        )
    actual = inspect(path, processor_dir)
    expected = reference(
        videos=[np.stack([frame, frame])],
        text=[reference_prompt(reference, "video")],
        video_metadata=[
            video_utils.VideoMetadata(total_num_frames=1, fps=2, frames_indices=[0, 0])
        ],
        do_sample_frames=False,
        return_tensors="pt",
    )
    assert actual.manifest.selected_frame_count == 1
    assert actual.manifest.processed_frame_count == 2
    assert actual.manifest.processed_frames[1].duplicated
    assert actual.manifest.processed_frames[1].duplication_reason
    assert actual.warnings or actual.manifest.warnings
    assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
    assert_token_evidence(actual.token_accounting, expected, reference)


def test_vfr_nonzero_origin_keeps_real_pts_separate_from_processor_labels(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    path = tmp_path / "vfr-offset.mkv"
    pts = (2000, 2120, 2530, 3100, 3900)
    write_video(path, pts=pts, rate=Fraction(5, 2))
    actual = inspect(path, processor_dir, sampling="uniform", frames=3)
    assert [frame.ordinal for frame in actual.manifest.selected_frames] == [0, 3, 4]
    for selected in actual.manifest.selected_frames:
        assert selected.pts is not None
        assert selected.time_base_numerator is not None
        assert selected.time_base_denominator is not None
        true_timestamp = selected.pts * Fraction(
            selected.time_base_numerator, selected.time_base_denominator
        )
        assert true_timestamp == Fraction(pts[selected.ordinal], 1000)
        assert selected.timestamp_seconds == float(true_timestamp)
        assert selected.processor_timestamp_seconds == selected.ordinal / 2.5
        assert selected.timestamp_seconds != selected.processor_timestamp_seconds
    assert actual.compatibility.server_parity == "server_parity_unverified"
    assert any(
        "timestamp" in warning.lower() or "vfr" in warning.lower() for warning in actual.warnings
    )
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    expected = reference(
        videos=[np.stack([frame_rgb(index) for index in (0, 3, 4)])],
        text=[reference_prompt(reference, "video")],
        video_metadata=[
            video_utils.VideoMetadata(total_num_frames=5, fps=2.5, frames_indices=[0, 3, 4])
        ],
        do_sample_frames=False,
        return_tensors="pt",
    )
    assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
    assert_token_evidence(actual.token_accounting, expected, reference)
    assert actual.group_timestamp_labels == re.findall(
        r"<\d+(?:\.\d+)? seconds>", reference.tokenizer.decode(expected["input_ids"][0])
    )


def test_generated_fixture_manifest_matches_actual_decoder_pixels_and_pts(tmp_path: Path) -> None:
    import json

    av = importlib.import_module("av")
    manifest = json.loads(generate(tmp_path).read_text(encoding="utf-8"))
    for record in manifest["videos"]:
        path = tmp_path / record["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        with av.open(str(path)) as container:
            frames = list(container.decode(video=0))
            assert len(frames) == record["frame_count"]
            assert [str(frame.pts * frame.time_base) for frame in frames] == record["pts_seconds"]
            assert [
                hashlib.sha256(frame.to_ndarray(format="rgb24").tobytes()).hexdigest()
                for frame in frames
            ] == record["rgb_sha256"]


def test_repeated_pts_keep_ordinals_and_report_effective_uniform_budget(
    tmp_path: Path, processor_dir: Path, reference: Any
) -> None:
    path = tmp_path / "repeated-pts.mkv"
    write_video(path, pts=(0, 0, 500, 500))
    actual = inspect(path, processor_dir, sampling="uniform", frames=4)
    assert actual.manifest.source_frame_count == 4
    assert actual.manifest.requested_frames == 4
    assert actual.manifest.selected_frame_count == 2
    assert [frame.ordinal for frame in actual.manifest.selected_frames] == [0, 2]
    assert [frame.timestamp_seconds for frame in actual.manifest.selected_frames] == [0.0, 0.5]
    assert actual.manifest.processed_frame_count == 2
    assert actual.warnings or actual.manifest.warnings
    np = importlib.import_module("numpy")
    video_utils = importlib.import_module("transformers.video_utils")
    expected = reference(
        videos=[np.stack([frame_rgb(0), frame_rgb(2)])],
        text=[reference_prompt(reference, "video")],
        video_metadata=[
            video_utils.VideoMetadata(total_num_frames=4, fps=2.0, frames_indices=[0, 2])
        ],
        do_sample_frames=False,
        return_tensors="pt",
    )
    assert actual.grid_thw == expected["video_grid_thw"][0].tolist()
    assert_token_evidence(actual.token_accounting, expected, reference)


def test_offline_cached_rerun_retains_deterministic_observations(
    tmp_path: Path, processor_dir: Path
) -> None:
    path = tmp_path / "repeat.png"
    write_image(path, width=160, height=96)
    first = inspect(path, processor_dir)
    second = inspect(path, processor_dir)
    assert first.run_id != second.run_id
    assert first.manifest == second.manifest
    assert first.grid_thw == second.grid_thw
    assert first.token_accounting == second.token_accounting
    assert first.processor == second.processor
    assert first.prompt_sha256 == second.prompt_sha256
    assert first.template_sha256 == second.template_sha256
