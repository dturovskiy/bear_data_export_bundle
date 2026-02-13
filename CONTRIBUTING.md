# Contributing

Thanks for your interest in contributing! Here's how to get started.

## Local setup

```bash
git clone https://github.com/your-username/bear_data_export_bundle.git
cd bear_data_export_bundle
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Code style

- Follow **PEP 8**
- We recommend using [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:
  ```bash
  pip install ruff
  ruff check .
  ruff format .
  ```

## Before submitting a PR

1. **Syntax check passes:**
   ```bash
   python -m py_compile binance_ohlcv_exporter.py
   ```

2. **CLI runs without errors:**
   ```bash
   python binance_ohlcv_exporter.py --help
   python binance_ohlcv_exporter.py --version
   ```

3. **Lint is clean** (optional but appreciated):
   ```bash
   ruff check .
   ```

4. **Test a short run** if you changed data logic:
   ```bash
   python binance_ohlcv_exporter.py \
     --symbols BTCUSDT \
     --intervals 1h \
     --days 1 \
     --out test_out
   ```

## Pull Request guidelines

- Keep PRs focused on a single change
- Write a clear PR description explaining **what** and **why**
- Reference related issues with `Fixes #123` or `Closes #123`
