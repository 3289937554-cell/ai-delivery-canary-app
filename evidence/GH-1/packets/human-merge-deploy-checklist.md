# Human Merge and Deploy Checklist

## Before Merge
- Confirm PR-2 targets main and head branch is ai/GH-1-managed-status.
- Confirm GitHub Actions checks are complete, including validate-evidence.
- Confirm aid delivery final-check result is PASS for GH-1 and PR-2.
- Confirm branch governance evidence is present and accepted by project owner.
- Confirm CODEOWNERS review expectation is satisfied.

## Manual-Only Actions
- Merge to main is a human decision.
- Production deployment is a human decision.
- Branch protection or repository ruleset changes are human decisions.
- Secrets and credential changes are human decisions.

## Rollback
Use evidence/GH-1/rollback.md to revert the canary implementation and evidence if the human reviewer rejects the PR.
