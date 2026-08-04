# Final Delivery Template

本模板用于 S10。DeepSeek final 只给出终审交付建议，主分支合并、生产部署、secrets 修改和保护分支规则变更仍由人工执行。

```yaml
delivery_type: deepseek_final_gate
workflow_status: S10_final_gate
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
approval_status: approved_for_human_merge
runbook:
  local_run:
    - command: ${INSTALL_COMMAND}
      expected_result: dependencies_ready
    - command: ${START_COMMAND}
      expected_result: service_ready
  verification:
    - command: ${SMOKE_COMMAND}
      expected_result: smoke_passed
evidence:
  manifest: evidence/GH-${ISSUE_NUMBER}/manifest.json
  diff: evidence/GH-${ISSUE_NUMBER}/diff.patch
  logs: evidence/GH-${ISSUE_NUMBER}/logs
  tests: evidence/GH-${ISSUE_NUMBER}/tests
  surface-evidence: evidence/GH-${ISSUE_NUMBER}/surface-evidence
residual_risks:
  - risk: ${RISK_DESCRIPTION}
    owner: ${OWNER}
    decision: accepted_for_this_release
rollback:
  strategy: revert_pr
  command: git revert ${MERGE_COMMIT_SHA}
  data_migration_backout: ${MIGRATION_BACKOUT_COMMAND_OR_NOT_APPLICABLE}
  validation_after_rollback: ${SMOKE_COMMAND}
human_actions:
  - confirm_codeowners_review
  - approve_pr_merge
  - trigger_deployment_after_policy_gate
  - monitor_release_metrics
final_statement: ready_for_human_merge
```
