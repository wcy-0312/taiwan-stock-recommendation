# 台股智能雷達 LINE Bot — V2 Design Spec

**Date:** 2026-06-13
**Status:** Approved by user

---

## Goal

Upgrade `taiwan-stock-recommendation` from a push-only 0050 technical script into a full LINE Bot: daily radar broadcasts, interactive stock queries, user watchlists, backtesting, and cloud deployment on Render.

---

## Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Deployment | Render Web Service | Free tier, GitHub deploy, HTTPS for webhook |
| Web framework | FastAPI | Async, modern, auto OpenAPI |
| Scheduler | APScheduler embedded in FastAPI process | Avoids cache-sync issues with separate Cron Job |
| Persistence | SQLite (watchlist) + JSON (daily cache) | No server required, Render persistent disk |
| Chip data | Skipped (chip_score = None) | No free source; field reserved for future |
| Backtesting | Included (basic, yfinance historical) | Standalone CLI script |
| Architecture | Full app/ package restructure | Long-term maintainability |
| Backward compat | Thin wrappers for scheduler.py, verify_live_send.py | Old CLI commands must still work |

---

## Architecture

```
Render Web Service
└── python -m app.main  (FastAPI + APScheduler)
    ├── POST /webhook          ← LINE platform calls here
    ├── GET  /health           ← Render health check
    └── APScheduler
        ├── weekday 14:00 CST → analysis pipeline → write cache
        └── weekday 08:30 CST → read cache → push LINE message
```

---

## Package Structure

```
taiwan-stock-recommendation/
├── app/
│   ├── main.py                  # FastAPI app entry + APScheduler start
│   ├── config.py                # All settings (env vars, thresholds, paths)
│   ├── pipeline.py              # Orchestrate: data → features → scoring → recommendation
│   │
│   ├── data/
│   │   ├── universe_provider.py # Load tw0050.json → ticker list with name/sector
│   │   └── yfinance_provider.py # Fetch OHLCV, derive latest_data_date from index
│   │
│   ├── features/
│   │   ├── technical.py         # MA5/20/60, RSI14, MACD, slopes, crossovers
│   │   ├── volume.py            # volume_ratio, volume_up, volume_down patterns
│   │   └── risk.py              # ATR14, atr_pct, support_20d, resistance_20d
│   │
│   ├── scoring/
│   │   ├── models.py            # StockRadarResult dataclass
│   │   ├── radar.py             # 5 sub-scores → radar_score 0–100
│   │   ├── reasons.py           # Event-based reasons, risk_notes, invalidation
│   │   └── market_context.py    # Universe-level stats (bullish_ratio, avg_score)
│   │
│   ├── recommendation/
│   │   ├── selector.py          # strong_watchlist / weakness_alerts / turning_points
│   │   └── formatter.py         # LINE message formatting (multi-message, None-safe)
│   │
│   ├── backtesting/
│   │   ├── engine.py            # Historical simulation over radar signals
│   │   └── metrics.py           # win_rate, avg_return, max_drawdown, sharpe
│   │
│   └── linebot/
│       ├── webhook.py           # FastAPI router: POST /webhook, signature verify
│       ├── notifier.py          # Push message via LINE Messaging API v3
│       ├── commands.py          # Parse + dispatch user commands
│       └── watchlist.py         # SQLite CRUD: user_id ↔ tickers
│
├── data/
│   ├── universes/tw0050.json    # {ticker, code, name, sector} list
│   └── cache/                   # Daily analysis JSON cache
│
├── scripts/
│   └── backtest_strategy.py     # CLI: --universe --start --end --top-n --holding-days
│
├── tests/
│   ├── test_scoring.py          # radar_score always 0–100, rank correct
│   ├── test_formatter.py        # No None/nan in output, long messages split
│   ├── test_backtest.py         # Small sample runs to completion
│   └── test_commands.py         # Command parser: 2330, 查 2330, 追蹤 2330, etc.
│
├── docs/
│   ├── scoring-spec.md
│   ├── product-spec.md
│   └── linebot-commands.md
│
├── scheduler.py                 # Backward-compat wrapper → app.pipeline
├── verify_live_send.py          # Backward-compat wrapper → app.pipeline
├── render.yaml                  # Render deployment config
├── requirements.txt
├── .env.example
└── README.md
```

---

## Data Model: StockRadarResult

```python
@dataclass
class StockRadarResult:
    # Identity
    ticker: str
    code: str
    name: str
    data_date: str

    # Price
    latest_close: float
    price_change_1d_pct: float
    price_change_5d_pct: float

    # Ranking & Direction
    radar_score: int          # 0–100 (clamped)
    rank_in_universe: int
    universe_size: int
    direction: str            # "bullish" / "neutral" / "bearish"
    confidence: str           # "高" / "中" / "低"

    # Sub-scores
    trend_score: int          # 0–30
    momentum_score: int       # 0–20
    volume_score: int         # 0–20
    risk_score: int           # 0–15
    market_score: int         # 0–10
    chip_score: Optional[int] # None (reserved)

    # Indicators (display)
    ma5: float
    ma20: float
    ma60: Optional[float]
    rsi14: float
    macd_hist: float
    macd_hist_delta: float
    volume_ratio: float
    atr14: float
    atr_pct: float
    support_20d: float
    resistance_20d: float

    # Explanations
    positive_reasons: list[str]        # ✅ Bullish signals
    negative_reasons: list[str]        # 🔻 Bearish / weakening reasons
    risk_notes: list[str]              # ⚠️ Risk reminders (even bullish stocks can have)
    invalidation_conditions: list[str] # Signal invalidation triggers

    # Backtesting (all Optional)
    historical_win_rate_5d: Optional[float]
    historical_avg_return_5d: Optional[float]
    historical_win_rate_10d: Optional[float]
    historical_avg_return_10d: Optional[float]
```

---

## Scoring Spec

### Sub-score Bands

**trend_score (0–30)**
| Band | Range | Conditions |
|------|-------|------------|
| High | 22–30 | MA5 > MA20 > MA60, close > MA5, MA5 slope > 0, MA20 slope > 0 |
| Mid  | 12–21 | MA5 > MA20 but MA60 missing or not aligned, OR close near MA5 |
| Low  | 0–11  | MA5 < MA20, OR close < MA20 |

**momentum_score (0–20)**
| Band | Range | Conditions |
|------|-------|------------|
| High | 15–20 | MACD hist > 0 and expanding, RSI 50–70 |
| Mid  | 8–14  | MACD hist > 0 but flat, OR RSI 70–75 (slightly hot) |
| Low  | 0–7   | MACD hist < 0, OR RSI < 50 |

**RSI Rules (explicit):**
- RSI 50–70: healthy bull → add to momentum score
- RSI 70–75: slightly hot → small add or neutral
- RSI > 75: overheated → add to `risk_notes`
- RSI 30–50: neutral-weak → no score
- RSI < 30: oversold → NOT bullish signal, add to `risk_notes` (high volatility)

**volume_score (0–20)**
| Band | Range | Conditions |
|------|-------|------------|
| High | 15–20 | volume_ratio ≥ 1.5 and price up |
| Mid  | 8–14  | volume_ratio 1.0–1.5, or normal |
| Low  | 0–7   | volume_ratio < 0.8 (volume contraction breakout), OR high-volume decline |

**risk_score (0–15)**
| Band | Range | Conditions |
|------|-------|------------|
| High | 11–15 | ATR% < 2%, distance to resistance > 5%, above support |
| Mid  | 6–10  | ATR% 2–4%, distance to resistance 3–5% |
| Low  | 0–5   | ATR% > 4%, near resistance (< 3%), OR broke support |

**market_score (0–10)**
- Context only — does NOT drive individual stock selection
- **Hard rule: if trend+momentum+volume+risk ≤ 65, market_score CANNOT push radar_score ≥ 70**
- Implementation: selection threshold uses base_score (without market_score), not radar_score

### Direction Thresholds
- `bullish`:  radar_score ≥ 70
- `bearish`:  radar_score ≤ 35
- `neutral`:  36–69

### Confidence Rules (ALL conditions required for 高)
**高信心:**
- radar_score ≥ 80
- volume_ratio ≥ 1.2
- len(risk_notes) ≤ 1
- len(positive_reasons) ≥ 3
- No signal conflict (e.g., not: volume contraction + breakout, not: RSI > 75 + bullish)

**中信心:** Does not meet all 高 conditions AND radar_score ≥ 60

**低信心:** radar_score < 60, OR ATR% > 4%, OR obvious signal conflict

---

## Stock Selection Logic

```python
strong_watchlist:  base_score >= 70, sorted desc, max Top 5, broadcast Top 3
weakness_alerts:   base_score <= 35, sorted asc,  max Bottom 5, broadcast Top 2
turning_points:    MACD hist flipped pos/neg today, OR close reclaimed/broke MA20,
                   OR high-volume breakout above 20d high
```

No stocks → display "今日無明確技術面強勢股" (do not force neutral stocks in).

---

## LINE Message Format

Split into up to 3 messages to stay within LINE's 5000-char limit.

**Message 1:** Market context + 強勢觀察 Top 3
**Message 2:** 轉弱警示 Top 2 (only if weakness stocks exist)
**Message 3:** Summary + disclaimer

Formatter rules:
- All fields: use `or` fallback, never output `None` or `nan`
- Numeric formatting: prices to 2 decimal places, pct to 1 decimal place
- Sub-score display: `趨勢28｜動能18｜量能17｜風險12｜市場9`
- Disclaimer: `以上僅為量化技術觀察，不構成投資建議。`

---

## LINE Bot Interactive Commands

| Input | Response |
|-------|----------|
| `2330` or `查 2330` | Full radar for single stock |
| `今日雷達` | Today's full broadcast summary |
| `強勢股` | Today's strong watchlist Top 10 |
| `轉弱股` | Today's weakness alerts Top 10 |
| `追蹤 2330` | Add to user watchlist |
| `取消追蹤 2330` | Remove from watchlist |
| `我的清單` | User's watchlist with today's status |
| `幫助` / `help` | Command list |

Watchlist stored in SQLite: `(user_id TEXT, ticker TEXT, added_at TEXT)`.

---

## Backtesting CLI

```bash
python scripts/backtest_strategy.py \
  --universe tw0050 \
  --start 2023-01-01 \
  --end 2026-06-13 \
  --top-n 5 \
  --holding-days 5,10,20
```

Outputs: trade_count, win_rate, avg_return, annualized_return, max_drawdown, sharpe_ratio.
Benchmark: skipped or labeled "unavailable" if not available.
Min sample size: 10 trades required; otherwise display "歷史樣本不足".

---

## Render Deployment

**render.yaml:**
```yaml
services:
  - type: web
    name: taiwan-stock-radar
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.main
    envVars:
      - key: LINE_CHANNEL_ACCESS_TOKEN
        sync: false
      - key: LINE_USER_ID
        sync: false
      - key: LINE_CHANNEL_SECRET
        sync: false
```

**New required env var:** `LINE_CHANNEL_SECRET` (for webhook signature verification).

---

## Backward Compatibility

These commands must still work after migration:
```bash
python scheduler.py
python scheduler.py --analysis-now
python scheduler.py --send-now
python verify_live_send.py --full
```

Implemented as thin wrappers that call `app.pipeline` functions.

---

## Test Coverage

| Test | What it checks |
|------|----------------|
| test_scoring.py | radar_score always 0–100, rank_in_universe correct, RSI < 30 not bullish |
| test_formatter.py | No None/nan in output, messages split at 5000 chars |
| test_backtest.py | Small sample (5 stocks, 30 days) runs to completion |
| test_commands.py | Parser handles: 2330, 查 2330, 追蹤 2330, 取消追蹤 2330, 我的清單 |

Smoke tests preserved:
```bash
python recommendation_generator.py  # wrapper smoke test
python scheduler.py --analysis-now
python verify_live_send.py --full
```

---

## Out of Scope (this iteration)

- Chip data / 法人籌碼 (chip_score = None, field reserved)
- Fundamental data
- OTC stocks (.TWO)
- Real-time / intraday data
- Market holiday handling
- LLM-generated explanations
- Paid APIs
