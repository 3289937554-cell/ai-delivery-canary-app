# 产品设计路由与人工确认记录

schema_version: product-design-decision/v2
issue_id: GH-123
surface_type: web | desktop | mobile | none
rationale: 说明界面适用性、主要用户和运行环境
design_required: true | false
design_root: docs/product-design
accessibility_standard: WCAG 2.2 AA
token_standard: DTCG 2025.10
provider_name: repository | penpot | figma | stitch | other | none
provider_authority: non_authoritative_adapter
private_artifacts_upload: forbidden | allowed
training_opt_out_confirmed: false

## D0-D7 状态

| 状态 | 工件 | 状态 | 负责人 | 阻塞项 |
| --- | --- | --- | --- | --- |
| D0 | product-brief.md | pending | DeepSeek Planner |  |
| D1 | functional-map.json + functional approval | pending | 人工产品负责人 |  |
| D2 | user-flows.md + screen-state-matrix.json | pending | DeepSeek Planner |  |
| D3 | DESIGN.md + DTCG tokens + component catalog | pending | Product Designer |  |
| D4 | three variants + concept approval | pending | Product Designer + 人工产品负责人 |  |
| D5 | four independent reviews | pending | Design Reviewer |  |
| D6 | handoff + licensed asset inventory | pending | Product Designer |  |
| D7 | design package + final approval | pending | 人工产品负责人 |  |

## 哈希确认

functional_artifact_path: docs/product-design/GH-123/functional-map.json
functional_artifact_sha256: <64-char-sha256>
functional_approval_owner: @product-owner

selected_variant_id: variant-b
concept_artifact_path: docs/product-design/GH-123/variants/variant-b.md
concept_artifact_sha256: <64-char-sha256>
concept_approval_owner: @product-owner

design_package_path: docs/product-design/GH-123/design-package.json
design_package_sha256: <64-char-sha256>
final_approval_owner: @product-owner

本模板用于计划与人工核对。正式审批只能由 `aid design approve` 写入对应 approval JSON；不得把本 Markdown 或聊天结论当作批准。
