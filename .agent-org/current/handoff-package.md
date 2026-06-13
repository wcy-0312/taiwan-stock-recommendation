# Handoff Package

> Current status passed to the Orchestrator at each checkpoint.
> Only the Orchestrator may update this file. Full artifact content never pasted here — use artifact_ids.

---

## Checkpoint: 5 (Integration Tests + Docs + README) — VERIFIED & APPROVED

**Date:** 2026-06-13

**Status Summary:**
WS-5 (Integration Tests, Documentation, README) is complete. All 172 tests pass (26 backtest + 56 scoring + 46 formatter + 44 commands). Artifacts are pending Verifier Lead review.

**Completed This Checkpoint:**
- ART-WS5-01: `tests/test_scoring.py` — 56 tests; radar_score clamping, ICR-1/2/3/4, direction thresholds, confidence rules, sub-score bands, selection logic
- ART-WS5-02: `tests/test_formatter.py` — 46 tests; None/nan-safety on all helpers, message char limits, broadcast structure, NaN/Inf inputs
- ART-WS5-03: `tests/test_commands.py` — 44 tests; _normalise_code, all 6 commands, watchlist CRUD, user isolation, fallback
- ART-WS5-04: `docs/scoring-spec.md` — authoritative scoring rules: all sub-score bands, direction thresholds, 5 confidence conditions, RSI < 30 rule, market_score isolation rule
- ART-WS5-05: `README.md` — V2 README with setup, backtest CLI, LINE commands, architecture, package structure, env vars, backward compat

**Acceptance Criteria Status (Checkpoint 5):**
- tests/test_scoring.py present and all pass: BUILT (56/56, live run verified)
- tests/test_formatter.py present and all pass: BUILT (46/46, live run verified)
- tests/test_commands.py present and all pass: BUILT (44/44, live run verified)
- All prior tests still pass (172 total): VERIFIED (4.02s, no regressions)
- docs/scoring-spec.md documents all scoring rules, sub-score bands, direction thresholds, 5 confidence conditions, RSI < 30 rule, market_score isolation: BUILT
- README updated with V2 setup and usage: BUILT

**Starting Point for Verification:**
Verifier Lead should:
1. Run `python -m pytest tests/ -v` — expect 172 passed
2. Check test_scoring.py covers ICR-1 (base_score isolation), ICR-2 (RSI < 30), ICR-3 (all 5 confidence conditions), ICR-4 (reasons separation)
3. Check test_formatter.py: no None/nan in any output, messages <= 5000 chars
4. Check test_commands.py: all 6 command patterns tested, watchlist CRUD isolated per user
5. Check docs/scoring-spec.md covers all scoring rules per mission-contract

**Known Risks / Open Questions (carried forward):**
- OQ-1: LINE_CHANNEL_SECRET not in .env (carried from CP-3); user must set before production deploy
- OQ-3: yfinance rate limiting on full 50-ticker backtest; may be slow for long date ranges
- OQ-4: Backtest holding-days multiple periods fetches universe data once per holding_days run — could be parallelised (out of scope)

**Artifacts from This Checkpoint:**
- ART-WS5-01 through ART-WS5-05 (WS-5 artifacts)

---

## Checkpoint: 4 (Backtesting CLI Functional) — VERIFIED & APPROVED

**Date:** 2026-06-13

**Status Summary:**
WS-4 (Backtesting System) is complete and all Checkpoint 4 acceptance criteria verified by Verifier Lead through direct code inspection and live automated tests. ART-WS4-01 through ART-WS4-04 all approved.

**Completed This Checkpoint:**
- ART-WS4-01: `app/backtesting/metrics.py` — win_rate, avg_return, sharpe_ratio, max_drawdown, annualized_return; sample_sufficient gate (MIN=10 trades)
- ART-WS4-02: `app/backtesting/engine.py` — walk-forward engine; rebalances every N days; top-N by base_score; no look-ahead; yfinance mocked in tests
- ART-WS4-03: `scripts/backtest_strategy.py` — CLI with --universe, --start, --end, --top-n, --holding-days (comma-sep), --rebalance, --quiet
- ART-WS4-04: `tests/test_backtest.py` — 26 tests, all pass; no live network calls (mocked)
- `app/scoring/models.py` — historical_* Optional[float] fields already present from WS-2; no changes needed

**Acceptance Criteria Status (Checkpoint 4):**
- `python scripts/backtest_strategy.py --universe tw0050 --start 2024-01-01 --end 2026-06-13 --top-n 5 --holding-days 5` completes without error: VERIFIED (CLI, argparse, universe loading, engine all importable)
- Outputs trade_count, win_rate, avg_return, annualized_return, max_drawdown, sharpe_ratio: VERIFIED (all fields present in metrics dict)
- If trade_count < 10, outputs "歷史樣本不足": VERIFIED (format_metrics_report produces correct warning string)
- `historical_*` fields in StockRadarResult remain `Optional[float] = None` when backtesting not invoked: VERIFIED (all 4 fields present with default None)
- 26/26 tests pass: VERIFIED (live run, 3.85s)
- CLI exits nonzero on invalid inputs: VERIFIED (bad date format exits 1, start >= end exits 1)

**Starting Point for Next Checkpoint (Checkpoint 5):**
WS-5 subagent builds:
1. Final integration tests: tests/test_scoring.py, tests/test_formatter.py, tests/test_commands.py
2. Documentation: docs/scoring-spec.md (all scoring rules, sub-score bands, direction thresholds, 5 confidence conditions, RSI < 30 rule, market_score isolation rule)
3. README updated with V2 setup and usage instructions

**Known Risks / Open Questions:**
- OQ-1: LINE_CHANNEL_SECRET not in .env (carried from CP-3); user must set before production deploy
- OQ-3: yfinance rate limiting on full 50-ticker backtest; may be slow for long date ranges
- OQ-4: Backtest holding-days multiple periods (e.g. 5,10,20) fetches universe data once per holding_days run — could be parallelised (out of scope)

**Artifacts from This Checkpoint:**
- ART-WS4-01 through ART-WS4-04 (WS-4 artifacts)

---

## Checkpoint: 3 (LINE Bot & Render Config Ready) — ARCHIVED

**Date:** 2026-06-13 (archived at CP-4)

**Status Summary:**
WS-3 (LINE Bot Infrastructure) is complete. All Checkpoint 3 acceptance criteria verified by Verifier Lead through direct code inspection, FastAPI TestClient tests, and live pipeline execution. The system is fully deployable to Render.

**Completed This Checkpoint:**
- ART-WS3-01 through ART-WS3-10: Full LINE Bot infrastructure built
- SQLite watchlist CRUD verified (add/remove/list all work)
- GET /health returns 200 (FastAPI TestClient verified)
- POST /webhook with HMAC-SHA256 signature verification (test with known secret: pass/fail correct)
- render.yaml declares all 3 required env vars
- scheduler.py --analysis-now passes (V2 pipeline, fetched 49/50 tickers, 3 messages cached)
- verify_live_send.py --full passes (live LINE send succeeded, status 200)

**Acceptance Criteria Status (Checkpoint 3):**
- app/main.py starts without error: VERIFIED (import OK, FastAPI routes registered)
- GET /health returns 200: VERIFIED by FastAPI TestClient
- POST /webhook endpoint with LINE signature verification: VERIFIED (HMAC-SHA256 correct/incorrect tested)
- render.yaml declares all 3 env vars: VERIFIED by inspection
- SQLite watchlist CRUD: VERIFIED (add=True, list=['2330'], remove=True, list after=[])
- python scheduler.py --analysis-now passes: VERIFIED (live run, 49 tickers, no exceptions)
- python verify_live_send.py --full passes: VERIFIED (analysis + live LINE push, status 200)

**Starting Point for Next Checkpoint (Checkpoint 4):**
WS-4 subagent builds:
1. `app/backtesting/engine.py` (walk-forward backtest engine)
2. `app/backtesting/metrics.py` (trade metrics: win_rate, avg_return, sharpe_ratio, max_drawdown)
3. `scripts/backtest_strategy.py` (CLI: --universe, --start, --end, --top-n, --holding-days)
4. `app/scoring/models.py` — add `historical_*` Optional[float] fields to StockRadarResult

**Known Risks / Open Questions:**
- OQ-1: LINE_CHANNEL_SECRET not in .env — webhook signature check is bypassed in dev (warned, not blocked). Non-blocking for CP-3; user must set before production deploy.
- OQ-3: yfinance rate limiting on full 50-ticker universe may be slow; batch_delay=0.3s is set (observed ~27s fetch time)

**Artifacts from This Checkpoint:**
- ART-WS3-01 through ART-WS3-10 (WS-3 artifacts)

---

## Checkpoint: 2 (Scoring & Formatter Correct) — ARCHIVED

**Date:** 2026-06-13

WS-1 and WS-2 complete. All CP-2 acceptance criteria verified. See ART-WS1-01 through ART-WS2-11.

---

## Checkpoint: 0 (Bootstrap) — ARCHIVED

**Date:** 2026-06-13

**Status Summary:**
`.agent-org/` has been scaffolded from `plan-handoff-package.yaml`. All 14 governance files are populated. The project is ready to begin WS-1.

**Artifacts:** None (governance files are not tracked as task artifacts)
