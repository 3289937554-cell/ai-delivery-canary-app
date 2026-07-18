# Variant A: Operational Density

schema_version: product-design-variant/v1
issue_id: GH-3
variant_id: variant-a

Information-dense operational direction. This variant keeps the release table, create form, selected release detail, gate rail, risk register, and audit timeline visible at once on wide screens. FLOW-001 benefits because release selection and creation are always adjacent. FLOW-002 and FLOW-003 benefit because gate and risk work remain visible while status changes are made. FLOW-004 is weaker because audit history competes for space with execution controls. The direction is efficient for expert operators but can feel visually heavy at 1024px and below.

Accessibility fit is acceptable if semantic table, keyboard focus, wrapping, and live feedback remain strict. Main risk: density can make validation and conflict messages less prominent during failure recovery.
