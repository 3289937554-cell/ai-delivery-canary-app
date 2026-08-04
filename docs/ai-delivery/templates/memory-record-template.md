# Memory Record Template

用途：记录通过 memory admission 的项目记忆或长期规则。只有被证据支持、可复用、无敏感信息、可撤销的内容可以进入本模板。

```yaml
memory_id: MEM-2026-0001
created_at: 2026-07-10T00:00:00Z
scope: project_memory
owner: repo maintainer
source_issue: GH-123
source_pr: PR-456
evidence:
  - evidence/GH-123/manifest.json
  - evidence/GH-123/logs/test.log
  - evidence/GH-123/context-checkpoint.md
claim: npm run smoke must run after npm run build in this repository because smoke imports build output.
decision: In this repository, keep build before smoke in local verification and CI required checks.
usage_rule: Codex worker and GitHub Actions run lint, typecheck, test, build, smoke in that order unless a later PR changes the application runtime.
validation:
  verified_by: CI validate-evidence and DeepSeek final review
  last_verified_commit: def456
  command: npm run build && npm run smoke
risk_if_wrong: smoke can fail with missing build artifact or pass against stale output.
rollback_or_retire: Remove this record after a PR proves smoke no longer depends on build output and updates CI accordingly.
promotion:
  target_layer: L2 project memory
  promote_to_long_term_rule: false
sensitive_data_review:
  contains_secrets: false
  contains_personal_data: false
```

## 准入检查

- `evidence` 指向真实 artifact。
- `claim` 是可执行规则，不是情绪描述。
- `usage_rule` 能被后续 DeepSeek 或 Codex 使用。
- `rollback_or_retire` 写清撤销条件。
- `sensitive_data_review` 明确不含 secrets、token、私钥、生产连接串和客户隐私。
