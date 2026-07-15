#!/bin/bash
# RPGM-Translator - macOS/Linux Launcher

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v uv &>/dev/null; then
    echo "[RPGM-Translator] uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv &>/dev/null; then
    echo "[RPGM-Translator] ERROR: uv installation failed."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[RPGM-Translator] Starting..."
cd "$SCRIPT_DIR"
export UV_LINK_MODE=copy
PYTHON_BIN=$(command -v python3 || command -v python)
uv run --python "$PYTHON_BIN" rpgm_tool.py "$@"
