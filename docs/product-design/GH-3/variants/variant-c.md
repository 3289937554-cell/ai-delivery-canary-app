# Variant C: Adaptive Overview

schema_version: product-design-variant/v1
issue_id: GH-3
variant_id: variant-c

Adaptive overview-and-detail direction. This variant emphasizes a high-level status overview first, then progressively opens release detail, gates, risks, and audit history. FLOW-001 would be approachable for infrequent operators. FLOW-002 and FLOW-003 would need extra disclosure steps before gate and risk actions are visible, increasing the chance that an operator attempts ready without seeing the blocker context. FLOW-004 is strong because audit can be elevated as a separate inspection mode.

The direction is not selected for this canary because the product is a repeated operational tool. It would be reasonable later if the console adds multi-release dashboards, but the current scope needs faster gate/risk execution and lower navigation overhead.
