# Frontend Architecture

schema_version: frontend-architecture/v1
issue_id: GH-999
architecture: feature-slice
server-state: API/Gateway projections, cache, events, and receipts are server-owned
workflow-state: domain workflows and legal transitions are workflow-owned
ui-state: selection, filters, drawers, focus, and responsive presentation are local UI state
source-of-truth: application-blueprint.json, typed API contracts, workflow-state-machine.json, and screen-state-matrix.json

## Route Map

- `SCREEN-RUN-CENTER`: task=TASK-MONITOR-RUN; entry=primary-navigation, global-search; exit=open-run-detail, open-approval-drawer, open-evidence; action=Create or resume a run
- `SCREEN-RUN-DETAIL`: task=TASK-MONITOR-RUN, TASK-RESOLVE-HUMAN-TASK; entry=run-center, notification; exit=return-to-run-center, open-approval-drawer, open-evidence; action=Inspect the next legal action
- `SCREEN-APPROVAL-DESK`: task=TASK-RESOLVE-HUMAN-TASK; entry=run-detail, approvals-navigation; exit=resolve-task, refresh-stale-task, return-to-run-detail; action=Resolve a revision-bound human task
- `SCREEN-EVIDENCE`: task=TASK-INSPECT-EVIDENCE; entry=evidence-navigation, run-detail, approval-drawer; exit=return-to-run-detail; action=Inspect verified evidence metadata

## State Ownership

Server data/cache/events -> API/Gateway; lifecycle -> workflows; selection/drawers/filters -> UI; loading/retry/stale/transport -> transport state.

## Feature Slices

- `TASK-MONITOR-RUN` -> entities=ENT-PROJECT, ENT-RUN -> workflows=FLOW-GOVERNED-RUN -> API=API-TASK-TASK-MONITOR-RUN -> evidence=event receipt hash, revision-bound decision, verified evidence metadata, no raw output
- `TASK-RESOLVE-HUMAN-TASK` -> entities=ENT-RUN, ENT-HUMAN-TASK, ENT-EVIDENCE -> workflows=FLOW-GOVERNED-RUN, FLOW-HUMAN-DECISION -> API=API-TASK-TASK-RESOLVE-HUMAN-TASK -> evidence=event receipt hash, revision-bound decision, verified evidence metadata, no raw output
- `TASK-INSPECT-EVIDENCE` -> entities=ENT-RUN, ENT-EVIDENCE -> workflows=FLOW-GOVERNED-RUN -> API=API-TASK-TASK-INSPECT-EVIDENCE -> evidence=event receipt hash, revision-bound decision, verified evidence metadata, no raw output

## Required Frontend Boundaries

```text
src/app          shell, routes, providers, error boundaries
src/entities     domain types, projections, queries, display models
src/features     one user capability per slice (approve, assign, import)
src/workflows    legal transitions and cross-entity orchestration
src/pages        task-oriented composition only; no domain rules
src/shared       tokens, accessible primitives, tables, drawers, command bars
```

## Screen Contracts

- `SCREEN-RUN-CENTER`: composition=master-detail, timeline, command-bar, status-summary; states=blocked, default, disabled, empty, error, extreme-content, loading, permission-denied, readonly, stale; entry=primary-navigation, global-search; exit=open-run-detail, open-approval-drawer, open-evidence
- `SCREEN-RUN-DETAIL`: composition=detail-pane, timeline, command-bar, audit-feed; states=blocked, default, disabled, empty, error, extreme-content, loading, permission-denied, readonly, stale; entry=run-center, notification; exit=return-to-run-center, open-approval-drawer, open-evidence
- `SCREEN-APPROVAL-DESK`: composition=detail-pane, approval-drawer, evidence-summary, decision-bar, stale-warning; states=blocked, default, disabled, empty, error, extreme-content, loading, permission-denied, readonly, stale; entry=run-detail, approvals-navigation; exit=resolve-task, refresh-stale-task, return-to-run-detail
- `SCREEN-EVIDENCE`: composition=evidence-table, metadata-panel, redaction-notice, audit-feed; states=blocked, default, disabled, empty, error, extreme-content, loading, permission-denied, readonly, stale; entry=evidence-navigation, run-detail, approval-drawer; exit=return-to-run-detail

## Interaction Contracts

- `TASK-MONITOR-RUN`: precondition=permission granted, current revision; success=The operator can see the current checkpoint, next legal action, and latest event receipt.; recovery=Show the blocking reason, owner, retry or resume action, and preserve the run revision.
- `TASK-RESOLVE-HUMAN-TASK`: precondition=operator has owner role, task revision matches run revision, evidence hash is current; success=The allowed decision is recorded with actor, reason, revision, evidence hash, and receipt hash.; recovery=Keep the drawer open, identify stale or mismatched evidence, and require refresh instead of accepting a guess.
- `TASK-INSPECT-EVIDENCE`: precondition=permission granted, current revision; success=The auditor can confirm an evidence reference without receiving raw secrets, absolute paths, or model output.; recovery=Explain why content is withheld and keep metadata available for audit without exposing restricted bytes.

## Required Surfaces

Pages must compose task-oriented master-detail, timeline, command-bar, drawer, evidence, history, and bulk-action patterns where declared; no page may own domain transitions.

## Responsive and Accessibility Contract

- accessibility: WCAG 2.2 AA, keyboard-first operation, visible focus, announced state changes, and no color-only status.
- responsive: Preserve the active task and next legal action at 1440, 1024, 768, and 390px.
- audit: Persist structured receipts, revision, actor, decision, evidence hash, and event sequence without raw output.
- performance: List and detail surfaces remain responsive with 1000 runs and 10,000 events through pagination and incremental reconciliation.

## Vertical Slice

The first slice is `SLICE-RUN-APPROVAL` and must run from a real user task through typed API, workflow transition, event receipt, and evidence reference.
