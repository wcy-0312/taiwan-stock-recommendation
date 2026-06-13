# Review Protocol

> Stability: MEDIUM — update acceptance criteria after each checkpoint based on what was learned.

---

## Checkpoint Trigger Conditions

A checkpoint is triggered by a **decision point**, not by task completion.

Triggers include:
- A major assumption has been validated or invalidated
- A key artifact is ready for a go/no-go decision
- The team has reached a fork: continuing requires a direction choice
- An unexpected finding changes the risk profile

Checkpoints are **not** triggered by:
- Completing a step in the plan
- Finishing a subagent's work
- Hitting a time boundary (unless it coincides with a decision point)

---

## Evaluation Dimensions

For each checkpoint, the Verifier Lead evaluates submitted artifacts along these dimensions:

| Dimension | Question |
|-----------|----------|
| Correctness | Does the artifact do what it was supposed to do? |
| Completeness | Are all required parts present? |
| Consistency | Is it consistent with the mission-contract and prior decisions? |
| Risk | Does anything here introduce unacceptable risk? |

---

## Acceptance Criteria

### Checkpoint 0 — Bootstrap

Acceptance criteria: `.agent-org/` directory created and all governance files populated. Orchestrator has read handoff-package and confirmed readiness to proceed.

Declared complete by: Human (confirmed via create-agent-organization skill).

---

### Checkpoint 1 — Data & Features Importable

**Trigger:** WS-1 complete

Acceptance criteria:
- `from app.data.universe_provider import get_universe` returns list of ≥49 tickers with name/sector
- `from app.data.yfinance_provider import fetch_ohlcv` fetches OHLCV for a sample ticker; `latest_data_date` derived from DataFrame index (not `date.today()`)
- `from app.features.technical import compute_technical_features` returns dict with no NaN values
- `from app.features.volume import compute_volume_features` returns dict with no NaN values
- `from app.features.risk import compute_risk_features` returns dict with no NaN values
- 2888.TW is gracefully skipped (no exception raised)
- `app/__init__.py` and all sub-package `__init__.py` files exist

Declared complete by: Verifier Lead.

---

### Checkpoint 2 — Scoring & Formatter Correct

**Trigger:** WS-2 complete

Acceptance criteria:
- `radar_score` always in [0, 100] (clamped)
- Selection uses `base_score` (trend+momentum+volume+risk), NOT `radar_score` — verified by inspection
- RSI < 30 does not contribute to `momentum_score` — verified by unit test
- `confidence = 高` requires ALL 5 conditions simultaneously — verified by unit test
- `formatter.py` produces no `None` or `nan` in output strings — verified by test_formatter.py
- LINE messages split at ≤3 messages, each ≤5000 chars

Declared complete by: Verifier Lead.

---

### Checkpoint 3 — LINE Bot & Render Config Ready

**Trigger:** WS-3 complete

Acceptance criteria:
- `app/main.py` starts without error (`python -m app.main` or `uvicorn app.main:app`)
- `GET /health` returns 200
- `POST /webhook` endpoint exists with LINE signature verification logic
- `render.yaml` declares all 3 required env vars (LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID, LINE_CHANNEL_SECRET)
- SQLite watchlist CRUD: add, remove, list all work
- `python scheduler.py --analysis-now` still passes (backward compat)
- `python verify_live_send.py --full` still passes (backward compat)

Declared complete by: Verifier Lead.

---

### Checkpoint 4 — Backtesting CLI Functional

**Trigger:** WS-4 complete

Acceptance criteria:
- `python scripts/backtest_strategy.py --universe tw0050 --start 2024-01-01 --end 2026-06-13 --top-n 5 --holding-days 5` completes without error
- Outputs trade_count, win_rate, avg_return, annualized_return, max_drawdown, sharpe_ratio
- If trade_count < 10, outputs "歷史樣本不足"
- `historical_*` fields in StockRadarResult remain `Optional[float] = None` when backtesting not invoked

Declared complete by: Verifier Lead.

---

### Checkpoint 5 — Tests Green & Docs Complete

**Trigger:** WS-5 complete

Acceptance criteria:
- All 4 test files pass: test_scoring.py, test_formatter.py, test_backtest.py, test_commands.py
- `docs/scoring-spec.md` contains all scoring rules (sub-score bands, direction thresholds, 5 confidence conditions, RSI < 30 rule, market_score isolation rule)
- README updated with V2 setup and usage instructions

Declared complete by: Verifier Lead + Human.

---

## Handoff-Package Audit Checklist

The Verifier Lead checks the handoff-package against this list before approving:

- [ ] Status summary is accurate (no inflated claims)
- [ ] All referenced artifact_ids exist in artifact-manifest.md
- [ ] Decisions include reasoning, not just conclusions
- [ ] Next stage starting point is unambiguous
- [ ] All known risks and open questions are surfaced
- [ ] No full artifact content is pasted into the handoff (use artifact_id references only)
