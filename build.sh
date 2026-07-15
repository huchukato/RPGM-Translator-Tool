#!/bin/bash
# RPGM-Translator - local release builder
# Creates a distributable zip under dist/

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(grep -E '^version\s*=\s*"' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
PROJECT_NAME="RPGM-Translator"
RELEASE_NAME="${PROJECT_NAME}-v${VERSION}"
OUT_DIR="dist/${RELEASE_NAME}"
ZIP_FILE="dist/${RELEASE_NAME}.zip"

echo "[build] Building release ${RELEASE_NAME}..."

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

cp -r \
    pyproject.toml \
    README.md \
    start.sh \
    start.bat \
    rpgm_tool.py \
    rpgm_detector.py \
    rpgm_extractor.py \
    rpgm_parser.py \
    rpgm_writer.py \
    rpgm_translator.py \
    rpgm_settings.py \
    logo_*.png \
    splash.jpg \
    "$OUT_DIR/"

chmod +x "$OUT_DIR/start.sh"

rm -f "$ZIP_FILE"
(cd dist && zip -r "${RELEASE_NAME}.zip" "${RELEASE_NAME}")

echo "[build] Release ready: $ZIP_FILE"
