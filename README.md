# 台股智能雷達 LINE Bot

V2 system: daily radar broadcasts, interactive LINE Bot commands, user watchlists, backtesting CLI, and cloud deployment on Render.

Analyzes all tw0050 constituent stocks every trading day using a 5-sub-score radar engine. Results are pushed via LINE Messaging API each morning.

---

## Features

- **Daily radar broadcast** — weekday 08:30 CST push via LINE
- **5 sub-score engine** — trend, momentum, volume, risk, market context (0–100)
- **Interactive commands** — query individual stocks, manage watchlists
- **Backtesting CLI** — walk-forward backtest over yfinance historical data
- **Cloud deployment** — Render Web Service with persistent SQLite watchlist
- **Backward-compatible** — old `scheduler.py` and `verify_live_send.py` CLI commands still work

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in:
# LINE_CHANNEL_ACCESS_TOKEN=...
# LINE_USER_ID=...
# LINE_CHANNEL_SECRET=...
```

### 3. Run the app

```bash
# Start FastAPI + APScheduler (production entry point)
python -m app.main

# Trigger analysis immediately (backward-compat)
python scheduler.py --analysis-now

# Live send verification (requires valid LINE credentials)
python verify_live_send.py --full
```

### 4. Run tests

```bash
python -m pytest tests/ -v
```

Expected: 172 tests, all passing.

---

## Backtest CLI

```bash
python scripts/backtest_strategy.py \
  --universe tw0050 \
  --start 2024-01-01 \
  --end 2026-06-13 \
  --top-n 5 \
  --holding-days 5,10,20
```

Options:
| Flag | Description | Default |
|------|-------------|---------|
| `--universe` | Universe name (currently only `tw0050`) | `tw0050` |
| `--start` | Start date (YYYY-MM-DD) | required |
| `--end` | End date (YYYY-MM-DD) | required |
| `--top-n` | Top-N stocks per rebalance period | `5` |
| `--holding-days` | Holding period(s); comma-separated | `5` |
| `--rebalance` | Rebalance every N days | same as holding-days |
| `--quiet` | Suppress progress output | off |

Outputs: `trade_count`, `win_rate`, `avg_return`, `annualized_return`, `max_drawdown`, `sharpe_ratio`.

Minimum 10 trades required; otherwise prints `歷史樣本不足`.

---

## LINE Bot Commands

| Input | Response |
|-------|----------|
| `查 2330` or `2330` | Full radar analysis for one stock |
| `今日雷達` | Today's broadcast summary |
| `追蹤 2330` | Add to your watchlist |
| `移除 2330` | Remove from watchlist |
| `我的清單` | Show your watchlist with current status |
| `幫助` / `help` | Command reference |

---

## Architecture

```
Render Web Service
└── python -m app.main  (FastAPI + APScheduler)
    ├── POST /webhook          ← LINE platform webhook
    ├── GET  /health           ← Render health check
    └── APScheduler
        ├── weekday 14:00 CST → analysis pipeline → write data/cache/
        └── weekday 08:30 CST → read cache → push LINE message
```

---

## Package Structure

```
app/
├── main.py                  # FastAPI app + APScheduler
├── config.py                # All settings (env vars, thresholds, paths)
├── pipeline.py              # Data → features → scoring → recommendation
├── data/
│   ├── universe_provider.py # tw0050 universe loader
│   └── yfinance_provider.py # OHLCV fetcher (skips 2888.TW)
├── features/
│   ├── technical.py         # MA5/20/60, RSI14, MACD
│   ├── volume.py            # volume_ratio, buy/sell patterns
│   └── risk.py              # ATR14, support/resistance
├── scoring/
│   ├── models.py            # StockRadarResult dataclass
│   ├── radar.py             # 5-sub-score computation
│   ├── reasons.py           # positive/negative/risk reasons
│   └── market_context.py    # Universe-level market scorer
├── recommendation/
│   ├── selector.py          # strong_watchlist / weakness_alerts
│   └── formatter.py         # None-safe LINE message formatter
├── backtesting/
│   ├── engine.py            # Walk-forward backtest engine
│   └── metrics.py           # win_rate, avg_return, sharpe, max_drawdown
└── linebot/
    ├── webhook.py           # FastAPI router + LINE signature verification
    ├── notifier.py          # LINE Messaging API v3 push/reply client
    ├── commands.py          # Command parser and dispatcher
    └── watchlist.py         # SQLite CRUD (user_id, ticker, added_at)

data/
├── universes/tw0050.json    # 50-ticker universe definition
└── cache/                   # Daily analysis JSON cache

scripts/
└── backtest_strategy.py     # Backtest CLI entry point

tests/
├── test_scoring.py          # 56 tests: radar_score, ICR rules, bands
├── test_formatter.py        # 46 tests: None/nan-safety, message limits
├── test_backtest.py         # 26 tests: metrics, engine, CLI
└── test_commands.py         # 44 tests: command parser, watchlist CRUD

docs/
├── scoring-spec.md          # Authoritative scoring rules and bands
└── operator-guide.md        # Deployment and operations guide
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Yes | LINE Messaging API access token |
| `LINE_USER_ID` | Yes | Target user/group ID for broadcasts |
| `LINE_CHANNEL_SECRET` | Yes | For webhook HMAC-SHA256 signature verification |

Copy `.env.example` to `.env` and fill in all three values before running.

---

## Deployment (Render)

The `render.yaml` defines a single Web Service that runs `python -m app.main`.

All three env vars must be configured as secret environment variables in the Render dashboard (marked `sync: false` — they are never committed to source).

See [docs/operator-guide.md](docs/operator-guide.md) for full deployment walkthrough.

---

## Scoring Summary

| Sub-score | Max | Key Signals |
|-----------|-----|-------------|
| trend_score | 30 | MA alignment (MA5/20/60), close position, slopes |
| momentum_score | 20 | MACD histogram, RSI (ICR-2: RSI < 30 is risk, not bullish) |
| volume_score | 20 | volume_ratio, price direction |
| risk_score | 15 | ATR%, distance to support/resistance |
| market_score | 10 | Universe-level context (display only, not for selection) |

Selection gate uses **base_score** (trend+momentum+volume+risk ≥ 70), not radar_score — see `docs/scoring-spec.md`.

---

## Backward Compatibility

These V1 commands still work:

```bash
python scheduler.py              # daily scheduler
python scheduler.py --analysis-now
python scheduler.py --send-now
python verify_live_send.py --full
```

They delegate to the V2 `app.pipeline` internally.
