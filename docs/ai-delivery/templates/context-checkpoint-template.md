# Context Checkpoint Template

用途：每个 GitHub Issue 在 `evidence/GH-<number>/context-checkpoint.md` 维护一份最新状态，供 DeepSeek、Codex、Archon、Task Master 和总控会话恢复上下文。聊天摘要不得替代本文件。

```yaml
checkpoint_version: 1
issue_id: GH-123
pr_id: PR-456
current_state: S6
state_name: codex_implementation
branch: ai/GH-123-short-feature-name
worktree_path: ../worktrees/GH-123-short-feature-name
base_sha: abc123
commit_sha: def456
allowed_actor: codex_worker
allowed_write_scope: feature_branch
required_inputs:
  - evidence/GH-123/codex-plan.md
  - evidence/GH-123/explorer/tests.md
required_outputs:
  - evidence/GH-123/logs/lint.log
  - evidence/GH-123/logs/typecheck.log
  - evidence/GH-123/logs/test.log
  - evidence/GH-123/logs/build.log
  - evidence/GH-123/logs/smoke.log
  - evidence/GH-123/manifest.json
latest_verification:
  command: python3 scripts/validate_evidence_manifest.py evidence/GH-123/manifest.json --repo-root .
  exit_code: 0
  log_path: evidence/GH-123/logs/validate-evidence.log
open_blockers:
  - id: CR-1-mobile-overlap
    first_seen_state: S8
    rounds_seen: 1
    owner: codex_reviser
next_state_if_pass: S7
next_state_if_fail: S6
memory_candidates:
  - id: MC-001
    claim: smoke command depends on a successful build in this repository
    evidence: evidence/GH-123/logs/smoke.log
    proposed_scope: project_memory
human_actions:
  - action: merge PR after Final Gate
    owner: repo maintainer
    required_at_state: S10
```

## 更新规则

- 每次状态变更后更新 `current_state`、`commit_sha`、`latest_verification` 和 `open_blockers`。
- 每次 Codex reviser 推新 commit 后更新 `commit_sha`，并刷新 manifest。
- 每次 DeepSeek reviewer 或 final 输出结论后，把 review artifact 路径加入 `required_inputs` 或 `required_outputs`。
- 如果 checkpoint 与 GitHub PR head 不一致，以 GitHub PR head 和 evidence manifest 为准，回 S6/S7 修复证据。
