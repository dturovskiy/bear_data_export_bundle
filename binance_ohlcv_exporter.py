#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
binance_ohlcv_exporter.py

Експортер OHLCV (spot) з Binance у CSV для:
- BTCUSDT + список buy_targets
- TF: 1h та 4h
- window: 180d за замовчуванням (можна задати --start/--end)

Джерело: публічний Market Data Only домен Binance:
https://data-api.binance.vision/api/v3/klines  (без API-ключа)
Див. офіційну довідку Binance: Market Data Only URLs.

Вихід:
out/
  klines_1h/<SYMBOL>_1h.csv
  klines_4h/<SYMBOL>_4h.csv
  summary_metrics.csv

CSV колонки (1h/4h):
open_time_utc,open,high,low,close,volume,close_time_utc,quote_volume,trades,taker_buy_base_volume,taker_buy_quote_volume

Метрики (summary_metrics.csv):
symbol,price_change_90d_pct,price_change_180d_pct,avg_daily_volume_base,avg_daily_volume_quote
"""

__version__ = "1.1.0"

import argparse
import csv
import datetime as dt
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
from tqdm import tqdm


# --- Logging ---
log = logging.getLogger(__name__)


# --- Константи API (публічний домен, не потребує ключа) ---
BASE_URL = "https://data-api.binance.vision"
KLINES_PATH = "/api/v3/klines"


@dataclass(frozen=True)
class Kline:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int
    quote_volume: float
    trades: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float


def ms_to_utc_iso(ms: int) -> str:
    """Конвертація Unix ms -> ISO-8601 UTC (без мілісекунд для компактності)."""
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export Binance spot OHLCV data to CSV.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--symbols", nargs="+", required=True, help="Список символів, напр. BTCUSDT BNBUSDT ...")
    p.add_argument("--intervals", nargs="+", default=["1h", "4h"], help="Інтервали, напр. 1h 4h")
    p.add_argument("--days", type=int, default=180, help="Вікно в днях (якщо не задані --start/--end).")
    p.add_argument("--start", type=str, default=None, help="Початок UTC: YYYY-MM-DD або YYYY-MM-DDTHH:MM:SS")
    p.add_argument("--end", type=str, default=None, help="Кінець UTC: YYYY-MM-DD або YYYY-MM-DDTHH:MM:SS")
    p.add_argument("--out", type=str, default="out", help="Папка для CSV.")
    p.add_argument("--timeout", type=int, default=20, help="Таймаут HTTP (сек).")
    return p.parse_args()


def parse_dt_utc(s: str) -> dt.datetime:
    """Парсимо дату/час у UTC. Підтримка: YYYY-MM-DD або YYYY-MM-DDTHH:MM:SS."""
    if "T" in s:
        d = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    else:
        d = dt.datetime.strptime(s, "%Y-%m-%d")
    return d.replace(tzinfo=dt.timezone.utc)


def get_range(days: int, start: Optional[str], end: Optional[str]) -> Tuple[int, int]:
    """Повертає (start_ms, end_ms) у Unix milliseconds."""
    if end:
        end_dt = parse_dt_utc(end)
    else:
        end_dt = dt.datetime.now(tz=dt.timezone.utc)

    if start:
        start_dt = parse_dt_utc(start)
    else:
        start_dt = end_dt - dt.timedelta(days=days)

    # Binance приймає ms. endTime інклюзивний, але ми будемо керуватися циклом пагінації.
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


def _request_with_retry(
    url: str,
    params: dict[str, str | int],
    timeout: int,
    retries: int = 3,
) -> list:
    """
    HTTP GET з retry + exponential backoff.
    Повертає розпарсений JSON (список).
    """
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            log.warning("network error (%s), retry %d/%d in %ds…", exc, attempt, retries, wait)
            time.sleep(wait)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 2 ** attempt
                log.warning("rate-limited (429), retry %d/%d in %ds…", attempt, retries, wait)
                time.sleep(wait)
            else:
                raise
    return []  # unreachable, kept for type-checker


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, timeout: int) -> List[Kline]:
    """
    Завантажує klines через /api/v3/klines з пагінацією (limit=1000).
    Повертає список Kline, відсортований за часом зростання.
    """
    out: List[Kline] = []
    limit = 1000
    url = f"{BASE_URL}{KLINES_PATH}"
    next_start = start_ms

    while True:
        params: dict[str, str | int] = {
            "symbol": symbol,
            "interval": interval,
            "startTime": next_start,
            "endTime": end_ms,
            "limit": limit,
        }
        data = _request_with_retry(url, params, timeout)

        if not data:
            break

        # Парсимо відповідь
        for row in data:
            out.append(
                Kline(
                    open_time_ms=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time_ms=int(row[6]),
                    quote_volume=float(row[7]),
                    trades=int(row[8]),
                    taker_buy_base_volume=float(row[9]),
                    taker_buy_quote_volume=float(row[10]),
                )
            )

        last_open = int(data[-1][0])
        # Якщо остання свічка вже дійшла до end_ms або повернули < limit — виходимо.
        if last_open >= end_ms or len(data) < limit:
            break

        # Наступна сторінка: +1 ms, щоб уникнути дубля
        next_start = last_open + 1

        # Rate-limit: невелика пауза між сторінками
        time.sleep(0.15)

    # У Binance інколи можуть бути дублікати на стиках; зачистимо:
    dedup: dict[int, Kline] = {}
    for k in out:
        dedup[k.open_time_ms] = k
    out_sorted = [dedup[t] for t in sorted(dedup.keys())]

    # Відрізаємо по end_ms (на випадок зайвого хвоста)
    out_sorted = [k for k in out_sorted if k.open_time_ms <= end_ms]
    return out_sorted


def write_klines_csv(path: str, klines: List[Kline]) -> None:
    """Записує klines у CSV."""
    header = [
        "open_time_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time_utc",
        "quote_volume",
        "trades",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for k in klines:
            w.writerow(
                [
                    ms_to_utc_iso(k.open_time_ms),
                    f"{k.open:.10f}",
                    f"{k.high:.10f}",
                    f"{k.low:.10f}",
                    f"{k.close:.10f}",
                    f"{k.volume:.10f}",
                    ms_to_utc_iso(k.close_time_ms),
                    f"{k.quote_volume:.10f}",
                    k.trades,
                    f"{k.taker_buy_base_volume:.10f}",
                    f"{k.taker_buy_quote_volume:.10f}",
                ]
            )


def calc_metrics(symbol: str, klines_1h: List[Kline]) -> Tuple[float, float, float, float]:
    """
    Рахує:
    - % зміни ціни за 90d і 180d (за close)
    - середній денний обсяг (base та quote) по 1h свічках.

    Примітка: 90d/180d — за "найближчою доступною" свічкою на старті вікна.
    """
    if not klines_1h:
        return float("nan"), float("nan"), float("nan"), float("nan")

    # Допоміжна функція: знайти close "на або після" target_time
    def close_at_or_after(target_ms: int) -> float:
        for k in klines_1h:
            if k.open_time_ms >= target_ms:
                return k.close
        return klines_1h[-1].close

    end_ms = klines_1h[-1].open_time_ms
    c_end = klines_1h[-1].close

    ms_90 = end_ms - int(90 * 24 * 3600 * 1000)
    ms_180 = end_ms - int(180 * 24 * 3600 * 1000)

    c_90 = close_at_or_after(ms_90)
    c_180 = close_at_or_after(ms_180)

    ch90 = (c_end / c_90 - 1.0) * 100.0 if c_90 else float("nan")
    ch180 = (c_end / c_180 - 1.0) * 100.0 if c_180 else float("nan")

    # Середній денний обсяг: групуємо по YYYY-MM-DD (UTC)
    day_b: dict[str, float] = {}
    day_q: dict[str, float] = {}
    for k in klines_1h:
        day = ms_to_utc_iso(k.open_time_ms)[:10]
        day_b[day] = day_b.get(day, 0.0) + k.volume
        day_q[day] = day_q.get(day, 0.0) + k.quote_volume

    avg_b = sum(day_b.values()) / len(day_b) if day_b else float("nan")
    avg_q = sum(day_q.values()) / len(day_q) if day_q else float("nan")
    return ch90, ch180, avg_b, avg_q


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    args = parse_args()
    start_ms, end_ms = get_range(args.days, args.start, args.end)

    out_root = args.out
    os.makedirs(out_root, exist_ok=True)

    # Папки під інтервали
    for interval in args.intervals:
        os.makedirs(os.path.join(out_root, f"klines_{interval}"), exist_ok=True)

    # Метрики будемо рахувати з 1h (щоб добові обсяги були точнішими)
    summary_rows: list[list[str]] = []

    total_jobs = len(args.symbols) * len(args.intervals)
    pbar = tqdm(total=total_jobs, desc="Exporting", unit="job")

    for symbol in args.symbols:
        log.info("Fetching %s …", symbol)
        klines_by_interval: dict[str, List[Kline]] = {}

        for interval in args.intervals:
            kl = fetch_klines(symbol, interval, start_ms, end_ms, args.timeout)
            klines_by_interval[interval] = kl

            out_csv = os.path.join(out_root, f"klines_{interval}", f"{symbol}_{interval}.csv")
            write_klines_csv(out_csv, kl)
            log.info("  saved: %s (%d rows)", out_csv, len(kl))
            pbar.update(1)

        if "1h" in klines_by_interval:
            ch90, ch180, avg_b, avg_q = calc_metrics(symbol, klines_by_interval["1h"])
            summary_rows.append([symbol, f"{ch90:.6f}", f"{ch180:.6f}", f"{avg_b:.10f}", f"{avg_q:.10f}"])

    pbar.close()

    # Запис метрик
    summary_path = os.path.join(out_root, "summary_metrics.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "price_change_90d_pct", "price_change_180d_pct", "avg_daily_volume_base", "avg_daily_volume_quote"])
        w.writerows(summary_rows)

    log.info("Done. Summary → %s", summary_path)


if __name__ == "__main__":
    main()
