# Rollback plan for GH-999 / PR-9

1. Stop rollout or disable the affected feature flag before reverting if a rollout is in progress.
2. Run `gh pr revert 9` after human approval, or run `git revert ddb9e5c226d952819268e53d42569b9b56c0e232` on the protected branch.
3. Re-run lint, typecheck, test, build, smoke, and strict evidence validation after the rollback commit.
4. Attach rollback command output and post-rollback smoke evidence to the same GitHub Issue/PR audit trail.
