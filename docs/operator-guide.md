# ART-007: Operator Deployment Guide
# 台股智能推薦系統 — Final Configuration & Verification

> Checkpoint: 5 — Operator Deployment
> Status: All code complete (ART-001 through ART-006 approved). One user action required: supply .env credentials.
> Last pipeline run: 2026-06-13 — 49/50 tickers, 5 recommendations (3 BUY: 2412, 2884, 2891 / 2 SELL: 2330, 2317)

---

## Prerequisites

- Windows machine with Miniconda installed
- conda environment `linebot` (Python 3.10.20) already configured
- LINE Messaging API channel with:
  - A Channel Access Token (from LINE Developers console)
  - Your LINE User ID (the user to receive push messages)

---

## Step 1 — Create the .env File

Create a file named `.env` at the project root:

```
C:\Users\NM6124020\Desktop\Code\agent-organization-framework\.env
```

Contents (replace placeholders with your actual values):

```
LINE_CHANNEL_ACCESS_TOKEN=<your_channel_access_token_here>
LINE_USER_ID=<your_line_user_id_here>
```

How to obtain these values:
- LINE_CHANNEL_ACCESS_TOKEN: LINE Developers console → your channel → Messaging API tab → Channel access token (long-lived)
- LINE_USER_ID: LINE Developers console → your channel → Messaging API tab → "Your user ID" field

IMPORTANT: Never commit the .env file to git. It is listed in .gitignore (or should be added).

---

## Step 2 — Verify Credentials

Run this command to confirm credentials are correctly set:

```
PYTHONIOENCODING=utf-8 conda run -n linebot --no-capture-output python artifacts/checkpoint-4/ART-006/verify_live_send.py --check-env
```

Expected output:
```
[PASS] LINE_CHANNEL_ACCESS_TOKEN found: <masked>
[PASS] LINE_USER_ID found: <your_id>
[PASS] .env credentials look valid. Ready for live send test.
```

---

## Step 3 — Full End-to-End Verification (Checkpoint 4 Acceptance Criteria)

Run ART-006 in full mode to execute the complete pipeline and send a real LINE message:

```
PYTHONIOENCODING=utf-8 conda run -n linebot --no-capture-output python artifacts/checkpoint-4/ART-006/verify_live_send.py --full
```

This will:
1. Fetch OHLCV data for 0050 component stocks (49/50 expected; 2888.TW is delisted and skipped)
2. Compute MA crossover / RSI / MACD signals
3. Select top 3-5 stocks by composite score
4. Cache the formatted Chinese-language recommendation message
5. Send the message to your LINE app via the Messaging API

All five Checkpoint 4 acceptance criteria should print [PASS].

---

## Step 4 — Alternative: Send Cached Message Only

If the analysis pipeline already ran today and the cache is fresh:

```
PYTHONIOENCODING=utf-8 conda run -n linebot --no-capture-output python artifacts/checkpoint-4/ART-006/verify_live_send.py --send-now
```

The cached message is stored at:
```
artifacts/checkpoint-3/ART-005/.scheduler-cache/pending-message.json
```

---

## Step 5 — Start the Automated Scheduler

Once credentials are verified and a test message is received, start the scheduler for daily automated operation:

```
PYTHONIOENCODING=utf-8 conda run -n linebot --no-capture-output python artifacts/checkpoint-3/ART-005/scheduler.py
```

The scheduler runs two jobs each weekday:
- 14:00 CST — Analysis pipeline (fetches data, computes signals, caches recommendation message)
- 08:30 CST — LINE push notification (sends cached message to your LINE app)

IMPORTANT: The machine must remain running for the scheduler to fire. There is no built-in restart-on-failure or Windows Task Scheduler integration in the current MVP.

CLI flags for manual testing:
- `--analysis-now` : Run the analysis pipeline immediately (does not wait for 14:00)
- `--send-now`     : Send the cached message immediately (does not wait for 08:30)
- `--dry-run`      : Run analysis only, print message to console, do not send LINE message

---

## Artifact Map

| Artifact | Path | Purpose |
|----------|------|---------|
| ART-001 | artifacts/checkpoint-1/ART-001/data_pipeline.py | Fetches OHLCV data via yfinance |
| ART-002 | artifacts/checkpoint-1/ART-002/analysis_engine.py | MA crossover / RSI / MACD signals + composite score |
| ART-003 | artifacts/checkpoint-2/ART-003/recommendation_generator.py | Top stock selection + Chinese plain-language explanations |
| ART-004 | artifacts/checkpoint-2/ART-004/line_notifier.py | LINE Messaging API push notification |
| ART-005 | artifacts/checkpoint-3/ART-005/scheduler.py | APScheduler daily jobs (entry point for production use) |
| ART-006 | artifacts/checkpoint-4/ART-006/verify_live_send.py | Acceptance-criteria runner (use to verify end-to-end) |
| .env.example | artifacts/checkpoint-2/ART-004/.env.example | Template showing required credential fields |

---

## Known Limitations

| Issue | Severity | Workaround |
|-------|----------|------------|
| 2888.TW (新光金) not found by yfinance — possibly delisted | Minor | Pipeline skips gracefully; ticker list in ART-001 may need periodic updates |
| Scheduler requires machine to stay running | Minor | Consider Windows Task Scheduler or a dedicated server for production |
| PYTHONIOENCODING=utf-8 must be set for Windows Chinese output | Minor | Always use the conda run command forms shown above |
| Cache key is today's date; stale cache from yesterday is not sent automatically | Minor | Run --analysis-now before --send-now if using on a new day without scheduler |

---

## Mission Success Definition

The mission (mission-contract.md) is satisfied when:
- ART-006 --full returns [PASS] for all 5 acceptance criteria, AND
- The user confirms receiving a LINE message containing: today's date, top stock tickers, BUY/SELL labels, Chinese plain-language explanations, and disclaimer

No further agent checkpoints are required after this confirmation.
