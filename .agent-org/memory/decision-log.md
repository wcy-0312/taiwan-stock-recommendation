# Decision Log

> All Orchestrator decisions made outside of written rules, plus replanning decisions at Moderate/Major level.

---

## Format

```
## DL-NNN: [short title]

Date: YYYY-MM-DD
Checkpoint: [checkpoint number]
Made by: [role]
Level: [governance decision | replanning:Minor | replanning:Moderate | replanning:Major]

**Finding / Situation:**
[What triggered this decision]

**Decision:**
[What was decided]

**Reasoning:**
[Why]

**Who Was Involved:**
[roles]
```

---

## DL-1: Full app/ package restructure (not incremental)

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Finding / Situation:**
Project has grown from a single-file script to a system requiring webhook, scheduler, backtesting, and watchlist.

**Decision:**
Full `app/` package restructure (Option B chosen by user).

**Reasoning:**
Long-term maintainability; clear module boundaries; enables Render deployment.

**Who Was Involved:**
Human (wcy-0312), plan-formulation session

---

## DL-2: Deploy to Render Web Service (Free tier)

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Finding / Situation:**
LINE webhook requires HTTPS URL; local machine is unsuitable for production.

**Decision:**
Render Web Service (Free tier) chosen (Option C by user).

**Reasoning:**
Supports HTTPS webhook URL required by LINE, GitHub auto-deploy, env var management.

**Who Was Involved:**
Human (wcy-0312), plan-formulation session

---

## DL-3: APScheduler embedded in FastAPI process

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Finding / Situation:**
Separate Render Cron Job would require cache-sync between two processes.

**Decision:**
APScheduler runs inside the same FastAPI process.

**Reasoning:**
Avoids cache-sync issues; single deployment unit.

**Who Was Involved:**
Human (wcy-0312), plan-formulation session

---

## DL-4: FastAPI as web framework

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Decision:** FastAPI over Flask.

**Reasoning:** Async support, auto OpenAPI docs, modern Python standard.

**Who Was Involved:**
Human (wcy-0312)

---

## DL-5: SQLite for watchlist, JSON for daily analysis cache

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Decision:** SQLite watchlist at `data/watchlist.db`; JSON cache at `data/cache/`.

**Reasoning:** No external database server needed; Render persistent disk; JSON cache already working in V1.

**Who Was Involved:**
Human (wcy-0312)

---

## DL-6: chip_score = None (skipped, field reserved)

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Decision:** chip_score field is Optional[int] = None. Scoring skips it entirely.

**Reasoning:** No free chip data source available; field reserved for future integration.

**Who Was Involved:**
Human (wcy-0312)

---

## DL-7: Backtesting included (basic version)

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Decision:** Include backtesting CLI using yfinance historical data.

**Reasoning:** User explicitly chose to include; provides statistical basis for signal confidence.

**Who Was Involved:**
Human (wcy-0312)

---

## DL-8: radar_score 0-100 replaces composite_score -3/+3

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Decision:** V2 primary scoring system is radar_score 0-100 with 5 sub-scores.

**Reasoning:** More granular, easier to interpret, enables ranking.

**Who Was Involved:**
Human (wcy-0312)

---

## DL-9: Selection gate uses base_score, not radar_score

Date: 2026-06-13
Checkpoint: Pre-mission (plan phase)
Made by: Human (wcy-0312)
Level: governance decision

**Finding / Situation:**
market_score could push base_score ≤ 65 stocks into strong_watchlist if radar_score was the gate.

**Decision:**
`strong_watchlist` selection threshold is `base_score` (trend+momentum+volume+risk) ≥ 70. market_score is added after selection and affects display + ranking only.

**Reasoning:**
Prevents market context from overriding weak individual stock signals.

**Who Was Involved:**
Human (wcy-0312), plan-formulation session
