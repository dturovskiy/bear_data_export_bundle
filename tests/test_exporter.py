"""
Unit tests for binance_ohlcv_exporter.py

Run:  python -m pytest tests/ -v
"""

from __future__ import annotations

import csv
import math
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Ensure the repo root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import binance_ohlcv_exporter as exp  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kline(
    open_time_ms: int = 0,
    open: str = "100.0",
    high: str = "110.0",
    low: str = "90.0",
    close: str = "105.0",
    volume: str = "1000.0",
    close_time_ms: int = 3_599_999,
    quote_volume: str = "50000.0",
    trades: int = 42,
    taker_buy_base_volume: str = "600.0",
    taker_buy_quote_volume: str = "30000.0",
) -> exp.Kline:
    return exp.Kline(
        open_time_ms=open_time_ms,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        close_time_ms=close_time_ms,
        quote_volume=quote_volume,
        trades=trades,
        taker_buy_base_volume=taker_buy_base_volume,
        taker_buy_quote_volume=taker_buy_quote_volume,
    )


# ---------------------------------------------------------------------------
# ms_to_utc_iso
# ---------------------------------------------------------------------------

class TestMsToUtcIso:
    def test_epoch_zero(self):
        assert exp.ms_to_utc_iso(0) == "1970-01-01 00:00:00"

    def test_known_timestamp(self):
        # 2024-01-01 00:00:00 UTC = 1704067200000 ms
        assert exp.ms_to_utc_iso(1_704_067_200_000) == "2024-01-01 00:00:00"

    def test_with_time_component(self):
        # 2024-06-15 12:00:00 UTC = 1718452800000 ms
        assert exp.ms_to_utc_iso(1_718_452_800_000) == "2024-06-15 12:00:00"


# ---------------------------------------------------------------------------
# parse_dt_utc
# ---------------------------------------------------------------------------

class TestParseDtUtc:
    def test_date_only(self):
        result = exp.parse_dt_utc("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0

    def test_date_and_time(self):
        result = exp.parse_dt_utc("2024-06-15T14:30:00")
        assert result.hour == 14
        assert result.minute == 30

    def test_has_utc_timezone(self):
        import datetime as dt
        result = exp.parse_dt_utc("2024-01-01")
        assert result.tzinfo == dt.timezone.utc


# ---------------------------------------------------------------------------
# get_range
# ---------------------------------------------------------------------------

class TestGetRange:
    def test_explicit_start_end(self):
        start_ms, end_ms = exp.get_range(
            days=180,
            start="2024-01-01",
            end="2024-07-01",
        )
        # 2024-01-01 00:00:00 UTC
        assert start_ms == 1_704_067_200_000
        # 2024-07-01 00:00:00 UTC
        assert end_ms == 1_719_792_000_000

    def test_days_fallback(self):
        start_ms, end_ms = exp.get_range(days=30, start=None, end="2024-02-01")
        expected_end = 1_706_745_600_000  # 2024-02-01
        assert end_ms == expected_end
        # start should be ~30 days earlier
        delta_days = (end_ms - start_ms) / (1000 * 86400)
        assert abs(delta_days - 30) < 0.01


# ---------------------------------------------------------------------------
# _load_symbols_file
# ---------------------------------------------------------------------------

class TestLoadSymbolsFile:
    def test_reads_symbols(self, tmp_path):
        f = tmp_path / "syms.txt"
        f.write_text("BTCUSDT\nETHUSDT\n  BNBUSDT  \n\n# comment\n")
        result = exp._load_symbols_file(str(f))
        assert result == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    def test_skips_comments_and_blanks(self, tmp_path):
        f = tmp_path / "syms.txt"
        f.write_text("# header\n\nBTCUSDT\n\n")
        result = exp._load_symbols_file(str(f))
        assert result == ["BTCUSDT"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            exp._load_symbols_file("/nonexistent/path/symbols.txt")


# ---------------------------------------------------------------------------
# Kline dataclass
# ---------------------------------------------------------------------------

class TestKline:
    def test_frozen(self):
        k = _make_kline()
        with pytest.raises(AttributeError):
            k.open = "999.0"  # type: ignore[misc]

    def test_fields_are_strings(self):
        k = _make_kline(open="0.00000001", close="0.00000002")
        assert isinstance(k.open, str)
        assert isinstance(k.close, str)
        assert k.open == "0.00000001"


# ---------------------------------------------------------------------------
# write_klines_csv
# ---------------------------------------------------------------------------

class TestWriteKlinesCsv:
    def test_writes_correct_rows(self, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        klines = [
            _make_kline(open_time_ms=0, close_time_ms=3_599_999),
            _make_kline(open_time_ms=3_600_000, close_time_ms=7_199_999),
        ]
        exp.write_klines_csv(csv_path, klines)

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        # header + 2 rows
        assert len(reader) == 3
        assert reader[0][0] == "open_time_utc"
        assert reader[0][1] == "open"

    def test_preserves_string_precision(self, tmp_path):
        csv_path = str(tmp_path / "prec.csv")
        k = _make_kline(open="0.000000012345678901")
        exp.write_klines_csv(csv_path, [k])

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        # The open value must be written exactly as the original string
        assert reader[1][1] == "0.000000012345678901"

    def test_fails_on_missing_parent_dir(self, tmp_path):
        csv_path = str(tmp_path / "nonexistent" / "test.csv")
        with pytest.raises(FileNotFoundError):
            exp.write_klines_csv(csv_path, [_make_kline()])

    def test_empty_klines(self, tmp_path):
        csv_path = str(tmp_path / "empty.csv")
        exp.write_klines_csv(csv_path, [])

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        assert len(reader) == 1  # header only


# ---------------------------------------------------------------------------
# calc_metrics
# ---------------------------------------------------------------------------

class TestCalcMetrics:
    def _make_hourly_series(self, hours: int, base_price: float = 100.0):
        """Generate a series of hourly klines."""
        klines = []
        ms_per_hour = 3_600_000
        for i in range(hours):
            price = str(base_price + i * 0.01)
            klines.append(
                _make_kline(
                    open_time_ms=i * ms_per_hour,
                    close=price,
                    volume="1000.0",
                    quote_volume="50000.0",
                    close_time_ms=(i + 1) * ms_per_hour - 1,
                )
            )
        return klines

    def test_returns_four_values(self):
        klines = self._make_hourly_series(24 * 180)
        result = exp.calc_metrics("TEST", klines)
        assert len(result) == 4

    def test_empty_klines_returns_nan(self):
        ch90, ch180, avg_b, avg_q = exp.calc_metrics("TEST", [])
        assert math.isnan(ch90)
        assert math.isnan(ch180)
        assert math.isnan(avg_b)
        assert math.isnan(avg_q)

    def test_flat_price_zero_change(self):
        """If all close prices are the same, change should be 0%."""
        klines = []
        ms_per_hour = 3_600_000
        for i in range(24 * 180):
            klines.append(
                _make_kline(
                    open_time_ms=i * ms_per_hour,
                    close="100.0",
                    volume="500.0",
                    quote_volume="25000.0",
                    close_time_ms=(i + 1) * ms_per_hour - 1,
                )
            )
        ch90, ch180, avg_b, avg_q = exp.calc_metrics("FLAT", klines)
        assert abs(ch90) < 0.0001
        assert abs(ch180) < 0.0001

    def test_avg_volume_calculation(self):
        """Two days of data with known volumes."""
        klines = []
        ms_per_hour = 3_600_000
        for h in range(48):  # 2 days
            vol = "100.0" if h < 24 else "200.0"
            qvol = "5000.0" if h < 24 else "10000.0"
            klines.append(
                _make_kline(
                    open_time_ms=h * ms_per_hour,
                    close="50.0",
                    volume=vol,
                    quote_volume=qvol,
                    close_time_ms=(h + 1) * ms_per_hour - 1,
                )
            )
        _, _, avg_b, avg_q = exp.calc_metrics("VOL", klines)
        # Day 1: 24*100=2400, Day 2: 24*200=4800, avg = 3600
        assert abs(avg_b - 3600.0) < 0.01
        # Day 1: 24*5000=120000, Day 2: 24*10000=240000, avg = 180000
        assert abs(avg_q - 180000.0) < 0.01


# ---------------------------------------------------------------------------
# _request_with_retry (mocked)
# ---------------------------------------------------------------------------

class TestRequestWithRetry:
    @patch("binance_ohlcv_exporter.requests.get")
    def test_success_first_try(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [["data"]]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = exp._request_with_retry("http://test", {}, timeout=10)
        assert result == [["data"]]
        assert mock_get.call_count == 1

    @patch("binance_ohlcv_exporter.time.sleep")
    @patch("binance_ohlcv_exporter.requests.get")
    def test_retries_on_connection_error(self, mock_get, mock_sleep):
        import requests as req

        mock_resp = MagicMock()
        mock_resp.json.return_value = [["ok"]]
        mock_resp.raise_for_status.return_value = None

        mock_get.side_effect = [
            req.ConnectionError("fail"),
            mock_resp,
        ]

        result = exp._request_with_retry("http://test", {}, timeout=10, retries=3)
        assert result == [["ok"]]
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("binance_ohlcv_exporter.time.sleep")
    @patch("binance_ohlcv_exporter.requests.get")
    def test_raises_after_max_retries(self, mock_get, mock_sleep):
        import requests as req

        mock_get.side_effect = req.ConnectionError("persistent fail")

        with pytest.raises(req.ConnectionError):
            exp._request_with_retry("http://test", {}, timeout=10, retries=2)
        assert mock_get.call_count == 2

    @patch("binance_ohlcv_exporter.time.sleep")
    @patch("binance_ohlcv_exporter.requests.get")
    def test_retries_on_429(self, mock_get, mock_sleep):
        import requests as req

        # First call: 429, second call: success
        resp_429 = MagicMock()
        resp_429.status_code = 429
        http_err = req.HTTPError(response=resp_429)

        mock_resp = MagicMock()
        mock_resp.json.return_value = [["ok"]]
        mock_resp.raise_for_status.return_value = None

        mock_get.side_effect = [http_err, mock_resp]

        result = exp._request_with_retry("http://test", {}, timeout=10, retries=3)
        assert result == [["ok"]]
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("binance_ohlcv_exporter.requests.get")
    def test_raises_non_429_http_error(self, mock_get):
        import requests as req

        resp_404 = MagicMock()
        resp_404.status_code = 404
        http_err = req.HTTPError(response=resp_404)

        mock_get.side_effect = http_err

        with pytest.raises(req.HTTPError):
            exp._request_with_retry("http://test", {}, timeout=10, retries=3)
        # Should NOT retry on 404
        assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# fetch_klines (mocked, no network)
# ---------------------------------------------------------------------------

class TestFetchKlines:
    @patch("binance_ohlcv_exporter._request_with_retry")
    def test_single_page(self, mock_req):
        # Simulate one page that returns < limit rows (end of data)
        mock_req.return_value = [
            [0, "100", "110", "90", "105", "1000", 3599999, "50000", 42, "600", "30000", 0],
            [3600000, "105", "115", "95", "110", "1100", 7199999, "55000", 50, "650", "32000", 0],
        ]

        result = exp.fetch_klines("BTCUSDT", "1h", 0, 7_200_000, timeout=10, sleep_sec=0)
        assert len(result) == 2
        assert result[0].open == "100"
        assert result[1].close == "110"

    @patch("binance_ohlcv_exporter.time.sleep")
    @patch("binance_ohlcv_exporter._request_with_retry")
    def test_deduplication(self, mock_req, mock_sleep):
        # Same open_time_ms twice -> should deduplicate
        row = [0, "100", "110", "90", "105", "1000", 3599999, "50000", 42, "600", "30000", 0]
        mock_req.return_value = [row, row]

        result = exp.fetch_klines("BTCUSDT", "1h", 0, 3_600_000, timeout=10, sleep_sec=0)
        assert len(result) == 1

    @patch("binance_ohlcv_exporter._request_with_retry")
    def test_filters_beyond_end_ms(self, mock_req):
        mock_req.return_value = [
            [0, "100", "110", "90", "105", "1000", 3599999, "50000", 42, "600", "30000", 0],
            [99_999_999, "100", "110", "90", "105", "1000", 103599999, "50000", 42, "600", "30000", 0],
        ]

        result = exp.fetch_klines("BTCUSDT", "1h", 0, 3_600_000, timeout=10, sleep_sec=0)
        assert len(result) == 1
        assert result[0].open_time_ms == 0
