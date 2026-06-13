# Artifact Backend

> Stability: HIGH — do not change mid-task. Backend changes require human approval between tasks.

---

## Backend: local-git

Artifacts are stored as files in the project repository and tracked via git commits.

---

## Storage Convention

| Artifact Type | Location |
|--------------|----------|
| Source code | `app/`, `scripts/`, `tests/` |
| Data files | `data/` |
| Docs | `docs/` |
| Config | repo root (`render.yaml`, `requirements.txt`, `.env.example`) |
| Backward-compat wrappers | repo root (`scheduler.py`, `verify_live_send.py`) |

Artifact IDs use the format: `ART-NNN` (e.g., `ART-001`)

---

## Submission Protocol

When an Executor completes an artifact:
1. Write the artifact file(s) to the appropriate location above
2. Record it in `.agent-org/artifact-manifest.md` (artifact_id, path, status: pending_review)
3. Write a summary to `.agent-org/current/staging-buffer.md`
4. Notify the Orchestrator

---

## Review and Finalization

When the Verifier Lead approves an artifact:
1. Update `artifact-manifest.md` review_status to `approved`
2. Commit the artifact to git with message: `feat(ART-NNN): <description>`
3. Record the commit hash in `artifact-manifest.md`

---

## No Artifacts Inside .agent-org

`.agent-org/` contains governance documents only. Task artifacts (code, data, docs) always live in the project workspace.
