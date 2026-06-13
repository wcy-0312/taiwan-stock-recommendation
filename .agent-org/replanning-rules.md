# Replanning Rules

> Stability: MEDIUM — adjust severity thresholds after checkpoint review if calibration is off.

---

## Severity Classification

When an agent discovers something unexpected, they classify it before acting:

| Level | Description | Handling |
|-------|-------------|----------|
| Minor | Does not affect direction; only affects implementation detail | Executor self-adjusts, records in staging-buffer |
| Moderate | Affects the method for the current step | Orchestrator + relevant Lead convene; plan is adjusted locally |
| Major | Invalidates a core assumption | All agents convene; mission-contract may need revision; human intervention required |

---

## Classification Guidance

**Minor** — ask: "Can the Executor proceed to the same goal, just slightly differently?" If yes, it's minor.

**Moderate** — ask: "Does this change how we approach the current step, but not the overall goal?" If yes, it's moderate.

**Major** — ask: "Does this finding mean our goal, success definition, or core constraints are wrong?" If yes, it's major.

When in doubt, escalate one level rather than under-escalating.

---

## What Replanning Changes

Replanning **may** update:
- Steps within the current checkpoint plan
- The acceptance criteria for the next checkpoint
- Resource allocation among agents

Replanning **may not** update:
- mission-contract.md (requires Major finding + human)
- team-roster.md (governed by team-evolution-rules.md)
- governance-rules.md (requires 3-case pattern + human sign-off)

---

## Recording

All replanning decisions above Minor level must be recorded in `memory/decision-log.md` with:
- The finding that triggered replanning
- The severity classification and reasoning
- The decision made
- Who was involved
