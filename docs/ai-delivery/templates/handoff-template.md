# DeepSeek + Codex Handoff Template

本模板用于每一次从需求到终审的模型交接。所有字段必须落到 GitHub Issue、PR、CI、diff、日志、截图或 evidence manifest 中，避免只凭口头摘要推进。

## 1. DeepSeek To Codex Handoff

```yaml
packet_type: deepseek_to_codex_handoff
workflow_status: S1_prd_architecture
issue_id: GH-${ISSUE_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
target_branch: ai/GH-${ISSUE_NUMBER}-${SLUG}
worktree_path: ../worktrees/GH-${ISSUE_NUMBER}-${SLUG}
source_documents:
  prd: docs/requirements/GH-${ISSUE_NUMBER}-prd.md
  architecture: docs/requirements/GH-${ISSUE_NUMBER}-architecture.md
  acceptance: docs/requirements/GH-${ISSUE_NUMBER}-acceptance.md
  risks: docs/requirements/GH-${ISSUE_NUMBER}-risks.md
scope:
  must_change:
    - ${MODULE_OR_FILE_PATH}
  must_not_change:
    - ${PROTECTED_PATH_OR_BEHAVIOR}
acceptance_criteria:
  - ${MEASURABLE_BEHAVIOR}
required_verification:
  - lint
  - typecheck
  - test
  - build
  - smoke
required_artifacts:
  - diff
  - logs
  - tests
  - surface-evidence
  - rollback
human_approval_required_for:
  - production_deploy
  - github_secrets
  - protected_branch_rules
  - main_branch_merge
  - destructive_data_change
handoff_decision: ready_for_codex_plan
```

## 2. Codex To DeepSeek Review Packet

```yaml
packet_type: codex_to_deepseek_review_packet
workflow_status: S7_pr_ci
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
branch: ai/GH-${ISSUE_NUMBER}-${SLUG}
implementation_summary:
  changed_behavior:
    - ${USER_VISIBLE_CHANGE}
  changed_files:
    - path: ${FILE_PATH}
      reason: ${WHY_CHANGED}
verification:
  lint:
    command: ${LINT_COMMAND}
    exit_code: 0
    log: evidence/GH-${ISSUE_NUMBER}/logs/lint.log
  typecheck:
    command: ${TYPECHECK_COMMAND}
    exit_code: 0
    log: evidence/GH-${ISSUE_NUMBER}/logs/typecheck.log
  test:
    command: ${TEST_COMMAND}
    exit_code: 0
    log: evidence/GH-${ISSUE_NUMBER}/logs/test.log
  build:
    command: ${BUILD_COMMAND}
    exit_code: 0
    log: evidence/GH-${ISSUE_NUMBER}/logs/build.log
  smoke:
    command: ${SMOKE_COMMAND}
    exit_code: 0
    log: evidence/GH-${ISSUE_NUMBER}/logs/smoke.log
evidence_manifest: evidence/GH-${ISSUE_NUMBER}/manifest.json
known_residual_risks:
  - ${RISK_WITH_OWNER_AND_MITIGATION}
approval_status: ready_for_deepseek_review
handoff_decision: ready_for_deepseek_review
```

## 3. DeepSeek Review Result

```yaml
packet_type: deepseek_review_result
workflow_status: S8_deepseek_review
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
review_inputs_checked:
  - diff
  - ci_logs
  - tests
  - surface-evidence
  - evidence_manifest
blocking_findings:
  - id: CR-${FINDING_NUMBER}
    severity: high
    file: ${FILE_PATH}
    line: ${LINE_NUMBER}
    finding: ${OBSERVED_PROBLEM}
    required_fix: ${ACTIONABLE_FIX}
non_blocking_notes:
  - ${FOLLOW_UP_NOTE_WITH_OWNER}
approval_status: changes_requested
handoff_decision: return_to_implementation
```

当没有阻断问题时使用：

```yaml
packet_type: deepseek_review_result
workflow_status: S8_deepseek_review
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
review_inputs_checked:
  - diff
  - ci_logs
  - tests
  - surface-evidence
  - evidence_manifest
blocking_findings: []
non_blocking_notes:
  - ${FOLLOW_UP_NOTE_WITH_OWNER}
approval_status: approved_for_final_gate
handoff_decision: ready_for_final_gate
```

## 4. Revision Request

```yaml
packet_type: revision_request
workflow_status: S9_review_router
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
target_branch: ai/GH-${ISSUE_NUMBER}-${SLUG}
required_fixes:
  - finding_id: CR-${FINDING_NUMBER}
    change_required: ${ACTIONABLE_FIX}
    verification_required:
      - ${COMMAND_NAME}
      - validate-evidence
evidence_to_refresh:
  - diff
  - logs
  - tests
  - surface-evidence
  - rollback
approval_status: changes_requested
handoff_decision: return_to_implementation
```

## 5. Final Gate

```yaml
packet_type: deepseek_final_gate
workflow_status: S10_final_gate
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
release_readiness:
  runbook: docs/runbooks/GH-${ISSUE_NUMBER}.md
  evidence_manifest: evidence/GH-${ISSUE_NUMBER}/manifest.json
  rollback: evidence/GH-${ISSUE_NUMBER}/rollback.md
  residual_risks:
    - ${RISK_WITH_OWNER_AND_DECISION}
human_actions:
  - review_pr
  - approve_merge
  - trigger_deployment_when_policy_allows
approval_status: approved_for_human_merge
```
