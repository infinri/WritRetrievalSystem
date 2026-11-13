"""Fetch a pinned public MiniLM ONNX export; no PyTorch or export tooling needed.

This is the same model family as V1, not the original maintainer's unversioned
local export. Its numerical equivalence to that export has not been established.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EXPECTED_SHA256 = {
    "model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    "MODEL-README.md": "dcd602d2fd35c203a247304a06fec6654a12f7941b739f9221a064fe8dc3b7f0",
}
FILES = {"model.onnx": "onnx/model.onnx", "tokenizer.json": "tokenizer.json", "MODEL-README.md": "README.md"}


def prepare(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for local, remote in FILES.items():
        url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{remote}"
        target = output / local
        temp = target.with_suffix(target.suffix + ".download")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as dest:
                while chunk := response.read(1024 * 1024):
                    dest.write(chunk)
            digest = hashlib.sha256(temp.read_bytes()).hexdigest()
            if digest != EXPECTED_SHA256[local]:
                raise ValueError(f"SHA-256 mismatch for {local}")
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        hashes[local] = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f"{local}: {hashes[local]}", flush=True)
    manifest = {"model": MODEL, "revision": REVISION, "license": "Apache-2.0", "sha256": hashes}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/model"))
    prepare(parser.parse_args().output)
