# Binance OHLCV CSV Exporter (Spot)

A lightweight Python CLI tool that exports historical OHLCV (Open, High, Low, Close, Volume) candlestick data from the **Binance Spot** market into CSV files. Uses the public [Binance Market Data](https://data-api.binance.vision) endpoint — **no API key required**.

## Features

- Multiple symbols via CLI or text file (`--symbols-file`)
- Configurable timeframes (default: `1h`, `4h`)
- Configurable date range (default: last 180 days)
- Automatic pagination & deduplication
- Retry with exponential backoff on network errors / rate limits
- Adjustable request pause (`--sleep`)
- Progress bar (`tqdm`) for tracking export progress
- Structured logging via Python `logging` module
- `--version` flag
- Summary metrics: price change (90d / 180d), average daily volume

## Quick Start

### Linux / macOS

```bash
./run.sh --symbols-file symbols_spot_13.txt --days 180 --out out
```

### Windows (PowerShell)

```powershell
.\run.ps1 --symbols-file symbols_spot_13.txt --days 180 --out out
```

> Both scripts automatically create a virtual environment and install dependencies.

## Installation (manual)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Using a symbols file (recommended)

```bash
python binance_ohlcv_exporter.py \
  --symbols-file symbols_spot_13.txt \
  --intervals 1h 4h \
  --days 180 \
  --out out
```

### Inline symbols

```bash
python binance_ohlcv_exporter.py \
  --symbols BTCUSDT BNBUSDT XRPUSDT \
  --intervals 1h 4h \
  --days 180 \
  --out out
```

### Custom date range

```bash
python binance_ohlcv_exporter.py \
  --symbols-file symbols_spot_13.txt \
  --start 2025-01-01 \
  --end 2026-02-13 \
  --out out_2025_2026
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--symbols` | — | Space-separated list of trading pairs |
| `--symbols-file` | — | Text file with symbols (one per line) |
| `--intervals` | `1h 4h` | Candlestick intervals |
| `--days` | `180` | Lookback window (ignored if `--start` is set) |
| `--start` | — | Start date `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` |
| `--end` | *now* | End date (same format) |
| `--out` | `out` | Output directory |
| `--timeout` | `20` | HTTP timeout in seconds |
| `--sleep` | `0.15` | Pause between paginated requests (seconds) |

> You can combine `--symbols` and `--symbols-file`; duplicates are removed automatically.

## Output

```
out/
  klines_1h/<SYMBOL>_1h.csv
  klines_4h/<SYMBOL>_4h.csv
  summary_metrics.csv
```

- **Kline CSVs** — columns: `open_time_utc, open, high, low, close, volume, close_time_utc, quote_volume, trades, taker_buy_base_volume, taker_buy_quote_volume`
- **summary_metrics.csv** — columns: `symbol, price_change_90d_pct, price_change_180d_pct, avg_daily_volume_base, avg_daily_volume_quote`

## License

[MIT](LICENSE)
