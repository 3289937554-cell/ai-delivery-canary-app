# Rollback

Revert PR-6 after review with `gh pr revert 6 --repo 3289937554-cell/ai-delivery-canary-app`, or revert commit 4cd26b2 with `git revert 4cd26b2`. Re-run the five project checks and the evidence validator after rollback; no data migration is included in this change.
