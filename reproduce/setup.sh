#!/bin/sh
# One-time POSIX setup: install uv if needed, then fetch pinned PatchDiff data.

set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"
: "${UV_CACHE_DIR:=${TMPDIR:-/tmp}/gold-signal-uv-cache}"
export UV_CACHE_DIR
mkdir -p "$UV_CACHE_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not found. Installing it from the official Astral installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    export PATH
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv installation finished but uv was not found. Open a new shell and rerun ./setup.sh."
    exit 1
fi

uv run scripts/setup_external_data.py "$@"
echo
echo "Setup complete. Run ./run_all.sh to reproduce all results."
