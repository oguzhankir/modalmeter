"""Offline selection contracts and explicitly enabled local decoder integration."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from modalmeter import media
from modalmeter.errors import InvalidInput
from modalmeter.media import load_media, processed_frame_mapping, uniform_frame_indices
from modalmeter.schemas import InspectionConfig


def test_uniform_sampling_uses_actual_pts_and_earlier_ties() -> None:
    # Targets 0, 1.5, 3 select ordinal one at the exact midpoint tie.
    assert uniform_frame_indices(list(map(Fraction, [0, 1, 2, 3])), 3) == [0, 1, 3]
    # VFR nearest neighbors differ from ordinal-based linspace selection.
    assert uniform_frame_indices(list(map(Fraction, [0, 1, 2, 10, 11])), 3) == [0, 2, 4]
    # A PTS origin shift changes no identities, including at sub-millisecond precision.
    pts = [Fraction(2), Fraction(2001, 1000), Fraction(3)]
    assert uniform_frame_indices(pts, 3) == [0, 1, 2]


def test_uniform_sampling_preserves_selected_count_when_targets_repeat() -> None:
    assert uniform_frame_indices(list(map(Fraction, [0, 1, 2, 100])), 4) == [0, 2, 3]
    assert uniform_frame_indices([Fraction(5)], 8) == [0]
    assert uniform_frame_indices(list(map(Fraction, [4, 5, 6])), 1) == [0]
    assert uniform_frame_indices([Fraction(1), Fraction(1)], 2) == [0]


@pytest.mark.parametrize(
    "pts,count", [([], 1), ([Fraction(1)], 0), ([Fraction(2), Fraction(1)], 2)]
)
def test_uniform_sampling_rejects_invalid_time_domain(pts: list[Fraction], count: int) -> None:
    with pytest.raises(InvalidInput):
        uniform_frame_indices(pts, count)


def test_padding_preserves_frame_identity_and_duplication_origin() -> None:
    odd = processed_frame_mapping([1, 5, 9])
    assert [(item.source_ordinal, item.selected_position) for item in odd] == [
        (1, 0),
        (5, 1),
        (9, 2),
        (9, 2),
    ]
    assert odd[-1].duplication_reason == "native_temporal_padding"
    single = processed_frame_mapping([8])
    assert single[-1].duplication_reason == "single_frame_adapter_padding_before_native_resize"
    repeated = processed_frame_mapping([0, 0])
    assert repeated[-1].duplication_reason == "sampling_repeat"
    assert repeated[0].duplicated is False


def test_missing_timestamp_is_rejected_instead_of_manufactured() -> None:
    frame = SimpleNamespace(pts=None, time_base=Fraction(1, 1000))
    with pytest.raises(InvalidInput, match="missing decoded PTS"):
        media._frame_identity(frame, 0, 2.0)


def test_file_validation_precedes_optional_dependency_import(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput, match="existing local regular file"):
        load_media(InspectionConfig(path=tmp_path / "absent.mp4"))
    path = tmp_path / "private-name.png"
    path.write_bytes(b"too long")
    with pytest.raises(InvalidInput, match="max_file_bytes"):
        load_media(InspectionConfig(path=path, max_file_bytes=1))
    path.write_bytes(b"")
    with pytest.raises(InvalidInput, match="empty"):
        load_media(InspectionConfig(path=path))


def _fake_av(frames: list[Any], *, fps: Fraction | None = Fraction(2)) -> Any:
    stream = SimpleNamespace(
        codec_context=SimpleNamespace(width=96, height=64),
        frames=0,
        average_rate=fps,
        duration=None,
        time_base=Fraction(1, 1000),
    )

    class Container:
        def __enter__(self) -> Container:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        streams = SimpleNamespace(video=[stream])

        def decode(self, video_stream: Any) -> Any:
            return iter(frames)

    return SimpleNamespace(
        open=lambda *args, **kwargs: Container(), __version__="test", library_versions={}
    )


def test_missing_fps_is_rejected_without_default24(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _fake_av([], fps=None)
    monkeypatch.setattr(media, "_optional_module", lambda name: fake)
    with pytest.raises(InvalidInput, match="no average FPS metadata"):
        media._scan_video(io.BytesIO(), InspectionConfig(path=tmp_path), time.monotonic())


def test_scan_runtime_and_frame_limit_have_explicit_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames = [
        SimpleNamespace(width=96, height=64, pts=index * 500, time_base=Fraction(1, 1000))
        for index in range(3)
    ]
    fake = _fake_av(frames)
    monkeypatch.setattr(media, "_optional_module", lambda name: fake)
    with pytest.raises(InvalidInput, match="max_decoded_frames"):
        media._scan_video(
            io.BytesIO(),
            InspectionConfig(path=tmp_path, max_decoded_frames=2),
            time.monotonic(),
        )
    monkeypatch.setattr(time, "monotonic", lambda: 2.0)
    with pytest.raises(InvalidInput, match="max_decode_seconds"):
        media._scan_video(io.BytesIO(), InspectionConfig(path=tmp_path, max_decode_seconds=1), 0.0)


def _fixture_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "modalmeter_synthetic_media", Path(__file__).parents[1] / "examples/generate_fixtures.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.processor
def test_image_exif_rgb_hash_privacy_and_limits(tmp_path: Path) -> None:
    image_module = importlib.import_module("PIL.Image")
    source = image_module.new("L", (64, 96), 180)
    exif = image_module.Exif()
    exif[274] = 6
    path = tmp_path / "private-photo.png"
    source.save(path, exif=exif)
    loaded = load_media(InspectionConfig(path=path))
    assert loaded.content.size == (96, 64)
    assert loaded.content.mode == "RGB"
    assert loaded.manifest.source_width == 64
    assert loaded.manifest.source_height == 96
    assert loaded.manifest.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert loaded.manifest.source_mode == "L"
    assert any("EXIF orientation 6" in transform for transform in loaded.manifest.transforms)
    assert "private-photo" not in loaded.manifest.model_dump_json()
    assert loaded.thumbnails == []
    with pytest.raises(InvalidInput, match="max_pixels"):
        load_media(InspectionConfig(path=path, max_pixels=100))
    with pytest.raises(InvalidInput, match="working memory"):
        load_media(InspectionConfig(path=path, max_decoded_bytes=100))
    public = load_media(InspectionConfig(path=path, include_media=True))
    assert public.thumbnails[0].startswith("data:image/png;base64,")


@pytest.mark.processor
def test_unsupported_exif_orientation_is_rejected_without_claiming_a_transform(
    tmp_path: Path,
) -> None:
    image_module = importlib.import_module("PIL.Image")
    path = tmp_path / "invalid-orientation.png"
    image = image_module.new("RGB", (96, 64), (40, 100, 160))
    exif = image_module.Exif()
    exif[274] = 0  # Pillow ignores this invalid value instead of applying a transform.
    image.save(path, exif=exif)
    with pytest.raises(InvalidInput, match="Unsupported EXIF orientation"):
        load_media(InspectionConfig(path=path))


@pytest.mark.processor
def test_concurrent_source_change_cannot_keep_the_original_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "changing.png"
    _fixture_module().write_image(path)
    original_thumbnail = media._thumbnail

    def mutate_after_decoding(image: Any) -> str:
        result = original_thumbnail(image)
        path.write_bytes(b"changed while the image was being decoded")
        return result

    monkeypatch.setattr(media, "_thumbnail", mutate_after_decoding)
    with pytest.raises(InvalidInput, match="Source media changed"):
        load_media(InspectionConfig(path=path, include_media=True))


@pytest.mark.processor
def test_video_pts_selected_pixels_and_native_padding(tmp_path: Path) -> None:
    fixtures = _fixture_module()
    np = importlib.import_module("numpy")
    path = tmp_path / "clip.mkv"
    fixtures.write_video(path, pts=(2000, 2120, 2530, 3100, 3900), rate=Fraction(5, 2))
    loaded = load_media(
        InspectionConfig(path=path, sampling="uniform", frames=3, include_media=True)
    )
    assert [frame.ordinal for frame in loaded.manifest.selected_frames] == [0, 3, 4]
    assert [frame.timestamp_seconds for frame in loaded.manifest.selected_frames] == [2.0, 3.1, 3.9]
    assert [frame.processor_timestamp_seconds for frame in loaded.manifest.selected_frames] == [
        0,
        1.2,
        1.6,
    ]
    assert loaded.manifest.selected_frame_count == 3
    assert loaded.manifest.processed_frame_count == 4
    assert loaded.content.shape == (3, 64, 96, 3)
    assert len(loaded.thumbnails) == 3
    assert loaded.manifest.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert any("Variable presentation" in warning for warning in loaded.manifest.warnings)
    for position, ordinal in enumerate([0, 3, 4]):
        np.testing.assert_array_equal(loaded.content[position], fixtures.frame_rgb(ordinal))


@pytest.mark.processor
def test_single_frame_is_deliberately_replicated_before_native_resize(tmp_path: Path) -> None:
    fixtures = _fixture_module()
    np = importlib.import_module("numpy")
    path = tmp_path / "single.mkv"
    fixtures.write_video(path, pts=(0,))
    loaded = load_media(InspectionConfig(path=path, sampling="uniform", frames=8))
    assert loaded.manifest.requested_frames == 8
    assert loaded.manifest.selected_frame_count == 1
    assert loaded.manifest.processed_frame_count == 2
    assert loaded.content.shape[0] == 2
    np.testing.assert_array_equal(loaded.content[0], loaded.content[1])


@pytest.mark.processor
def test_model_default_delegates_actual_metadata_and_preserves_repeats(tmp_path: Path) -> None:
    fixtures = _fixture_module()
    path = tmp_path / "default.mkv"
    fixtures.write_video(path, rate=Fraction(5, 2))
    calls: list[tuple[int, float]] = []

    def sample(count: int, fps: float) -> list[int]:
        calls.append((count, fps))
        return [1, 1]

    loaded = load_media(InspectionConfig(path=path), default_frame_indices=sample)
    assert calls == [(4, 2.5)]
    assert [frame.ordinal for frame in loaded.manifest.selected_frames] == [1, 1]
    assert loaded.manifest.processed_frames[1].duplication_reason == "sampling_repeat"
    with pytest.raises(InvalidInput, match="requires the pinned processor"):
        load_media(InspectionConfig(path=path))
    with pytest.raises(InvalidInput, match="invalid source frame indices"):
        load_media(InspectionConfig(path=path), default_frame_indices=lambda count, fps: [count])


@pytest.mark.processor
def test_video_caps_bound_materialized_pixels_and_scan(tmp_path: Path) -> None:
    fixtures = _fixture_module()
    path = tmp_path / "bounded.mkv"
    fixtures.write_video(path, pts=tuple(index * 500 for index in range(20)))
    # Two retained frames plus two workspaces fit; materializing all 20 does not.
    loaded = load_media(
        InspectionConfig(
            path=path,
            sampling="uniform",
            frames=2,
            max_decoded_bytes=96 * 64 * 3 * 4,
        )
    )
    assert loaded.content.shape[0] == 2
    assert loaded.manifest.source_frame_count == 20
    with pytest.raises(InvalidInput, match="max_decoded_frames"):
        load_media(InspectionConfig(path=path, sampling="uniform", frames=2, max_decoded_frames=3))
    with pytest.raises(InvalidInput, match="max_frames"):
        load_media(
            InspectionConfig(path=path, max_frames=2),
            default_frame_indices=lambda count, fps: [0, 1, 2],
        )
    with pytest.raises(InvalidInput, match="Selected RGB video"):
        load_media(
            InspectionConfig(
                path=path,
                sampling="uniform",
                frames=4,
                max_decoded_bytes=96 * 64 * 3 * 4,
            )
        )


@pytest.mark.processor
@pytest.mark.parametrize("suffix", [".png", ".mkv"])
def test_corrupt_media_fails_without_leaking_filename(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / ("secret-account-name" + suffix)
    path.write_bytes(b"this is not encoded media")
    with pytest.raises(InvalidInput, match="Cannot decode") as exc:
        load_media(InspectionConfig(path=path))
    assert "secret-account-name" not in str(exc.value)
