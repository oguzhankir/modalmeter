"""Generate tiny, original synthetic media under the repository's MIT license.

The RGB pixels and input frame timestamps are deterministic. Matroska container
bytes can differ between encoder runs, so the manifest records the actual file
hash alongside the independently known pixel identities and presentation times.
No model, network request, or third-party media is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


def frame_rgb(ordinal: int, width: int = 96, height: int = 64) -> Any:
    """Return an RGB array with spatial variation and the ordinal in its color."""
    np = importlib.import_module("numpy")
    y, x = np.indices((height, width))
    return np.stack(
        [
            (x * 3 + ordinal * 47) % 256,
            (y * 5 + ordinal * 83) % 256,
            ((x // 8 + y // 8) * 31 + ordinal * 29) % 256,
        ],
        axis=-1,
    ).astype(np.uint8)


def write_image(path: Path, width: int = 96, height: int = 64, mode: str = "RGB") -> None:
    """Write a lossless synthetic image; PNG is the default fixture format."""
    image = importlib.import_module("PIL.Image")
    image.fromarray(frame_rgb(0, width, height)).convert(mode).save(path)


def write_video(
    path: Path,
    *,
    pts: tuple[int, ...] = (0, 500, 1000, 1500),
    time_base: Fraction = Fraction(1, 1000),
    rate: Fraction = Fraction(2, 1),
    width: int = 96,
    height: int = 64,
) -> None:
    """Write lossless FFV1 frames with explicit timestamps in a Matroska file.

    ``rate`` is the nominal stream rate. Explicit PTS can intentionally disagree
    with it to exercise VFR and nonzero-origin timestamp handling. Matroska uses
    millisecond precision; choose integer milliseconds for exact fixture PTS.
    """
    av = importlib.import_module("av")
    with av.open(str(path), mode="w", format="matroska") as container:
        stream = container.add_stream("ffv1", rate=rate)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "bgr0"
        stream.time_base = time_base
        stream.codec_context.time_base = time_base
        for ordinal, frame_pts in enumerate(pts):
            frame = av.VideoFrame.from_ndarray(frame_rgb(ordinal, width, height), format="rgb24")
            frame.pts = frame_pts
            frame.time_base = time_base
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def generate(output: Path) -> Path:
    """Write the small demo set and its known input provenance manifest."""
    output.mkdir(parents=True, exist_ok=True)
    write_image(output / "synthetic-image.png", width=160, height=96)
    cases = {
        "synthetic-video.mkv": ((0, 500, 1000, 1500, 2000, 2500), Fraction(2)),
        "coupled-budget-video.mkv": (tuple(index * 250 for index in range(16)), Fraction(4)),
        "single-frame.mkv": ((0,), Fraction(2)),
        "noninteger-fps.mkv": ((0, 400, 800, 1200, 1600), Fraction(5, 2)),
        "vfr-offset.mkv": ((2000, 2120, 2530, 3100, 3900), Fraction(5, 2)),
    }
    records: list[dict[str, Any]] = []
    for filename, (pts, rate) in cases.items():
        path = output / filename
        write_video(path, pts=pts, rate=rate)
        records.append(
            {
                "file": filename,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "codec": "ffv1",
                "width": 96,
                "height": 64,
                "nominal_fps": str(rate),
                "frame_count": len(pts),
                "frame_ordinals": list(range(len(pts))),
                "pts_seconds": [str(Fraction(value, 1000)) for value in pts],
                "rgb_sha256": [
                    hashlib.sha256(frame_rgb(ordinal).tobytes()).hexdigest()
                    for ordinal in range(len(pts))
                ],
            }
        )
    image_path = output / "synthetic-image.png"
    manifest = {
        "purpose": "Synthetic CPU inspection fixtures; no inference or serving measurements",
        "generator": "examples/generate_fixtures.py",
        "license": "MIT; original algorithmic media authored for ModalMeter",
        "container_reproducibility": "Pixels and PTS are deterministic; container bytes may vary",
        "image": {
            "file": image_path.name,
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "width": 160,
            "height": 96,
            "rgb_sha256": hashlib.sha256(frame_rgb(0, 160, 96).tobytes()).hexdigest(),
        },
        "videos": records,
    }
    target = output / "fixture-provenance.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runs/synthetic-media"))
    args = parser.parse_args()
    print(generate(args.output))


if __name__ == "__main__":
    main()
