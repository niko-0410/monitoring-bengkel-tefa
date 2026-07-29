#!/bin/bash
RELEASE_TAG="${1:-models-v1}"
REPO="niko-0410/monitoring-bengkel-tefa"
BASE_URL="https://github.com/$REPO/releases/download/$RELEASE_TAG"
MODELS_DIR="$(dirname "$0")/models"
FILES=("apd_custom_best.pt" "ppe_6class.onnx" "ppe_6class.pt")

mkdir -p "$MODELS_DIR"

for file in "${FILES[@]}"; do
    url="$BASE_URL/$file"
    out="$MODELS_DIR/$file"
    echo "Downloading $file ..."
    if curl -sL "$url" -o "$out"; then
        echo "  OK -> $out"
    else
        echo "  GAGAL: $file" >&2
    fi
done

echo ""
echo "Selesai. Jalankan ulang aplikasi."
