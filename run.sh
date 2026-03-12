#!/usr/bin/env bash
# run.sh — creates venv (if needed), installs deps, and runs the exporter.
# Usage: ./run.sh --symbols BTCUSDT BNBUSDT --intervals 1h 4h --days 180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Allow override from env, otherwise default to project-local .venv
DEFAULT_VENV_DIR="$SCRIPT_DIR/.venv"
VENV_DIR="${VENV_DIR:-$DEFAULT_VENV_DIR}"

# If the project path contains ':' (GVFS sftp:host=...), venv creation will fail.
# In that case, place venv in a local cache directory with a safe path.
if [[ "$SCRIPT_DIR" == *:* ]]; then
    SAFE_BASE="${XDG_CACHE_HOME:-$HOME/.cache}/venvs"
    mkdir -p "$SAFE_BASE"

    # Use a stable name; add a short hash to avoid collisions across different paths.
    if command -v sha1sum >/dev/null 2>&1; then
        PATH_HASH="$(printf "%s" "$SCRIPT_DIR" | sha1sum | awk '{print substr($1,1,10)}')"
    else
        PATH_HASH="nohash"
    fi

    VENV_DIR="$SAFE_BASE/$(basename "$SCRIPT_DIR")-$PATH_HASH"
    echo "⚠️ Detected ':' in path ($SCRIPT_DIR). Using venv at: $VENV_DIR"
fi

# 1) Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "⏳ Creating virtual environment…"
    python3 -m venv "$VENV_DIR"
fi

# 2) Install / update deps
echo "📦 Installing dependencies…"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# 3) Run the exporter, forwarding all CLI arguments
echo "🚀 Starting exporter…"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/binance_ohlcv_exporter.py" "$@"

