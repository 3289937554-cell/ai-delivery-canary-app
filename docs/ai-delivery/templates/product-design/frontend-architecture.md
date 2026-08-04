# Frontend Architecture

schema_version: frontend-architecture/v1
issue_id: GH-123
architecture: feature-slice
server-state: gateway projections, events, and receipts are server-owned
workflow-state: run lifecycle and human-task state are domain-owned
ui-state: selection, drawers, filters, focus, and responsive presentation are local UI state
source-of-truth: typed API contracts, workflow-state-machine.json, DESIGN.md, and screen-state-matrix.json

## Composition Rules

Build the shell, routes, entities, features, workflows, and shared UI primitives as separate boundaries. A page must compose a user task from those boundaries; it must not become a single form component.

## Required Frontend Boundaries

```text
src/app          shell, routes, providers, error boundaries
src/entities     domain types, projections, queries, display models
src/features     one user capability per slice
src/workflows    legal transitions and cross-entity orchestration
src/pages        task-oriented composition only; no domain rules
src/shared       tokens, accessible primitives, tables, drawers, command bars
```

## Route Map

For every route, record its primary user task, entry points, exit paths, required entity projections, and allowed actions. Deep links, refresh, back navigation, empty results, and permission denial must have explicit behavior.

## Screen Contracts

Every screen declares its structural pattern, decision/recovery pattern, entry and exit paths, and the required loading, empty, error, permission-denied, blocked, readonly, stale, and extreme-content states.

## State Ownership

| State | Owner | Read/write rule |
| --- | --- | --- |
| Server data, cache, pagination, events | API/Gateway query layer | Never invented by a page |
| Domain lifecycle and legal transitions | Workflow/domain layer | UI dispatches typed actions only |
| Selection, filters, drawers, focus | Local UI layer | May reset without changing business truth |
| Loading, retry, stale, transport failure | Transport layer | Must map to visible recovery UI |

## Feature Slices

List each feature as `feature -> entity -> workflow -> API -> evidence`. A feature must have one owner directory and one verification command. Cross-feature rules belong in `workflows`, not duplicated in pages.

## Interaction Contracts

For each primary action, specify preconditions, optimistic/pessimistic behavior, idempotency, revision conflict handling, permission failure, retry behavior, success receipt, and undo/cancel semantics where applicable.

## Responsive and Accessibility Contract

Record the layout behavior at every declared viewport, keyboard order, focus restoration, announcements, table overflow strategy, long-content behavior, and reduced-motion behavior. A desktop screenshot alone is not evidence.

## Required Surfaces

Use master-detail, timeline, command-bar, approval-drawer, evidence-summary, and status-summary patterns where the user must scan, decide, recover, and audit work. Every surface must expose loading, empty, error, permission-denied, blocked, readonly, stale, and success behavior.

## Vertical Slice

The first implementation slice must run from a real user task through a typed API, workflow transition, event receipt, and evidence reference before additional modules are generated.
