# Codex Implementation Plan for GH-1

## Objective
Add a managed delivery status capability that demonstrates the target application can participate in the AI Delivery S0-S10 governance workflow while keeping implementation small and reversible.

## Repository Anchors
- Application code and governance template sync: files changed by implementation commit 9f7beabdaeea39c006d575c606e4eb55829cce28.
- Verification adapters: scripts/lint.sh, scripts/typecheck.sh, scripts/build.sh, scripts/smoke.sh.
- Test surface: tests discovered by python3 -B -m unittest discover -s tests -v.
- Evidence surface: evidence/GH-1/manifest.json, evidence/GH-1/diff.patch, evidence/GH-1/logs, evidence/GH-1/reports, evidence/GH-1/surface-evidence, evidence/GH-1/rollback.md.

## Steps
1. Confirm target branch is ai/GH-1-managed-status and not main.
2. Inspect current application structure without writing during exploration.
3. Implement the managed status behavior with minimal production code changes.
4. Run lint, typecheck, unit tests, build, and smoke verification.
5. Generate manifest, diff patch, rollback plan, surface observation, and run log.
6. Submit a final evidence-only commit under evidence/GH-1/.
7. Run aid delivery final-check and GitHub validate-evidence before human merge consideration.

## Boundaries
- No automatic merge.
- No production deployment.
- No secrets or credential edits.
- No broad filesystem writes.
- No work on main for implementation.
