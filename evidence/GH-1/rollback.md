# Rollback plan for GH-1 / PR-2

1. Stop rollout or disable the affected feature flag before reverting if a rollout is in progress.
2. Run `gh pr revert 2` after human approval, or run `git revert 9f7beabdaeea39c006d575c606e4eb55829cce28` on the protected branch.
3. Re-run lint, typecheck, test, build, smoke, and strict evidence validation after the rollback commit.
4. Attach rollback command output and post-rollback smoke evidence to the same GitHub Issue/PR audit trail.
