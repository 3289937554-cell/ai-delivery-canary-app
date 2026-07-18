# Rollback plan for GH-3 / PR-4

1. Stop rollout or disable the affected feature flag before reverting if a rollout is in progress.
2. Run `gh pr revert 4` after human approval, or run `git revert 6bb9497b3e4d19866e7201aca08c20b8d180033a` on the protected branch.
3. Re-run lint, typecheck, test, build, smoke, and strict evidence validation after the rollback commit.
4. Attach rollback command output and post-rollback smoke evidence to the same GitHub Issue/PR audit trail.
