# DeepSeek PR Review Template

本模板用于 S8/S9。DeepSeek reviewer 必须基于真实 PR diff、CI 日志、测试报告、截图、evidence manifest 审查，不接受仅基于 Codex 摘要审查。

```yaml
review_type: deepseek_pr_review
workflow_status: S8_deepseek_review
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
inputs_verified:
  diff: evidence/GH-${ISSUE_NUMBER}/diff.patch
  manifest: evidence/GH-${ISSUE_NUMBER}/manifest.json
  ci_run: ${CI_RUN_URL}
  logs:
    - evidence/GH-${ISSUE_NUMBER}/logs/lint.log
    - evidence/GH-${ISSUE_NUMBER}/logs/typecheck.log
    - evidence/GH-${ISSUE_NUMBER}/logs/build.log
    - evidence/GH-${ISSUE_NUMBER}/logs/smoke.log
  tests:
    - evidence/GH-${ISSUE_NUMBER}/logs/test.log
  surface-evidence:
    - evidence/GH-${ISSUE_NUMBER}/surface-evidence/${SURFACE_EVIDENCE_NAME}.png
acceptance_criteria_checked:
  - criterion: ${ACCEPTANCE_CRITERION}
    evidence: ${DIFF_OR_TEST_OR_SURFACE_EVIDENCE_REFERENCE}
    result: pass
blocking_findings:
  - id: CR-${FINDING_NUMBER}
    severity: high
    file: ${FILE_PATH}
    line: ${LINE_NUMBER}
    problem: ${OBSERVED_PROBLEM}
    required_fix: ${ACTIONABLE_FIX}
    handoff_decision: return_to_implementation
non_blocking_notes:
  - note: ${FOLLOW_UP_NOTE_WITH_OWNER}
    owner: ${OWNER}
decision:
  approval_status: changes_requested
  handoff_decision: return_to_implementation
  required_next_actor: codex_reviser
```

通过时使用：

```yaml
review_type: deepseek_pr_review
workflow_status: S8_deepseek_review
issue_id: GH-${ISSUE_NUMBER}
pr_id: PR-${PR_NUMBER}
base_sha: ${BASE_COMMIT_SHA}
commit_sha: ${HEAD_COMMIT_SHA}
inputs_verified:
  diff: evidence/GH-${ISSUE_NUMBER}/diff.patch
  manifest: evidence/GH-${ISSUE_NUMBER}/manifest.json
  ci_run: ${CI_RUN_URL}
  tests:
    - evidence/GH-${ISSUE_NUMBER}/logs/test.log
  surface-evidence:
    - evidence/GH-${ISSUE_NUMBER}/surface-evidence/${SURFACE_EVIDENCE_NAME}.png
acceptance_criteria_checked:
  - criterion: ${ACCEPTANCE_CRITERION}
    evidence: ${DIFF_OR_TEST_OR_SURFACE_EVIDENCE_REFERENCE}
    result: pass
blocking_findings: []
non_blocking_notes:
  - note: ${FOLLOW_UP_NOTE_WITH_OWNER}
    owner: ${OWNER}
decision:
  approval_status: approved_for_final_gate
  handoff_decision: ready_for_final_gate
  required_next_actor: deepseek_final
```
