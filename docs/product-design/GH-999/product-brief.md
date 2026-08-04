# Product Brief

schema_version: product-brief/v1
issue_id: GH-999
research_status: complete
business_goal: Help an operator move governed work from intake to an auditable outcome without losing state or approval context.
primary_users: Operator (ROLE-OPERATOR), Product owner (ROLE-OWNER), Auditor (ROLE-AUDITOR)
non_goals: Automatic production merge or deployment, Replacing human approval for high-risk actions
constraints: Local single-operator desktop and responsive web surfaces, Private evidence and raw model output must remain out of model context

## Product depth
- primary_success_task: Monitor a governed run — The operator can see the current checkpoint, next legal action, and latest event receipt.
- business_entities: Project, Run, Human task, Evidence reference
- user_tasks: Monitor a governed run, Resolve a bound human task, Inspect verified evidence
- roles_and_boundaries: Operator (ROLE-OPERATOR), Product owner (ROLE-OWNER), Auditor (ROLE-AUDITOR)
- failure_and_recovery: Show the blocking reason, owner, retry or resume action, and preserve the run revision., Keep the drawer open, identify stale or mismatched evidence, and require refresh instead of accepting a guess., Explain why content is withheld and keep metadata available for audit without exposing restricted bytes.
- frontend_surface: Run center, Run detail, Approval desk, Evidence
- non_functional_requirements: WCAG 2.2 AA, keyboard-first operation, visible focus, announced state changes, and no color-only status., Preserve the active task and next legal action at 1440, 1024, 768, and 390px., Persist structured receipts, revision, actor, decision, evidence hash, and event sequence without raw output., List and detail surfaces remain responsive with 1000 runs and 10,000 events through pagination and incremental reconciliation.

## Research Evidence
Generated from the approved application-blueprint.json. Verify assumptions against repository evidence before implementation.

## Success Measures
- An operator can identify the next legal action from the run detail
- Every approval and evidence reference is revision-bound
- Blocked and waiting states are never presented as success
