# S0 Goal Boundary Packet

## Delivery Goal
Create a low-risk canary change proving that a target repository can complete managed AI Delivery governance from issue to PR evidence and final gate.

## Acceptance Criteria
- A branch named ai/GH-1-managed-status carries the implementation.
- The implementation exposes a managed status surface that can be verified by automated smoke checks.
- Local lint, typecheck, unit test, build, and smoke commands complete with exit code 0.
- Evidence includes manifest.json, diff.patch, rollback.md, run-log.md, verification logs, and surface observation.
- PR-2 points to GH-1 and GitHub Actions runs all required checks.
- Final evidence is committed as an evidence-only commit under evidence/GH-1/.

## Non-Goals
- No production deployment.
- No merge to main by automation.
- No secrets, billing, or irreversible data migration.
- No broad refactor beyond the canary surface.

## Risks
- Evidence can drift from implementation commit if not committed as a final evidence-only commit.
- Branch protection cannot be assumed unless GitHub confirms it or an approved governance control is recorded.
- Claude review must consume artifact evidence, not a chat-only summary.
