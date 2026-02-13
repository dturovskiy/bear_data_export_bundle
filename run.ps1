<# run.ps1 — creates venv (if needed), installs deps, and runs the exporter.
   Usage: .\run.ps1 --symbols BTCUSDT BNBUSDT --intervals 1h 4h --days 180 #>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir   = Join-Path $ScriptDir ".venv"

# 1) Create venv if it doesn't exist
if (-not (Test-Path $VenvDir)) {
    Write-Host "⏳ Creating virtual environment…"
    python -m venv $VenvDir
}

# 2) Install / update deps
Write-Host "📦 Installing dependencies…"
& "$VenvDir\Scripts\pip.exe" install --quiet --upgrade pip
& "$VenvDir\Scripts\pip.exe" install --quiet -r (Join-Path $ScriptDir "requirements.txt")

# 3) Run the exporter, forwarding all arguments
Write-Host "🚀 Starting exporter…"
& "$VenvDir\Scripts\python.exe" (Join-Path $ScriptDir "binance_ohlcv_exporter.py") @args
