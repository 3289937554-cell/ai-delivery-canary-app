# AI Delivery Onboarding Status

installed_at: 2026-07-26T14:14:29Z
project_id: project-0007-ai-delivery-canary-app
control_mode: thin
pack_root: /Users/jiangli/总控库/软件开发/.worktrees/aid-client-v1
target_repo: /Users/jiangli/项目库/worktrees/GH-7-bootstrap
registry_path: /Users/jiangli/总控库/软件开发/.worktrees/aid-client-v1/registry/projects.jsonl
default_owner: @3289937554-cell
platform_owner: @3289937554-cell
security_owner: @3289937554-cell
data_owner: @3289937554-cell

## Local enablement command

```bash
python3 /Users/jiangli/总控库/软件开发/.worktrees/aid-client-v1/scripts/validate_ai_delivery_pack.py --enabled-repo --repo-root /Users/jiangli/项目库/worktrees/GH-7-bootstrap
```

## Control-plane check command

```bash
python3 /Users/jiangli/总控库/软件开发/.worktrees/aid-client-v1/scripts/check_ai_delivery_target_repo.py --target-repo /Users/jiangli/项目库/worktrees/GH-7-bootstrap
python3 /Users/jiangli/总控库/软件开发/.worktrees/aid-client-v1/scripts/check_ai_delivery_registry.py
```

## Bootstrap PR sequence

```bash
cd /Users/jiangli/项目库/worktrees/GH-7-bootstrap
git checkout -b chore/ai-delivery-bootstrap
git add .github .ai-delivery scripts/generate_evidence_manifest.py scripts/validate_evidence_manifest.py docs/ai-delivery evidence/AI-DELIVERY-BOOTSTRAP
git commit -m "chore: enable AI delivery orchestration"
git push -u origin chore/ai-delivery-bootstrap
gh pr create --title "chore: enable AI delivery orchestration" --body "Bootstrap AI Delivery governance, agents, workflows, and evidence validation."
```

## Post-merge gate

- Set protected branch rules for the default branch.
- Require status checks: lint, typecheck, test, build, smoke, validate-evidence.
- Require CODEOWNERS review and conversation resolution.
- Run one low-risk canary Issue through S0-S10 before declaring the target repository fully operational.
