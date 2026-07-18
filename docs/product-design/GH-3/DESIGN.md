# Product Design Foundation

schema_version: product-design-foundation/v1
issue_id: GH-3
profile: operations
accessibility_standard: WCAG 2.2 AA

The Delivery Operations Console is an operational workspace, not a marketing surface. The first viewport prioritizes work state: connection/token controls, release table, create form, selected release detail, gate rail, risk register, and audit history. Visual density should be compact enough for repeated scan-and-update work while preserving readable labels, clear focus, and explicit status text.

Layout grammar: desktop and tablet use a two-column workspace with the release list/create form on the left and release execution panels on the right. Mobile collapses to a single-column sequence with the same semantic order, keeping create, detail, gate, risk, and audit controls reachable without horizontal scrolling. Fixed-format controls such as badges, tables, cards, and forms use stable dimensions and wrapping so long release titles, risk descriptions, and audit entries do not overlap.

Interaction grammar: forms validate at field level and focus the first invalid field. Status transitions only expose allowed domain moves. Unauthorized, conflict, validation, and offline outcomes use the flash banner and live region without clearing operator context. Token storage is session-scoped and visually subordinate to release work.

Visual language: the existing dark operational palette is accepted for this local console because it provides high contrast and clear severity accents. Cyan is reserved for actionable controls and focus, green for connected/passed/ready, amber for validation and waiver states, and coral for failures or blocking risks. Border radius remains 8px or less. Decorative media and external assets are intentionally absent; repository evidence screenshots are acceptance artifacts, not product assets.

Accessibility rules: preserve semantic table markup for release status, explicit labels for every form control, visible keyboard focus, polite live announcements, no color-only status, reflow at 390px mobile width, and WCAG 2.2 AA-oriented contrast. The UI must remain usable when releases, gate names, risks, and audit entries contain extreme but valid content.
