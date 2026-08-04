# Human Approval Checklist

Use this checklist when a request touches protected or irreversible surfaces. DeepSeek and Codex may prepare evidence and recommendations, but approval, merge, deployment, secrets, and production actions remain controlled human actions.

## Metadata

- issue_id:
- pr_id:
- approver:
- approval_date:
- approval_status:

Allowed approval status values:

- `approved_for_human_merge`
- `changes_requested`
- `blocked_for_human_decision`

## Protected Actions

| Action | Owner | Evidence Required | Approved |
|---|---|---|---|
| Merge to protected branch |  | CI green, CODEOWNERS review, manifest validated | [ ] |
| Production deployment |  | Deployment plan, rollback plan, monitoring owner | [ ] |
| Secrets or credentials change |  | Secret name, storage target, rotation plan | [ ] |
| Database migration or irreversible data change |  | Migration diff, backup plan, rollback or forward-fix plan | [ ] |
| Billing or paid resource expansion |  | Cost estimate, quota owner, cancellation path | [ ] |
| Branch protection or CI policy change |  | Settings diff, reviewer approval, restoration path | [ ] |
| Security-sensitive code path |  | Security review, threat notes, regression tests | [ ] |

## Approval Questions

- [ ] Does the Final Gate match the original S0/S1 objective?
- [ ] Are all non-goals still out of scope?
- [ ] Does `manifest.json` point to the verified implementation commit, and is the latest PR head an evidence-only final commit?
- [ ] Did `lint`, `typecheck`, `test`, `build`, `smoke`, and `validate-evidence` pass?
- [ ] Are rollback steps specific enough for a different operator to execute?
- [ ] Are residual risks acceptable for this release?
- [ ] Has the same blocker appeared fewer than three times in the current loop?

## Decision

Choose one:

- [ ] `approved_for_human_merge`
- [ ] `changes_requested`
- [ ] `blocked_for_human_decision`

Decision notes:
