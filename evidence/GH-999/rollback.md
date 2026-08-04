# Rollback plan for GH-999 / PR-7

1. Stop rollout or disable the affected feature flag before reverting if a rollout is in progress.
2. Run `gh pr revert 7` after human approval, or run `git revert f07fde7c284f436c634b81255b1ce56fb16a86dd` on the protected branch.
3. Re-run lint, typecheck, test, build, smoke, and strict evidence validation after the rollback commit.
4. Attach rollback command output and post-rollback smoke evidence to the same GitHub Issue/PR audit trail.
