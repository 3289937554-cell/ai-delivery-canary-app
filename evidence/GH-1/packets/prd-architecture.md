# S1 PRD and Architecture Packet

## Product Requirement
The application must show a managed delivery status suitable for smoke verification. The feature must be deterministic and small enough to audit through a PR diff.

## Architecture
- Keep the canary capability inside the existing application structure.
- Keep verification in repository scripts so CI and local execution use the same command surface.
- Evidence remains separate from implementation and is added only in the final evidence commit.
- The authoritative gate remains GitHub PR, CI, manifest validation, and aid final-check.

## Control Constraints
- Branch pattern: ai/GH-1-managed-status.
- Evidence root: evidence/GH-1/.
- Required local commands: lint, typecheck, test, build, smoke.
- Rollback must be possible by reverting the implementation and evidence commits.
