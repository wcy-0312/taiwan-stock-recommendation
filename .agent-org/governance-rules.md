# Governance Rules

> Stability: MEDIUM — revise only when a pattern appears in at least 3 distinct cases across tasks.

---

## Document Revision Rules

| Document | Can Be Revised When | Who Authorizes |
|----------|---------------------|----------------|
| mission-contract.md | Core assumption invalidated | Human + Orchestrator |
| team-roster.md | After checkpoint review, meets team-evolution-rules criteria | Orchestrator |
| governance-rules.md | Pattern observed in ≥3 distinct cases | Orchestrator + human sign-off |
| review-protocol.md | After checkpoint review | Orchestrator |
| replanning-rules.md | After checkpoint review | Orchestrator |
| artifact-backend.md | Never mid-task; only between tasks | Human |
| current/handoff-package.md | Only by Orchestrator after checkpoint review | Orchestrator |
| current/staging-buffer.md | Anytime during execution | Any agent |

---

## Orchestrator Discretion Boundaries

The Orchestrator may exercise judgment when rules do not cover a situation. When they do:

1. State the situation explicitly
2. State which rule is absent or ambiguous
3. State the decision made and reasoning
4. Record the full entry in `memory/decision-log.md`

The Orchestrator may **not** silently override a rule. If a rule appears wrong, they must record the deviation and flag it for human review at the next checkpoint.

---

## Rule Promotion Threshold

A behavior observed in practice becomes a rule candidate only when:

- It appears in at least **3 different cases** in the case-library
- The pattern is non-trivial (not already covered by an existing rule)
- The Orchestrator proposes promotion in writing
- A human confirms before the rule is added to this file

---

## Rule Gap Handling

When no rule covers the current situation:

1. Do not improvise silently
2. Log the gap to `memory/decision-log.md`
3. Handle based on the closest analogous rule, explicitly noted
4. Flag for review at next checkpoint

---

## Governance File Locations

All governance files live inside `.agent-org/`. No governance document lives in the project workspace. No task artifact lives inside `.agent-org/`.
