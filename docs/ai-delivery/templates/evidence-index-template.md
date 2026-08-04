# Evidence Index Template

每个 PR 必须在仓库内提交一个 machine-readable evidence manifest。CI 和 DeepSeek reviewer 都读取同一个文件，不接受只在聊天里描述验证结果。

## Path

```text
evidence/GH-${ISSUE_NUMBER}/manifest.json
```

## Machine Manifest

以下 JSON 必须与 `docs/ai-delivery/schema/manifest.schema.json` 保持一致；不要把 workflow、branch、review 摘要等扩展字段写入 manifest 顶层。扩展信息放在本文后面的 companion index 或 PR 评论中。

```json
{
  "manifest_version": "1.0",
  "issue_id": "GH-${ISSUE_NUMBER}",
  "pr_id": "PR-${PR_NUMBER}",
  "base_sha": "${BASE_COMMIT_SHA}",
  "commit_sha": "${HEAD_COMMIT_SHA}",
  "created_at": "${ISO_8601_UTC_TIME}",
  "actor": "codex worker",
  "approval_status": "ready_for_deepseek_review",
  "commands": [
    {
      "name": "lint",
      "command": "${LINT_COMMAND}",
      "exit_code": 0,
      "log_path": "evidence/GH-${ISSUE_NUMBER}/logs/lint.log",
      "sha256": "${LINT_LOG_SHA256}"
    },
    {
      "name": "typecheck",
      "command": "${TYPECHECK_COMMAND}",
      "exit_code": 0,
      "log_path": "evidence/GH-${ISSUE_NUMBER}/logs/typecheck.log",
      "sha256": "${TYPECHECK_LOG_SHA256}"
    },
    {
      "name": "test",
      "command": "${TEST_COMMAND}",
      "exit_code": 0,
      "log_path": "evidence/GH-${ISSUE_NUMBER}/logs/test.log",
      "sha256": "${TEST_LOG_SHA256}"
    },
    {
      "name": "build",
      "command": "${BUILD_COMMAND}",
      "exit_code": 0,
      "log_path": "evidence/GH-${ISSUE_NUMBER}/logs/build.log",
      "sha256": "${BUILD_LOG_SHA256}"
    },
    {
      "name": "smoke",
      "command": "${SMOKE_COMMAND}",
      "exit_code": 0,
      "log_path": "evidence/GH-${ISSUE_NUMBER}/logs/smoke.log",
      "sha256": "${SMOKE_LOG_SHA256}"
    }
  ],
  "artifacts": [
    {
      "type": "diff",
      "path": "evidence/GH-${ISSUE_NUMBER}/diff.patch",
      "sha256": "${DIFF_SHA256}"
    },
    {
      "type": "logs",
      "path": "evidence/GH-${ISSUE_NUMBER}/logs/test.log",
      "sha256": "${TEST_LOG_SHA256}"
    },
    {
      "type": "tests",
      "path": "evidence/GH-${ISSUE_NUMBER}/reports/test-summary.json",
      "sha256": "${TEST_SUMMARY_SHA256}"
    },
    {
      "type": "surface-evidence",
      "path": "evidence/GH-${ISSUE_NUMBER}/surface-evidence/desktop.png",
      "sha256": "${SURFACE_EVIDENCE_SHA256}"
    },
    {
      "type": "rollback",
      "path": "evidence/GH-${ISSUE_NUMBER}/rollback.md",
      "sha256": "${ROLLBACK_SHA256}"
    }
  ],
  "rollback": {
    "strategy": "revert_pr",
    "command": "git revert ${MERGE_COMMIT_SHA}",
    "data_notes": "${MIGRATION_BACKOUT_COMMAND_OR_NOT_APPLICABLE}"
  }
}
```

## Companion Evidence Index

以下信息建议写在 `evidence/GH-${ISSUE_NUMBER}/evidence-index.md` 或 PR 评论里，供人类和 DeepSeek 阅读；它们不是 machine manifest 字段。

```yaml
workflow_status: S7_pr_ci
branch: ai/GH-${ISSUE_NUMBER}-${SLUG}
review:
  deepseek_review_packet: docs/reviews/GH-${ISSUE_NUMBER}-deepseek-review.md
  blocking_findings_count: 0
handoff_decision: ready_for_deepseek_review
```

## Minimum CI Checks

- `issue_id` 必须匹配 PR branch 中的 `GH-<number>`。
- `pr_id` 必须匹配当前 PR number。
- `base_sha` 等于 PR base commit。
- `commit_sha` 等于 verified implementation commit；PR head 必须是只包含当前 Issue evidence 的 final commit。
- `created_at` 使用 `YYYY-MM-DDTHH:MM:SSZ` UTC 格式。
- 每个 command 都有 command string、exit code、log path 和 sha256，且 exit code 为 0。
- Required artifact types 必须存在：`diff`、`logs`、`tests`、`surface-evidence`、`rollback`。
- 每个本地 artifact path 必须位于 repo root 内、文件存在且 sha256 匹配；只有 URL artifact 可使用 `sha256: external`。
- `approval_status` 只能是 `draft`、`ready_for_deepseek_review`、`changes_requested`、`approved_for_final_gate`、`approved_for_human_merge`、`blocked_for_human_decision`。
