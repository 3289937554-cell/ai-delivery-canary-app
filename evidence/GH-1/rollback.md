# Rollback plan for GH-1 / PR-2

1. Stop rollout or disable the affected feature flag before reverting if a rollout is in progress.
2. Run `gh pr revert 2` after human approval, or run `git revert 4977986ab6fc83bf86d6125c8baf6e4b1ee6db06` on the protected branch.
3. Re-run lint, typecheck, test, build, smoke, and strict evidence validation after the rollback commit.
4. Attach rollback command output and post-rollback smoke evidence to the same GitHub Issue/PR audit trail.
