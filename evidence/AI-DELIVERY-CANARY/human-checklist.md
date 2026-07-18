# Human Merge / Deploy Checklist

Status: READY FOR HUMAN DECISION.

- [x] Main branch protection was read from the authenticated GitHub API and requires all six checks.
- [x] Single-maintainer self-review is recorded honestly; no independent approval is claimed.
- [x] Previous evidence head passed lint, typecheck, test, build, smoke, and validate-evidence in run `29638834475`.
- [x] GH-3 strict manifest, rollback instructions, browser acceptance, and four model execution records are present.
- [ ] Confirm the amended final PR head has all required checks successful.
- [ ] A different real GitHub identity is onboarded as collaborator and Code Owner, then reviews the PR diff and residual risks; the PR author cannot self-approve.
- [ ] Auto-merge or the authorized human performs merge only after branch protection is satisfied.
- [ ] Any deployment decision is handled separately; this delivery does not authorize production deployment.
