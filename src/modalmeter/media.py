"""Bounded local media decoding and reproducible frame selection.

PyAV and Pillow are imported only while loading the corresponding media. The
video path scans metadata with one decoded frame in memory, then materializes
only selected RGB frames in a second pass. Decoder time limits are cooperative
between frames; they do not interrupt a native codec call.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import math
import time
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, BinaryIO

from modalmeter.errors import InvalidInput, MissingExtra
from modalmeter.schemas import (
    InspectionConfig,
    MediaManifest,
    ProcessedFrame,
    SourceFrame,
)

_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"}


@dataclass(frozen=True)
class LoadedMedia:
    """Transient decoded content and its serializable provenance."""

    manifest: MediaManifest
    content: Any
    thumbnails: list[str]


@dataclass(frozen=True)
class _Scan:
    frames: list[SourceFrame]
    width: int
    height: int
    reported_count: int | None
    duration: float | None
    fps: float
    warnings: list[str]
    versions: dict[str, str]


def _optional_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise MissingExtra(
            "Media inspection requires the inspect extra. Install 'modalmeter[inspect]' "
            "or run 'uv sync --extra inspect'."
        ) from exc


def _check_deadline(start: float, limit: float) -> None:
    if time.monotonic() - start > limit:
        raise InvalidInput(
            f"Media decoding exceeded max_decode_seconds={limit:g}. "
            "Use a shorter input or explicitly increase the limit."
        )


def _check_dimensions(width: int, height: int, config: InspectionConfig) -> None:
    if width < 1 or height < 1:
        raise InvalidInput("Media has missing or invalid dimensions.")
    if width * height > config.max_pixels:
        raise InvalidInput(
            f"Decoded frame dimensions {width}x{height} exceed max_pixels="
            f"{config.max_pixels}. Use smaller media or explicitly increase the limit."
        )


def _source_hash(handle: BinaryIO, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    while chunk := handle.read(min(1024 * 1024, limit + 1 - total)):
        total += len(chunk)
        if total > limit:
            raise InvalidInput(f"Input exceeds max_file_bytes={limit}.")
        digest.update(chunk)
    handle.seek(0)
    if not total:
        raise InvalidInput("Input file is empty.")
    return digest.hexdigest(), total


def uniform_frame_indices(timestamps: Sequence[Fraction], count: int) -> list[int]:
    """Select nearest rational PTS targets; exact ties favor the earlier frame.

    Targets span the first and last PTS inclusively. A single target is the
    first frame. The target count is capped at the number of decoded frames,
    and repeated nearest matches are de-duplicated in presentation order.
    """
    if count < 1:
        raise InvalidInput("Uniform sampling requires a positive frame count.")
    if not timestamps:
        raise InvalidInput("Video contains no decoded frames.")
    if any(right < left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise InvalidInput("Decoded presentation timestamps are not monotonic.")
    target_count = min(count, len(timestamps))
    if target_count == 1:
        return [0]
    span = timestamps[-1] - timestamps[0]
    selected: list[int] = []
    for position in range(target_count):
        target = timestamps[0] + span * Fraction(position, target_count - 1)
        index = min(
            range(len(timestamps)),
            key=lambda candidate: (
                abs(timestamps[candidate] - target),
                timestamps[candidate],
                candidate,
            ),
        )
        if not selected or selected[-1] != index:
            selected.append(index)
    return selected


def processed_frame_mapping(indices: Sequence[int]) -> list[ProcessedFrame]:
    """Record the pinned temporal-patch-size-two replication convention."""
    if not indices:
        raise InvalidInput("At least one frame must be selected.")
    seen: set[int] = set()
    result: list[ProcessedFrame] = []
    for position, ordinal in enumerate(indices):
        duplicate = ordinal in seen
        result.append(
            ProcessedFrame(
                position=position,
                selected_position=position,
                source_ordinal=ordinal,
                duplicated=duplicate,
                duplication_reason="sampling_repeat" if duplicate else None,
            )
        )
        seen.add(ordinal)
    if len(indices) % 2:
        result.append(
            ProcessedFrame(
                position=len(indices),
                selected_position=len(indices) - 1,
                source_ordinal=indices[-1],
                duplicated=True,
                duplication_reason=(
                    "single_frame_adapter_padding_before_native_resize"
                    if len(indices) == 1
                    else "native_temporal_padding"
                ),
            )
        )
    return result


def _thumbnail(image: Any) -> str:
    preview = image.copy()
    preview.thumbnail((240, 160))
    buffer = io.BytesIO()
    preview.save(buffer, format="PNG", optimize=False)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _load_image(
    handle: BinaryIO, config: InspectionConfig, digest: str, source_bytes: int, started: float
) -> LoadedMedia:
    image_module = _optional_module("PIL.Image")
    image_ops = _optional_module("PIL.ImageOps")
    pillow = _optional_module("PIL")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", image_module.DecompressionBombWarning)
            with image_module.open(handle) as image:
                width, height = image.size
                _check_dimensions(width, height, config)
                # Decoded source, oriented copy, and RGB result can coexist.
                if width * height * 16 > config.max_decoded_bytes:
                    raise InvalidInput("Image working memory exceeds max_decoded_bytes.")
                if getattr(image, "n_frames", 1) != 1:
                    raise InvalidInput(
                        "Animated images are unsupported; use a still image or video."
                    )
                source_mode = str(image.mode)
                orientation = image.getexif().get(274, 1)
                if type(orientation) is not int or orientation not in range(1, 9):
                    raise InvalidInput(
                        "Unsupported EXIF orientation; expected an integer from 1 to 8. "
                        "Correct the orientation metadata or export a valid still image."
                    )
                image.load()
                _check_deadline(started, config.max_decode_seconds)
                oriented = image_ops.exif_transpose(image)
                content = oriented.convert("RGB")
                transforms = [f"EXIF orientation {orientation} applied"] if orientation != 1 else []
                if source_mode != "RGB":
                    transforms.append(
                        f"{source_mode} to RGB via Pillow.convert (no color profile conversion)"
                    )
                oriented_width, oriented_height = content.size
    except InvalidInput:
        raise
    except Exception as exc:
        raise InvalidInput(f"Cannot decode image: {type(exc).__name__}.") from exc
    frame = SourceFrame(
        ordinal=0,
        pts=None,
        time_base_numerator=None,
        time_base_denominator=None,
        timestamp_seconds=None,
        timestamp_unavailable_reason="Still images have no presentation timestamp.",
        processor_timestamp_seconds=None,
    )
    manifest = MediaManifest(
        kind="image",
        sha256=digest,
        display_name="image",
        source_bytes=source_bytes,
        source_width=width,
        source_height=height,
        oriented_width=oriented_width,
        oriented_height=oriented_height,
        source_mode=source_mode,
        transforms=transforms,
        source_frame_count=1,
        reported_frame_count=None,
        source_duration_seconds=None,
        source_duration_reason="Still images have no duration.",
        average_fps=None,
        fps_reason="Still images have no frame rate.",
        selected_frames=[frame],
        requested_frames=None,
        selected_frame_count=1,
        processed_frame_count=1,
        processed_frames=[
            ProcessedFrame(
                position=0,
                selected_position=0,
                source_ordinal=0,
                duplicated=False,
                duplication_reason=None,
            )
        ],
        sampling_policy="not_applicable",
        sampling_method="One still image; no frame sampling.",
        timestamp_policy="Not applicable to still images.",
        warnings=[],
        decoder_versions={"Pillow": str(pillow.__version__)},
        privacy_mode="media_included" if config.include_media else "sanitized",
    )
    return LoadedMedia(manifest, content, [_thumbnail(content)] if config.include_media else [])


def _frame_identity(frame: Any, ordinal: int, fps: float) -> SourceFrame:
    if frame.pts is None or frame.time_base is None:
        raise InvalidInput(
            "Video has missing decoded PTS/time base. This adapter requires actual "
            "presentation timestamps; re-encode with valid timestamps."
        )
    time_base = Fraction(frame.time_base)
    if time_base <= 0:
        raise InvalidInput("Video has an invalid decoded time base.")
    timestamp = int(frame.pts) * time_base
    return SourceFrame(
        ordinal=ordinal,
        pts=int(frame.pts),
        time_base_numerator=time_base.numerator,
        time_base_denominator=time_base.denominator,
        timestamp_seconds=float(timestamp),
        timestamp_unavailable_reason=None,
        processor_timestamp_seconds=ordinal / fps,
    )


def _rational_timestamp(frame: SourceFrame) -> Fraction:
    if (
        frame.pts is None
        or frame.time_base_numerator is None
        or frame.time_base_denominator is None
    ):
        raise InvalidInput("Actual rational presentation timestamps are required for sampling.")
    return frame.pts * Fraction(frame.time_base_numerator, frame.time_base_denominator)


def _scan_video(handle: BinaryIO, config: InspectionConfig, started: float) -> _Scan:
    av = _optional_module("av")
    observations: list[SourceFrame] = []
    notes = [
        "Decoder runtime is checked between frames; native codec calls cannot be interrupted.",
        "Memory limit bounds selected RGB arrays plus explicit frame workspace; codec buffers "
        "and later processor tensors are outside this decoder allocation bound.",
    ]
    with av.open(handle, mode="r") as container:
        if not container.streams.video:
            raise InvalidInput("Input contains no video stream.")
        stream = container.streams.video[0]
        # Avoid unconstrained codec thread buffers in this laptop inspection path.
        stream.thread_count = 1
        width, height = int(stream.codec_context.width), int(stream.codec_context.height)
        _check_dimensions(width, height, config)
        if width * height * 9 > config.max_decoded_bytes:
            raise InvalidInput("Video frame working memory exceeds max_decoded_bytes.")
        reported_count = int(stream.frames) if stream.frames and stream.frames > 0 else None
        if reported_count is not None and reported_count > config.max_decoded_frames:
            raise InvalidInput(
                "Reported video length exceeds max_decoded_frames; use a shorter clip."
            )
        if stream.average_rate is None:
            raise InvalidInput(
                "Video has no average FPS metadata. This processor requires nominal FPS for "
                "its index/FPS prompt timestamps; re-encode with explicit frame-rate metadata."
            )
        fps = float(stream.average_rate)
        if not math.isfinite(fps) or fps <= 0:
            raise InvalidInput("Video has invalid average FPS metadata.")
        duration = (
            float(stream.duration * stream.time_base)
            if stream.duration is not None and stream.time_base is not None and stream.duration > 0
            else None
        )
        for ordinal, frame in enumerate(container.decode(stream)):
            _check_deadline(started, config.max_decode_seconds)
            if ordinal >= config.max_decoded_frames:
                raise InvalidInput(
                    "Decoded video length exceeds max_decoded_frames; use a shorter clip."
                )
            _check_dimensions(int(frame.width), int(frame.height), config)
            if frame.width != width or frame.height != height:
                raise InvalidInput(
                    "Video changes dimensions midstream; constant frame dimensions are required."
                )
            observations.append(_frame_identity(frame, ordinal, fps))
    if not observations:
        raise InvalidInput("Video contains no decoded frames.")
    actual_times = [_rational_timestamp(frame) for frame in observations]
    if any(right < left for left, right in zip(actual_times, actual_times[1:], strict=False)):
        raise InvalidInput("Decoded presentation timestamps are not monotonic.")
    intervals = {right - left for left, right in zip(actual_times, actual_times[1:], strict=False)}
    if len(intervals) > 1:
        notes.append(
            "Variable presentation intervals observed; processor index/FPS timestamps "
            "differ from actual PTS."
        )
    if actual_times[0] != 0:
        notes.append(
            "Nonzero PTS origin is preserved; processor index/FPS timestamps "
            "start at decoded ordinal zero."
        )
    if reported_count is None:
        notes.append(
            "Container frame count is unavailable; source_frame_count is the "
            "complete decoded count."
        )
    elif reported_count != len(observations):
        notes.append(
            "Container frame count differs from the complete decoded count; "
            "decoded count is authoritative."
        )
    if any(
        abs(float(actual) - frame.ordinal / fps) > 0.001
        for actual, frame in zip(actual_times, observations, strict=True)
    ):
        notes.append(
            "Actual decoded PTS are retained separately; native prompt timestamp labels "
            "use ordinal / nominal FPS."
        )
    versions = {"PyAV": str(av.__version__)}
    versions.update(
        {f"FFmpeg {key}": ".".join(map(str, value)) for key, value in av.library_versions.items()}
    )
    return _Scan(observations, width, height, reported_count, duration, fps, notes, versions)


def _load_video(
    handle: BinaryIO,
    config: InspectionConfig,
    digest: str,
    source_bytes: int,
    started: float,
    default_frame_indices: Callable[[int, float], list[int]] | None,
) -> LoadedMedia:
    av = _optional_module("av")
    np = _optional_module("numpy")
    try:
        scan = _scan_video(handle, config, started)
        if config.sampling == "uniform":
            if config.frames is None:
                raise InvalidInput("Uniform sampling requires --frames.")
            indices = uniform_frame_indices(
                [_rational_timestamp(frame) for frame in scan.frames], config.frames
            )
            method = (
                "Inclusive rational PTS targets, nearest frame; ties choose earlier PTS then "
                "ordinal; de-duplicate targets; one target selects the first frame."
            )
        else:
            if default_frame_indices is None:
                raise InvalidInput(
                    "Model-default video sampling requires the pinned processor sampling function."
                )
            indices = default_frame_indices(len(scan.frames), scan.fps)
            method = (
                "Pinned Qwen3VLVideoProcessor.sample_frames over complete decoded count "
                "and nominal FPS."
            )
        if not indices or any(
            type(index) is not int or index < 0 or index >= len(scan.frames) for index in indices
        ):
            raise InvalidInput("Processor sampling returned empty or invalid source frame indices.")
        if indices != sorted(indices):
            raise InvalidInput("Processor sampling returned nonmonotonic source frame indices.")
        mapping = processed_frame_mapping(indices)
        if len(mapping) > config.max_frames:
            raise InvalidInput(
                "Selected frames including temporal padding exceed "
                f"max_frames={config.max_frames}. "
                "Use uniform sampling with fewer frames or explicitly increase the limit."
            )
        materialized_count = 2 if len(indices) == 1 else len(indices)
        frame_bytes = scan.width * scan.height * 3
        # Final array plus two RGB-sized workspaces; decode scan holds no RGB list.
        if (materialized_count + 2) * frame_bytes > config.max_decoded_bytes:
            raise InvalidInput("Selected RGB video and frame workspace exceed max_decoded_bytes.")
        content = np.empty((materialized_count, scan.height, scan.width, 3), dtype=np.uint8)
        positions: dict[int, list[int]] = {}
        for position, ordinal in enumerate(indices):
            positions.setdefault(ordinal, []).append(position)
        handle.seek(0)
        found: set[int] = set()
        with av.open(handle, mode="r") as container:
            stream = container.streams.video[0]
            stream.thread_count = 1
            for ordinal, frame in enumerate(container.decode(stream)):
                _check_deadline(started, config.max_decode_seconds)
                if ordinal > indices[-1]:
                    break
                if ordinal not in positions:
                    continue
                if frame.width != scan.width or frame.height != scan.height:
                    raise InvalidInput(
                        "Video dimensions changed between metadata and selected-frame passes."
                    )
                if _frame_identity(frame, ordinal, scan.fps) != scan.frames[ordinal]:
                    raise InvalidInput("Video timestamp identity changed between decode passes.")
                array = frame.to_ndarray(format="rgb24")
                for position in positions[ordinal]:
                    content[position] = array
                found.add(ordinal)
        if found != set(indices):
            raise InvalidInput("Selected video frames were unavailable on the second decode pass.")
        if len(indices) == 1:
            content[1] = content[0]
            scan.warnings.append(
                "One selected frame is replicated before native resize; selected=1, processed=2."
            )
        selected = [scan.frames[index] for index in indices]
        thumbs = []
        if config.include_media:
            image_module = _optional_module("PIL.Image")
            thumbs = [
                _thumbnail(image_module.fromarray(content[index])) for index in range(len(indices))
            ]
        manifest = MediaManifest(
            kind="video",
            sha256=digest,
            display_name="video",
            source_bytes=source_bytes,
            source_width=scan.width,
            source_height=scan.height,
            oriented_width=scan.width,
            oriented_height=scan.height,
            source_mode=None,
            transforms=["PyAV decoded selected frames to RGB24; no decoder resize."],
            source_frame_count=len(scan.frames),
            reported_frame_count=scan.reported_count,
            source_duration_seconds=scan.duration,
            source_duration_reason="Video stream duration metadata is unavailable."
            if scan.duration is None
            else None,
            average_fps=scan.fps,
            fps_reason=None,
            selected_frames=selected,
            requested_frames=config.frames,
            selected_frame_count=len(indices),
            processed_frame_count=len(mapping),
            processed_frames=mapping,
            sampling_policy=config.sampling,
            sampling_method=method,
            timestamp_policy=(
                "Actual rational PTS preserved separately from derived ordinal / nominal FPS "
                "processor timestamps."
            ),
            warnings=scan.warnings,
            decoder_versions=scan.versions,
            privacy_mode="media_included" if config.include_media else "sanitized",
        )
        return LoadedMedia(manifest, content, thumbs)
    except (InvalidInput, MissingExtra):
        raise
    except Exception as exc:
        raise InvalidInput(f"Cannot decode video: {type(exc).__name__}.") from exc


def load_media(
    config: InspectionConfig,
    *,
    default_frame_indices: Callable[[int, float], list[int]] | None = None,
) -> LoadedMedia:
    """Load a local still image or supported-extension video with explicit limits."""
    path: Path = config.path
    if not path.is_file():
        raise InvalidInput("Input must be an existing local regular file.")
    if path.stat().st_size > config.max_file_bytes:
        raise InvalidInput(f"Input exceeds max_file_bytes={config.max_file_bytes}.")
    is_video = path.suffix.lower() in _VIDEO_SUFFIXES
    if config.frames is not None and config.frames > config.max_frames:
        raise InvalidInput(f"Requested frames exceed max_frames={config.max_frames}.")
    if not is_video and (config.frames is not None or config.sampling != "model-default"):
        raise InvalidInput("Frame sampling options apply only to video input.")
    started = time.monotonic()
    try:
        # An unbuffered handle makes the final identity read observe on-disk
        # changes rather than a previously filled Python read buffer.
        with path.open("rb", buffering=0) as handle:
            digest, source_bytes = _source_hash(handle, config.max_file_bytes)
            _check_deadline(started, config.max_decode_seconds)
            if is_video:
                loaded = _load_video(
                    handle, config, digest, source_bytes, started, default_frame_indices
                )
            else:
                loaded = _load_image(handle, config, digest, source_bytes, started)
            handle.seek(0)
            final_digest, final_size = _source_hash(handle, config.max_file_bytes)
            if (final_digest, final_size) != (digest, source_bytes):
                raise InvalidInput(
                    "Source media changed during decoding; retry with an unchanged file."
                )
            _check_deadline(started, config.max_decode_seconds)
            return loaded
    except OSError as exc:
        raise InvalidInput(f"Cannot read local media: {type(exc).__name__}.") from exc
