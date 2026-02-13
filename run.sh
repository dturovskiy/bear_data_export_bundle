#!/usr/bin/env bash
# run.sh — creates venv (if needed), installs deps, and runs the exporter.
# Usage: ./run.sh --symbols BTCUSDT BNBUSDT --intervals 1h 4h --days 180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

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
