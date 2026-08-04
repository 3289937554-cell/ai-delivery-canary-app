# S2 Task Breakdown

Status: PASS.

1. Bind the work to GitHub Issue #3, branch `ai/GH-3-delivery-operations-console`, and an isolated worktree.
2. Use the real DeepSeek V4-Pro planner output to define product workflows, invariants, API boundaries, persistence, UI states, operations, and evidence requirements.
3. Implement domain, persistence, server, frontend, runbook, and deterministic verification adapters using TDD.
4. Harden model-execution and evidence validators with negative tests and immutable GitHub Action pins.
5. Run Ruff, strict Mypy, 71 unit tests, build, real smoke, strict manifest validation, and four-role execution validation.
6. Perform populated desktop and mobile browser acceptance and retain screenshots plus console results.
7. Obtain grounded DeepSeek V4-Pro reviewer and final decisions against the frozen implementation SHA.
8. Commit only evidence above the implementation commit, bind it to PR #9, and require lint, typecheck, test, build, smoke, and validate-evidence.
9. Stop before merge and hand the final decision to the human maintainer.
