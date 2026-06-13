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
| — | — | — | (none yet — populated as workstreams complete) | — | — |

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
