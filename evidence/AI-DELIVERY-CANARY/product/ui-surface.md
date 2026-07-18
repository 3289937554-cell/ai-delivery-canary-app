# Delivery Operations Console UI Surface

## Runtime

- URL: `http://127.0.0.1:8877/`
- Browser interaction: Codex in-app browser
- Screenshot fallback: standalone Playwright, used only because the in-app screenshot exporter returned incorrect pixel dimensions
- Desktop viewport: 1440 x 1000
- Mobile viewport: 390 x 844

## Verified Surface

- Release list, search, create form, selected release detail, status controls, delivery gates, risks, and audit history rendered with meaningful content.
- Empty and disabled states rendered before a release was selected.
- A release was created as `planned`, moved to `validating`, and completed as `ready`.
- A required gate was created and moved from `pending` to `passed`.
- A blocking high-severity risk was created and moved from `open` to `closed`.
- The audit timeline contained seven ordered events after the workflow.
- Browser console contained no errors or warnings.

## Responsive Evidence

- Desktop screenshot: `evidence/AI-DELIVERY-CANARY/product/acceptance-desktop.png`
- Mobile screenshot: `evidence/AI-DELIVERY-CANARY/product/acceptance-mobile.png`
- Desktop document width: 1425 CSS pixels within a 1440-pixel viewport.
- Mobile document width: 375 CSS pixels within a 390-pixel viewport.
- No rendered element crossed the viewport boundary in either measured layout.

The screenshots are runtime captures of the persisted release state. The separate design-concept images are reference material and are not counted as acceptance evidence.
