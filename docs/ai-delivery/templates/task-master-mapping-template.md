# Task Master Mapping

Task Master is a planning and dependency view. GitHub remains the audit source of truth. Every task must map to a GitHub Issue, Issue checklist item, or PR checklist item before it enters S3.

## Metadata

- issue_id:
- pr_id:
- task_master_project:
- owner:
- created_at:
- base_branch:
- feature_branch:

## Mapping Table

| Task ID | Task Name | Dependency | GitHub Anchor | Acceptance Evidence | Risk | State |
|---|---|---|---|---|---|---|
| TM-1 |  | none | GH-123 checklist item 1 | command/log/surface evidence/human review | low | S2 |
| TM-2 |  | TM-1 | GH-123 checklist item 2 | command/log/surface evidence/human review | medium | S2 |

## Gate Rules

- A task without a GitHub anchor cannot enter S3.
- A task without acceptance evidence cannot enter S4.
- A high or critical risk task must name a human approval owner.
- A task that changes production secrets, deployment, billing, protected branches, or irreversible data must stop at `blocked_for_human_decision` until approved.
- Completed Task Master state is not delivery proof; delivery proof is PR diff, CI, manifest, artifacts, DeepSeek review, and Final Gate.

## S2 Exit Checklist

- [ ] All tasks have GitHub anchors.
- [ ] All tasks have dependencies or explicit `none`.
- [ ] All tasks have acceptance evidence.
- [ ] High-risk tasks have human approval owner.
- [ ] The Issue checklist is synchronized with this mapping.
