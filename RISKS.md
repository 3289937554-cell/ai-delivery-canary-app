# 风险清单

| 风险 | 等级 | 控制 |
|---|---|---|
| 误把模拟证据当商业验收 | P0 | commercial-readiness gate 必须要求真实 GitHub URL 与 artifact |
| main 直接实现 | P0 | 使用 ai/GH-<number>-<slug> 分支 |
| 自动 merge/deploy | P0 | 本项目不执行自动合并与部署 |
