# User Flows

Generated from application-blueprint.json; do not edit individual screens without updating the blueprint.

## TASK-MONITOR-RUN — Monitor a governed run

- Flows: FLOW-GOVERNED-RUN
- Role: ROLE-OPERATOR, ROLE-OWNER, ROLE-AUDITOR
- Entry: primary-navigation, global-search, notification
- Action: Create or resume a run
- Success: The operator can see the current checkpoint, next legal action, and latest event receipt.
- Recovery: Show the blocking reason, owner, retry or resume action, and preserve the run revision.

## TASK-RESOLVE-HUMAN-TASK — Resolve a bound human task

- Flows: FLOW-GOVERNED-RUN, FLOW-HUMAN-DECISION
- Role: ROLE-OWNER
- Entry: run-detail, approvals-navigation
- Action: Review bound evidence and submit an allowed decision
- Success: The allowed decision is recorded with actor, reason, revision, evidence hash, and receipt hash.
- Recovery: Keep the drawer open, identify stale or mismatched evidence, and require refresh instead of accepting a guess.

## TASK-INSPECT-EVIDENCE — Inspect verified evidence

- Flows: FLOW-GOVERNED-RUN
- Role: ROLE-OWNER, ROLE-AUDITOR
- Entry: evidence-navigation, run-detail, approval-drawer
- Action: Verify classification, size, and hash metadata
- Success: The auditor can confirm an evidence reference without receiving raw secrets, absolute paths, or model output.
- Recovery: Explain why content is withheld and keep metadata available for audit without exposing restricted bytes.
