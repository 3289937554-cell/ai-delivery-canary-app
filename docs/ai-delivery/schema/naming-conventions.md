# 命名规范

本规范统一 Issue、branch、worktree、证据目录、PR 和状态文件命名，解决多会话、多子代理、多分支并行时的冲突。

## 1. 唯一标识

| 对象 | 格式 | 示例 |
|---|---|---|
| Issue id | `GH-<number>` | `GH-123` |
| PR id | `PR-<number>` | `PR-456` |
| feature branch | `ai/GH-<number>-<slug>` | `ai/GH-123-checkout-flow` |
| worktree | `../worktrees/GH-<number>-<slug>` | `../worktrees/GH-123-checkout-flow` |
| evidence dir | `evidence/GH-<number>/` | `evidence/GH-123/` |
| manifest | `evidence/GH-<number>/manifest.json` | `evidence/GH-123/manifest.json` |
| context checkpoint | `evidence/GH-<number>/context-checkpoint.md` | `evidence/GH-123/context-checkpoint.md` |

## 2. slug 规则

- 只使用小写字母、数字和短横线。
- 从用户可见目标提取，不包含日期和模型名。
- 同一 Issue 的 slug 在 S3 后固定；如必须更名，Issue、PR、worktree、manifest 同步记录。

## 3. branch 与 evidence 绑定

CI 的 `validate-evidence` 从 PR branch 提取 `GH-<number>`，只校验：

```text
evidence/GH-<number>/manifest.json
```

这避免一个 PR 携带其他 Issue 的旧 manifest，也避免扫全仓证据导致误绿或误红。

## 4. 子代理产物

| 子代理 | 只读/写入 | 产物路径 |
|---|---|---|
| structure explorer | 只读 | `evidence/GH-<number>/explorer/structure.md` |
| tests explorer | 只读 | `evidence/GH-<number>/explorer/tests.md` |
| security explorer | 只读 | `evidence/GH-<number>/explorer/security.md` |
| UI explorer | 只读 | `evidence/GH-<number>/explorer/ui.md` |
| performance explorer | 只读 | `evidence/GH-<number>/explorer/performance.md` |
| worker | 写 feature branch | code diff、logs、reports、manifest |
| reviewer-tests | 只读 | PR review note 或 `evidence/GH-<number>/review/tests.md` |
| reviewer-security | 只读 | PR review note 或 `evidence/GH-<number>/review/security.md` |

## 5. 清理规则

- 合并后保留 PR、CI artifact、manifest 和 final delivery packet。
- 本地 worktree 可清理，但清理前记录 `git worktree list` 与 PR URL。
- 被放弃的 Issue 保留 evidence dir，manifest 可停留在 `blocked_for_human_decision`。
