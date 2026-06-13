# Mission Contract

> Stability: HIGH — only revise when core assumptions are invalidated. Requires human confirmation.

---

## Task Objective

**Goal:** Upgrade `taiwan-stock-recommendation` from a push-only 0050 technical script into a full LINE Bot: daily radar broadcasts, interactive stock queries, user watchlists, backtesting, and cloud deployment on Render.

**Success Definition:**
1. `python -m app.main` starts FastAPI + APScheduler in one process; Render health check passes
2. Weekday 08:30 CST LINE push received, format matches V2 spec (radar_score, sub-scores, reasons)
3. At least 5 interactive commands functional (查 XXXX, 今日雷達, 追蹤 XXXX, 我的清單, 幫助)
4. `python scripts/backtest_strategy.py --universe tw0050 --start 2024-01-01 --end 2026-06-13 --top-n 5 --holding-days 5` completes without error
5. `python scheduler.py --analysis-now` and `python verify_live_send.py --full` still work (backward compat)
6. All tests pass: test_scoring.py, test_formatter.py, test_backtest.py, test_commands.py

---

## Scope

### In-Scope

- Full `app/` package restructure (WS-1 through WS-5)
- FastAPI webhook + APScheduler embedded in one process
- radar_score 0-100 scoring with 5 sub-scores
- Event-based reasons: positive_reasons, negative_reasons, risk_notes, invalidation_conditions
- LINE Bot interactive commands + SQLite watchlist
- Backtesting CLI (yfinance historical)
- Render deployment (render.yaml, env vars)
- Backward-compat wrappers for scheduler.py and verify_live_send.py
- Tests and docs/scoring-spec.md

### Out-of-Scope

- Chip data / 法人籌碼 (chip_score = None, field reserved)
- Fundamental data
- OTC stocks (.TWO)
- Real-time / intraday data
- Market holiday handling
- LLM-generated explanations
- Paid APIs

---

## Hard Constraints

| Constraint | Value | Reason |
|------------|-------|--------|
| market_score isolation | Selection uses base_score (trend+momentum+volume+risk), NOT radar_score | Prevents market context from pushing weak stocks into strong_watchlist |
| RSI < 30 rule | RSI < 30 adds to risk_notes only, never to momentum_score | Oversold ≠ bullish |
| confidence 高 | Requires ALL 5 conditions simultaneously (radar_score ≥ 80, volume_ratio ≥ 1.2, risk_notes ≤ 1, positive_reasons ≥ 3, no signal conflict) | User correction: composite gate, not partial |
| No credentials in source | LINE credentials only in .env (git-ignored) | Security |
| Backward compat | python scheduler.py --analysis-now and python verify_live_send.py --full must still pass | User requirement |
| Formatter None-safety | formatter.py must never output None or nan in LINE messages | Crash prevention |

---

## Information Continuity Requirements

The following must be preserved across all workstreams:

| ID | Area | Rule |
|----|------|------|
| ICR-1 | scoring | Selection into strong_watchlist uses base_score (trend+momentum+volume+risk ≥ 70), NOT radar_score |
| ICR-2 | scoring | RSI < 30 = oversold, NOT bullish. Adds to risk_notes only |
| ICR-3 | scoring | confidence = 高 requires ALL 5 conditions simultaneously |
| ICR-4 | data model | negative_reasons ≠ risk_notes: negative_reasons is bearish reasoning (SELL stocks); risk_notes are cautions even for bullish stocks |
| ICR-5 | backward compat | Old CLI commands must still work after restructuring |
| ICR-6 | credentials | LINE_CHANNEL_SECRET is a NEW required env var for webhook signature verification |
| ICR-7 | data | yfinance .TW suffix mandatory; 2888.TW is known-delisted and gracefully skipped |

---

## Revision History

| Version | Date | Change | Approved By |
|---------|------|--------|-------------|
| 1.0 | 2026-06-13 | Initial contract — V2 mission from plan-handoff-package.yaml | user (wcy-0312) |
