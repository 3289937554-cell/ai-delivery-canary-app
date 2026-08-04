# 状态枚举规范

本规范把“流程位置”“审批结论”“交接路由”拆开，避免一个字段同时表达三种含义。

## 1. workflow_status

`workflow_status` 表示 S0-S10 生命周期中的当前位置，只能用于控制面、Issue 评论、Archon adapter 和运行日志。

| 值 | 含义 | 主责 |
|---|---|---|
| S0_goal_boundary | 用户目标与边界确认 | human + DeepSeek planner |
| S1_prd_architecture | PRD、架构草案、验收标准、风险清单 | DeepSeek planner |
| S2_task_breakdown | 任务树、依赖图、GitHub 映射 | Task Master |
| S3_prepare_execution | Issue、branch、worktree、handoff | Archon / Codex |
| S4_codex_plan | Codex 实现计划 | Codex worker |
| S5_read_only_exploration | 子代理只读探索 | Codex explorer |
| S6_implementation_verification | 实现、本地验证、manifest | Codex worker/reviser |
| S7_pr_ci | PR、CI、validate-evidence | GitHub Actions |
| S8_deepseek_review | DeepSeek 基于证据审查 | DeepSeek reviewer |
| S9_review_router | 路由修复或退回设计 | Archon |
| S10_final_gate | 终审、交付包、人工合并建议 | DeepSeek final |

## 2. approval_status

`approval_status` 只表达 evidence manifest 或 Final Gate 审批状态。该字段由机器校验和 DeepSeek review/final 消费。

| 值 | 允许写入者 | 说明 |
|---|---|---|
| draft | Codex worker | 本地证据尚未准备完毕 |
| ready_for_deepseek_review | Codex worker | lint/typecheck/test/build/smoke 与 manifest 已通过本地校验 |
| changes_requested | DeepSeek reviewer | 需要 Codex 修复或补证据 |
| approved_for_final_gate | DeepSeek reviewer | 通过 S8，可进入 S10 |
| approved_for_human_merge | DeepSeek final | 终审通过，仍需人工合并 |
| blocked_for_human_decision | Archon / DeepSeek final / human | 同一阻断重复三轮或遇到高风险动作 |

## 3. handoff_decision

`handoff_decision` 只用于 DeepSeek、Codex、Archon、Task Master 之间的下一步路由，不写入 manifest。

| 值 | 下一步 |
|---|---|
| ready_for_task_breakdown | S2 |
| ready_for_codex_plan | S4 |
| ready_for_implementation | S6 |
| ready_for_pr_ci | S7 |
| ready_for_deepseek_review | S8 |
| return_to_requirements | S1 |
| return_to_task_breakdown | S2 |
| return_to_codex_plan | S4 |
| return_to_implementation | S6 |
| ready_for_final_gate | S10 |
| blocked_for_human_decision | 人工决策 |

## 4. 禁止混用

- 不用 `approval_status` 表示 S0-S10 位置。
- 不把 `ready_for_task_breakdown` 写入 manifest。
- 不把 `changes_requested` 当作 workflow state。
- 不让 Codex 写入 `approved_for_human_merge`。
- 不让 Archon 成为审批真源；Archon 只路由状态，最终证据仍在 GitHub PR、CI 和 manifest。
