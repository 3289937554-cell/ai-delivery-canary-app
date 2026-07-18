# Product Brief

schema_version: product-brief/v1
issue_id: GH-3
research_status: complete
business_goal: Deliver a local-first Delivery Operations Console that lets a single software operator move a release from planning to ready only after required delivery gates are cleared, blocking risks are resolved or accepted, and audit history proves the path.
primary_users: The primary user is an internal release operator who repeatedly scans active releases, records readiness gates, tracks risks, and needs fast recovery from validation or authorization errors while working in a responsive browser console.
non_goals: This delivery excludes internet deployment, multi-user identity, billing, external notification integrations, automatic merge, production secret management, and branch-protection changes.
constraints: The service must bind only to 127.0.0.1, mutations require a runtime bearer token, request bodies are bounded, state is stored locally with an append-only audit log, and UI evidence must remain repository-local and hash-bound.

## Research Evidence

Verified repository evidence:

- `README.md` defines the local runtime and operator start command.
- `src/delivery_ops/domain.py` defines release, gate, risk, and audit state machines.
- `web/index.html`, `web/styles.css`, and `web/app.js` define the browser console surface.
- `evidence/AI-DELIVERY-CANARY/product/ui-surface.md` records desktop and mobile browser acceptance.
- `evidence/AI-DELIVERY-CANARY/product/persistence.md` records local state and audit durability behavior.
- `evidence/AI-DELIVERY-CANARY/product/security-review.md` records loopback, bearer-token, CSP, and bounded-body controls.

Verified facts: the app creates releases, transitions eligible releases, manages gates and risks, persists state across restart, and exposes ordered audit history. Assumptions: a single trained operator owns token handling and host account security.

## Success Measures

Product success means the operator can create a release, add a required gate, add a blocking risk, transition to validating, clear the gate, close or accept the risk, move the release to ready, and inspect seven ordered audit events. Usability success means the table, detail, gates, risks, and audit history remain scannable at 1440, 1280, 1024, 768, and 390 pixel breakpoints without horizontal overflow. Accessibility success means semantic tables/forms, visible focus, live status, keyboard-reachable actions, and WCAG 2.2 AA-oriented contrast and reflow. Operational success means lint, typecheck, tests, build, smoke, strict evidence manifest, and model execution validation all pass.
