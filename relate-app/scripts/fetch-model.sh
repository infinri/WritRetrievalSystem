#!/bin/sh
# Download the pinned public embedding model (Apache-2.0) and verify exact bytes.
# Requires only curl (or wget) and sha256sum. No Python.
# Usage: scripts/fetch-model.sh [DEST_DIR]   (default: ./model)
set -eu
DEST="${1:-model}"
REPO="sentence-transformers/all-MiniLM-L6-v2"
REV="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
BASE="https://huggingface.co/$REPO/resolve/$REV"
mkdir -p "$DEST"
fetch() { # remote local sha256
  if [ -f "$DEST/$2" ] && echo "$3  $DEST/$2" | sha256sum -c --status; then return 0; fi
  if command -v curl >/dev/null 2>&1; then curl -fsSL -o "$DEST/$2.part" "$BASE/$1"; else wget -q -O "$DEST/$2.part" "$BASE/$1"; fi
  echo "$3  $DEST/$2.part" | sha256sum -c --status || { echo "hash mismatch for $2" >&2; rm -f "$DEST/$2.part"; exit 1; }
  mv "$DEST/$2.part" "$DEST/$2"
}
fetch onnx/model.onnx model.onnx 6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452
fetch tokenizer.json tokenizer.json be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037
fetch README.md MODEL-README.md dcd602d2fd35c203a247304a06fec6654a12f7941b739f9221a064fe8dc3b7f0
echo "model ready in $DEST ($REPO@$REV, Apache-2.0)"
