# Provenance

> Records the origin of this .agent-org/ structure and key decisions made before the first checkpoint.

---

## Origin

| Field | Value |
|-------|-------|
| Created by | create-agent-organization skill (Claude Code) |
| Created date | 2026-06-13 |
| Source plan | `agent-organization-framework/plan-handoff-package.yaml` (schema: plan-handoff-package-v1) |
| Design spec | `taiwan-stock-recommendation/docs/superpowers/specs/2026-06-13-taiwan-stock-radar-v2-design.md` |
| Human plan doc | `agent-organization-framework/計畫書_台股智能雷達LINE-Bot.md` |
| Confirmed by | user (wcy-0312), 2026-06-13, message: "確認" |

---

## Pre-existing Context

This project is a V2 upgrade of a working V1 system:
- V1 successfully sent LINE push notifications (confirmed 2026-06-13)
- V1 used flat-file structure (no `app/` package)
- V1 used composite_score -3/+3; V2 replaces with radar_score 0-100

The taiwan-stock-recommendation repo was created fresh on 2026-06-13 with V1 code committed.

---

## Plan Decisions Carried Into This Mission

| DL-ID | Decision | Status |
|-------|----------|--------|
| DL-1 | Full app/ package restructure | confirmed |
| DL-2 | Deploy to Render Web Service (Free tier) | confirmed |
| DL-3 | APScheduler embedded in FastAPI process | confirmed |
| DL-4 | FastAPI as web framework | confirmed |
| DL-5 | SQLite for watchlist, JSON for daily cache | confirmed |
| DL-6 | chip_score = None (skipped, field reserved) | confirmed |
| DL-7 | Backtesting included (basic, yfinance historical) | confirmed |
| DL-8 | radar_score 0-100 replaces composite_score -3/+3 | confirmed |
| DL-9 | Selection gate uses base_score, not radar_score | confirmed |
