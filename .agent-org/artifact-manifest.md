# Artifact Manifest

> All submitted artifacts are listed here. Verifier Lead updates review_status after review.

---

## Format

```
| artifact_id | workstream | path | description | status | commit |
```

Status values: `pending_review` | `approved` | `rejected` | `superseded`

---

## Artifacts

| artifact_id | workstream | path | description | status | commit |
|-------------|------------|------|-------------|--------|--------|
| ART-WS1-01 | WS-1 | `app/__init__.py` | App package root | approved | checkpoint-2 |
| ART-WS1-02 | WS-1 | `app/config.py` | Centralised configuration | approved | checkpoint-2 |
| ART-WS1-03 | WS-1 | `app/data/__init__.py` | Data sub-package | approved | checkpoint-2 |
| ART-WS1-04 | WS-1 | `app/data/universe_provider.py` | tw0050 universe loader | approved | checkpoint-2 |
| ART-WS1-05 | WS-1 | `app/data/yfinance_provider.py` | OHLCV fetcher; skips 2888.TW | approved | checkpoint-2 |
| ART-WS1-06 | WS-1 | `app/features/__init__.py` | Features sub-package | approved | checkpoint-2 |
| ART-WS1-07 | WS-1 | `app/features/technical.py` | MA/RSI/MACD features | approved | checkpoint-2 |
| ART-WS1-08 | WS-1 | `app/features/volume.py` | Volume features | approved | checkpoint-2 |
| ART-WS1-09 | WS-1 | `app/features/risk.py` | ATR/support/resistance features | approved | checkpoint-2 |
| ART-WS1-10 | WS-1 | `data/universes/tw0050.json` | 50-ticker universe definition | approved | checkpoint-2 |
| ART-WS2-01 | WS-2 | `app/scoring/__init__.py` | Scoring sub-package | approved | checkpoint-2 |
| ART-WS2-02 | WS-2 | `app/scoring/models.py` | StockRadarResult dataclass | approved | checkpoint-2 |
| ART-WS2-03 | WS-2 | `app/scoring/radar.py` | 5-sub-score radar engine | approved | checkpoint-2 |
| ART-WS2-04 | WS-2 | `app/scoring/reasons.py` | Event-based reasons/risk_notes | approved | checkpoint-2 |
| ART-WS2-05 | WS-2 | `app/scoring/market_context.py` | Universe-level market scorer | approved | checkpoint-2 |
| ART-WS2-06 | WS-2 | `app/recommendation/__init__.py` | Recommendation sub-package | approved | checkpoint-2 |
| ART-WS2-07 | WS-2 | `app/recommendation/selector.py` | base_score selection logic (ICR-1) | approved | checkpoint-2 |
| ART-WS2-08 | WS-2 | `app/recommendation/formatter.py` | None-safe LINE message formatter | approved | checkpoint-2 |
| ART-WS2-09 | WS-2 | `app/pipeline.py` | Full analysis pipeline orchestrator | approved | checkpoint-2 |
| ART-WS2-10 | WS-2 | `app/linebot/__init__.py` | LINE Bot sub-package stub | approved | checkpoint-2 |
| ART-WS2-11 | WS-2 | `app/backtesting/__init__.py` | Backtesting sub-package stub | approved | checkpoint-2 |
| ART-WS3-01 | WS-3 | `app/linebot/watchlist.py` | SQLite-backed per-user watchlist CRUD | pending_review | checkpoint-3 |
| ART-WS3-02 | WS-3 | `app/linebot/notifier.py` | LINE Messaging API push/reply client | pending_review | checkpoint-3 |
| ART-WS3-03 | WS-3 | `app/linebot/commands.py` | Interactive command dispatcher (5 commands) | pending_review | checkpoint-3 |
| ART-WS3-04 | WS-3 | `app/linebot/webhook.py` | FastAPI router with LINE signature verification | pending_review | checkpoint-3 |
| ART-WS3-05 | WS-3 | `app/main.py` | FastAPI + APScheduler entry point | pending_review | checkpoint-3 |
| ART-WS3-06 | WS-3 | `render.yaml` | Render deployment config (all 3 env vars) | pending_review | checkpoint-3 |
| ART-WS3-07 | WS-3 | `requirements.txt` | Python dependency manifest | pending_review | checkpoint-3 |
| ART-WS3-08 | WS-3 | `.env.example` | Updated credential template (adds LINE_CHANNEL_SECRET) | pending_review | checkpoint-3 |
| ART-WS3-09 | WS-3 | `scheduler.py` | Backward-compat wrapper to app.pipeline (V2) | pending_review | checkpoint-3 |
| ART-WS3-10 | WS-3 | `verify_live_send.py` | Backward-compat wrapper for live-send verification (V2) | pending_review | checkpoint-3 |

---

## Pre-existing Artifacts (V1 — carried forward)

The following V1 files exist in the repo and will be refactored or replaced by V2 workstreams:

| file | v1_status | v2_disposition |
|------|-----------|----------------|
| `analysis_engine.py` | working | superseded by `app/` modules |
| `data_pipeline.py` | working | superseded by `app/data/` |
| `line_notifier.py` | working | superseded by `app/linebot/notifier.py` |
| `recommendation_generator.py` | working (V1 phase 1 applied) | superseded by `app/recommendation/` |
| `scheduler.py` | working | becomes thin wrapper |
| `verify_live_send.py` | working (path bug fixed) | becomes thin wrapper |
