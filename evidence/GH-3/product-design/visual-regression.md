# Product Design Visual Regression Evidence

schema_version: product-design-runtime-review/v1
issue_id: GH-3
result: PASS within the retained browser evidence scope

## Inputs

- Selected design variant: `variant-b`, approved in `docs/product-design/GH-3/approvals/concept.json`.
- Final design package: `docs/product-design/GH-3/design-package.json`.
- Desktop acceptance image: `evidence/AI-DELIVERY-CANARY/product/acceptance-desktop.png`, SHA-256 `04dc748ff802ae9cfbfa82456811d16218b845504ea2934855972abd72a7ecde`.
- Mobile acceptance image: `evidence/AI-DELIVERY-CANARY/product/acceptance-mobile.png`, SHA-256 `ca2260a6103f37973de52be00bf9a3462dacfb755a04f871d94a9e953cf16e83`.
- Runtime browser acceptance: `evidence/GH-3/surface-evidence/browser-acceptance.md`.

## Observations

- Desktop and mobile acceptance show the guided execution layout: release rail, selected release detail, delivery gates, risks, and audit history remain in the approved task order.
- The desktop document width was recorded as 1425 CSS pixels inside a 1440 pixel viewport.
- The mobile document width was recorded as 375 CSS pixels inside a 390 pixel viewport.
- No rendered element crossed the viewport boundary in either retained measurement.
- Long operational content is governed by explicit design handoff constraints and implementation tests that require `overflow-x: hidden`, wrap-safe table cells, field errors, and responsive grid behavior.

## Boundaries

This is a retained screenshot and layout-measurement regression record, not an external visual-diff service run. The evidence is sufficient for the GH-3 local canary because the screenshots, design package, browser acceptance record, and implementation tests are all repository-local and hashable.
