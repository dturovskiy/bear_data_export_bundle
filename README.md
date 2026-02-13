# Binance OHLCV CSV Exporter (Spot)

A lightweight Python CLI tool that exports historical OHLCV (Open, High, Low, Close, Volume) candlestick data from the **Binance Spot** market into CSV files. Uses the public [Binance Market Data](https://data-api.binance.vision) endpoint — **no API key required**.

## Features

- Multiple symbols in a single run
- Configurable timeframes (default: `1h`, `4h`)
- Configurable date range (default: last 180 days)
- Automatic pagination & deduplication
- Retry with exponential backoff on network errors / rate limits
- Progress bar (`tqdm`) for tracking export progress
- Structured logging via Python `logging` module
- `--version` flag
- Summary metrics: price change (90d / 180d), average daily volume

## Quick Start (one command)

```bash
./run.sh --symbols BTCUSDT BNBUSDT --intervals 1h 4h --days 180 --out out
```

> `run.sh` automatically creates a virtual environment, installs dependencies, and runs the exporter.

## Installation (manual)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Basic (last 180 days)

```bash
python binance_ohlcv_exporter.py \
  --symbols BTCUSDT BNBUSDT FLOKIUSDT PEPEUSDT XRPUSDT DOGEUSDT SANDUSDT SHIBUSDT NEARUSDT DOTUSDT CAKEUSDT MANAUSDT WIFUSDT \
  --intervals 1h 4h \
  --days 180 \
  --out out
```

### Custom date range

```bash
python binance_ohlcv_exporter.py \
  --symbols BTCUSDT BNBUSDT \
  --intervals 1h 4h \
  --start 2025-01-01 \
  --end 2026-02-13 \
  --out out_2025_2026
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--symbols` | *(required)* | Space-separated list of trading pairs |
| `--intervals` | `1h 4h` | Candlestick intervals |
| `--days` | `180` | Lookback window (ignored if `--start` is set) |
| `--start` | — | Start date `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` |
| `--end` | *now* | End date (same format) |
| `--out` | `out` | Output directory |
| `--timeout` | `20` | HTTP timeout in seconds |

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
