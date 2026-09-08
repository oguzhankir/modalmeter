"""Explicit M0-only download of the recorded processor artifacts; never weights."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--download", action="store_true", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
manifest = json.loads(Path(__file__).with_name("processor-artifacts.json").read_text())
args.output.mkdir(parents=True, exist_ok=True)
for artifact in manifest["artifacts"]:
    target = args.output / artifact["file"]
    if target.exists():
        content = target.read_bytes()
    else:
        with urllib.request.urlopen(artifact["url"], timeout=60) as response:
            content = response.read(artifact["bytes"] + 1)
    if (
        len(content) != artifact["bytes"]
        or hashlib.sha256(content).hexdigest() != artifact["sha256"]
    ):
        raise SystemExit(f"Artifact size/hash mismatch: {artifact['file']}")
    if not target.exists():
        target.write_bytes(content)
    print(f"Verified {artifact['file']}: {len(content)} bytes")
