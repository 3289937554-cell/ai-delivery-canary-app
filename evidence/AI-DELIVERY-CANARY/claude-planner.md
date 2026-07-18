# Delivery Operations Console — Implementation Planning Artifact

| Field | Value |
| --- | --- |
| Product | Delivery Operations Console |
| Repository | 3289937554-cell/ai-delivery-canary-app |
| Issue | https://github.com/3289937554-cell/ai-delivery-canary-app/issues/3 |
| Branch | ai/GH-3-delivery-operations-console |
| Base commit | 9abade1930293e19b86c08e65c817c439fe84b21 |
| Planning role | Claude planner |
| Artifact type | Planning only (approves the implementation phase, nothing downstream) |
| Date | 2026-07-16 |

This document is the complete plan for one software operator's browser application. It authorizes the implementation phase and defines the contracts, invariants, security posture, tests, task order, and evidence capture that the Codex worker and the Claude reviewer/final roles will hold the build to. It does not report that any code, test run, pull request, continuous-integration result, or commercial readiness has been achieved; those states belong to later phases.

---

## 1. approval_status and handoff_decision

**approval_status: APPROVED FOR IMPLEMENTATION.** The scope is bounded, the contracts are decidable, and the security posture is enforceable with the Python 3.12 standard library alone. The plan clears the implementation phase to begin on branch `ai/GH-3-delivery-operations-console` from base commit `9abade1930293e19b86c08e65c817c439fe84b21`.

**What this approval does not cover.** No source module has been written, no test has executed, no build or smoke run has produced output, no pull request exists, no continuous-integration pipeline has reported, and no commercial-readiness judgment has been made. Each of those is a downstream gate owned by a later role and is explicitly out of planning scope.

**handoff_decision: HAND OFF TO THE CODEX WORKER.** The Codex worker implements the ordered tasks in section 10 against the exact repository paths listed below, producing one implementation commit followed by one evidence-only commit. The Claude reviewer role then verifies the diff against sections 4–9; the Claude final role renders the closing judgment against section 14. Every model run is recorded under the evidence plan in section 11.

Handoff surface (paths the worker owns):

```
src/delivery_ops/domain.py
src/delivery_ops/store.py
src/delivery_ops/server.py
web/index.html
web/app.js
web/styles.css
tests/test_domain.py
tests/test_store.py
tests/test_server.py
docs/operations-runbook.md
```

---

## 2. product goal, user, and measurable non-goals

**Goal.** Give a single delivery operator one local, responsive browser console to move software releases through delivery gates, track the risks attached to each release, and read an append-only audit history of every state change. The console must be operable end to end in a desktop browser and a mobile browser, backed by a local process that persists state durably and refuses unauthorized mutation.

**User.** One release/delivery operator running the console on their own machine. They open the app in a browser at `http://127.0.0.1:<port>`, hold a bearer token supplied out of band, and use it to record and advance releases. There is one operator identity and one token; there is no account system, no sign-up, and no shared multi-user surface.

**Measurable non-goals** (each is checkable, not aspirational):

1. **No internet-facing surface.** The listening socket binds to `127.0.0.1` only. Acceptance: `0` sockets bound to any non-loopback interface.
2. **No non-standard-library runtime.** Acceptance: `0` third-party imports resolvable in `src/delivery_ops/`; every runtime import is in the Python 3.12 standard library.
3. **No committed secret.** Acceptance: `0` occurrences of a live bearer token in tracked files; the token is read only from the `DELIVERY_OPS_TOKEN` environment variable.
4. **No automatic secret generation.** Acceptance: `0` code paths that self-mint a credential; a missing token disables mutations rather than inventing one.
5. **No account or role system.** Acceptance: `1` bearer identity, `0` user records, `0` role tables.
6. **No billing, metering, or payment surface.** Acceptance: `0` payment or invoicing endpoints and modules.
7. **No destructive migration.** Acceptance: `0` code paths that drop, truncate, or overwrite historical audit records; schema changes are additive and forward-only with a pre-write backup copy.
8. **No automatic merge or deploy.** Acceptance: `0` automated merge or remote-deploy steps triggered by the build; promotion of the branch is a human action.
9. **No unbounded request body.** Acceptance: request bodies above `1 MiB` are rejected with `413` before parsing.

---

## 3. workflows and UX states

### Primary workflows

**W1 — Register a release.** The operator opens the console, enters the bearer token once, and creates a release with a title and version. The server assigns an id and an initial status of `planned`, appends a `release.created` audit event, and the release appears in the list.

**W2 — Attach and evaluate delivery gates.** The operator opens a release and adds the delivery gates it must clear (for instance lint, typecheck, test, build, smoke, security). Each gate starts `pending`. As checks conclude, the operator marks each gate `passed`, `failed`, or `waived`; a waiver requires a written reason. Moving the release into `validating` reflects that evaluation is underway.

**W3 — Record and resolve risks.** The operator records risks against a release, each with a severity and a blocking flag. Open blocking risks hold the release back. The operator advances a risk through `mitigated`, `accepted`, or `closed`; acceptance requires a written reason.

**W4 — Advance and release.** When every required gate is `passed` or `waived` and no blocking risk remains `open` or `mitigated`, the release becomes eligible for `ready`. From `ready` the operator records `released`. If a shipped release must be reverted, the operator records `rolled_back` from `released`.

**W5 — Read the audit history.** The operator reads the append-only history for one release or across all releases, in reverse-chronological order, to see who changed what and when.

### UX states (every view resolves to exactly one)

| State | Trigger | Operator sees |
| --- | --- | --- |
| Loading | A fetch is in flight | A non-blocking progress indication in the affected region |
| Empty | A collection returns zero items | A short prompt describing the first useful action |
| Populated | Data returned | The list or detail content |
| Unauthorized | A mutation returns `401` | A prompt to enter or re-enter the bearer token; the pending change is preserved |
| Validation error | A mutation returns `400` or `409` | An inline message naming the field or the rejected transition |
| Conflict | A transition returns `409` | The current server state plus the reason the transition was refused |
| Confirmed | A mutation returns `200`/`201` | An accessible transient confirmation and the refreshed view |
| Offline/unreachable | The local process is down | A banner stating the console cannot reach the local service, with the restart pointer from the runbook |

---

## 4. domain invariants

These hold in `src/delivery_ops/domain.py` and are enforced independently of transport.

**Identity and time.**
- Every entity id is server-assigned (uuid4 hex) and unique within its collection; client-supplied ids are ignored on create.
- Every timestamp is UTC in RFC 3339 form; `completed_at`-style fields never precede their `created_at`.

**Field validation.**
- A release requires a non-empty `title` (≤ 200 characters) and a non-empty `version` (≤ 80 characters).
- Gate `name` is non-empty (≤ 120 characters); `required` is a boolean.
- Risk `description` is non-empty (≤ 500 characters); `severity` ∈ {`low`, `medium`, `high`, `critical`}; `blocking` is a boolean.
- Unknown fields on any create or update body are rejected rather than silently dropped.

**Release lifecycle** (allowed transitions; anything else is refused):
- `planned → validating`
- `validating → blocked`, `validating → ready`
- `blocked → validating`
- `ready → validating` (regression), `ready → released`
- `released → rolled_back`
- `rolled_back` is terminal.

**Gate lifecycle:**
- `pending → passed | failed | waived`
- `failed → pending | passed | waived`
- `waived → pending`
- `passed → pending` (regression re-open only)
- A `waived` gate carries a non-empty `reason`.

**Risk lifecycle:**
- `open → mitigated | accepted | closed`
- `mitigated → open | accepted | closed`
- `accepted → open | closed`
- `closed → open` (re-open only)
- An `accepted` risk carries a non-empty `reason`.

**Cross-entity eligibility.**
- A release is eligible for `ready` only when every gate with `required = true` is in {`passed`, `waived`} **and** no risk with `blocking = true` is in {`open`, `mitigated`}.
- A release may enter `released` only from `ready`.
- Gates and risks each belong to exactly one release; a gate or risk id is meaningless outside its parent release.

**Audit.**
- The audit history is append-only. Records are only ever added; no code path updates or removes an existing audit record.
- Every accepted mutation emits exactly one audit record capturing actor, action, entity type, entity id, the prior status, the new status, and the UTC time.

---

## 5. API methods and status semantics

Transport is the standard-library HTTP server. All request and response bodies are JSON. Reads are open on loopback; every mutation requires a valid bearer token.

| Method & path | Auth | Success | Refusals |
| --- | --- | --- | --- |
| `GET /api/health` | none | `200` | — |
| `GET /api/releases` | none | `200` | — |
| `POST /api/releases` | bearer | `201` | `400`, `401`, `413`, `415` |
| `GET /api/releases/{id}` | none | `200` | `404` |
| `PATCH /api/releases/{id}` | bearer | `200` | `400`, `401`, `404`, `409`, `413`, `415` |
| `POST /api/releases/{id}/gates` | bearer | `201` | `400`, `401`, `404`, `413`, `415` |
| `PATCH /api/releases/{id}/gates/{gate_id}` | bearer | `200` | `400`, `401`, `404`, `409`, `413`, `415` |
| `POST /api/releases/{id}/risks` | bearer | `201` | `400`, `401`, `404`, `413`, `415` |
| `PATCH /api/releases/{id}/risks/{risk_id}` | bearer | `200` | `400`, `401`, `404`, `409`, `413`, `415` |
| `GET /api/releases/{id}/audit` | none | `200` | `404` |
| `GET /api/audit` | none | `200` | — |

**Status semantics.**
- `200 OK` — read succeeded, or an in-place update applied.
- `201 Created` — a new release, gate, or risk was persisted; the body carries the created entity including its server id.
- `400 Bad Request` — malformed JSON, a failed field validation, or an unknown field. The body is a JSON error envelope `{"error": {"code": "...", "message": "..."}}`.
- `401 Unauthorized` — the `Authorization: Bearer <token>` header is absent or does not match; the comparison uses `hmac.compare_digest`.
- `404 Not Found` — an unknown route or an unknown entity id.
- `405 Method Not Allowed` — a known path with an unsupported method; the response carries an `Allow` header.
- `409 Conflict` — a refused state transition or an eligibility failure (for instance advancing to `ready` with a required gate still `pending`); the body names the reason.
- `413 Payload Too Large` — the request body exceeds `1 MiB`; enforced from `Content-Length` and again while reading.
- `415 Unsupported Media Type` — a mutation without a JSON content type.

Every response — success or refusal — carries the security headers in section 7, and every `/api/*` response additionally carries `Cache-Control: no-store`.

---

## 6. persistence and concurrency

**Layout.** State lives under a data directory chosen by the runbook (default `./data/`). Release records — each with its embedded gates and risks — are held in `state.json` as `{"schema_version": "delivery-ops-state/v1", "releases": [...]}`. The audit history is held in `audit.jsonl`, one JSON record per line.

**Atomic state writes.** `store.py` never writes `state.json` in place. It serializes the full document to a string, writes it to a staging sidecar `state.json.tmp` in the same directory, flushes and `os.fsync`s that file descriptor, then calls `os.replace(state.json.tmp, state.json)`. Because `os.replace` is atomic on a single filesystem, a reader ever sees either the prior complete document or the next complete document, never a partial one. A crash mid-write leaves only the sidecar, which the next start discards.

**Append-only audit.** Each audit record is appended to `audit.jsonl` opened with `O_APPEND`, followed by `os.fsync`. Appends never rewrite prior lines, which gives the append-only guarantee at the storage layer as well as the domain layer. Reads parse the file line by line and return records newest-first.

**Concurrency.** The server runs as a threading HTTP server so the UI stays responsive, and a single module-level `threading.Lock` serializes the read-modify-write cycle for every mutation. Under the lock the store loads current state, applies the domain-validated change, writes the state document atomically, appends the audit record, and releases the lock. Because writes are serialized and each write is atomic, concurrent mutations cannot interleave into a corrupt document. Reads take a consistent snapshot of the last committed document.

**Recovery.** On start the store loads `state.json` if present; a missing file yields an empty release set, and a leftover `state.json.tmp` is removed. A malformed `state.json` halts start with a clear message rather than overwriting the operator's data, so the runbook's restore procedure can run.

---

## 7. security boundaries

**Network boundary.** The server binds `127.0.0.1` and no other address. There is no reverse-proxy assumption and no external listener; the console is reachable only from the operator's machine.

**Authentication.** Every mutation requires `Authorization: Bearer <token>`. The expected value is read once at start from the `DELIVERY_OPS_TOKEN` environment variable and compared with `hmac.compare_digest` to avoid timing leakage. No token value is written to any tracked file, and none is generated by the process; if `DELIVERY_OPS_TOKEN` is unset the server still serves reads but refuses every mutation with `401`, so the console is never silently open to writes.

**Input limits.** Request bodies are capped at `1 MiB`. The cap is checked against `Content-Length` up front and enforced again while reading the stream, so a dishonest length cannot bypass it; an oversize body returns `413`. Bodies that are not valid JSON return `400` through a guarded parse that never lets a decode failure crash the handler.

**Response headers on every response:**
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Cache-Control: no-store` on all `/api/*` responses.

The CSP confines scripts and styles to same-origin files, which is why the UI keeps its JavaScript and CSS in `web/app.js` and `web/styles.css` rather than inline.

**Static serving.** Static assets are served only from the `web/` directory. Requested paths are normalized and any path escaping `web/` (for instance a traversal sequence) is refused with `404`, so the file server cannot read outside its root.

**Secret hygiene.** The token is never logged, never echoed in a response body, and never included in an error message. Logs record method, path, and status, not credentials.

---

## 8. responsive UI information architecture

**Shell.** A semantic HTML document (`web/index.html`) with a header, a main region, and a live region for confirmations. The header shows the product name, a health indicator sourced from `GET /api/health`, and a token control that stores the bearer token in `sessionStorage` for the tab's lifetime so it is not persisted to disk.

**Regions.**
- **Releases list** — releases as cards on narrow screens and as a table on wide screens, each showing title, version, status, gate summary, and open-risk count.
- **Release detail** — the selected release with three panels: delivery gates, risks, and the audit timeline. Each panel exposes the transitions allowed by section 4 for the current state, and disables transitions that eligibility rules forbid.
- **Create-release form** — title and version with inline validation matching the domain limits.
- **Audit view** — the cross-release history newest-first.

**Responsive behavior.**
- Base layout is a single scrolling column for viewports below 640 px, with the token control and primary action reachable without horizontal scrolling.
- At 640 px and above, the list and detail sit side by side in a two-column grid.
- Layout uses CSS grid and flexbox with media-query breakpoints; there are no fixed pixel widths that force horizontal scrolling on a phone.

**State handling.** `web/app.js` owns a small in-memory model, issues `fetch` calls, and renders each region into exactly one of the section 3 states. A `401` routes to the token prompt while preserving the pending action; a `409` re-renders with the server's current state and the refusal reason.

**Accessibility.** Controls are real buttons and labeled inputs; the confirmation region is an ARIA live region; focus moves to the first error on a failed submit; interactive targets meet contrast and hit-size expectations so the console is usable by keyboard and on a touch screen.

---

## 9. test and acceptance matrix

Runtime code is standard-library only; the development toolchain (lint, type check, test runner) is permitted to use dev-only tools that never ship in `src/`.

| Suite | File | Cases it must cover |
| --- | --- | --- |
| Domain | `tests/test_domain.py` | Each allowed release/gate/risk transition succeeds; each disallowed transition is refused; `ready` eligibility passes only with required gates cleared and no blocking risk open or mitigated; field validation rejects empty, over-length, and unknown fields; waiver and acceptance require a reason; ids are unique; timestamps are UTC and ordered. |
| Store | `tests/test_store.py` | An atomic write leaves no `state.json.tmp` behind on success; an interrupted write cannot corrupt `state.json`; audit records only ever grow and prior lines are unchanged; serialized state round-trips exactly; a missing state file yields an empty set; a leftover sidecar is discarded on load; serialized mutations under the lock do not interleave. |
| Server | `tests/test_server.py` | Routing and method handling; `401` without a token and with a wrong token, success with the right token; `400` on malformed JSON and on an unknown field; `413` on a body above 1 MiB; `404` for unknown routes and ids; `405` with an `Allow` header; `409` on a refused transition; the three security headers and `no-store` are present on responses; `GET /api/health` returns `200`. Tests bind an ephemeral loopback port and drive it with `http.client`. |

**Deterministic pipeline** (each step has a fixed command and a pass/refuse result):
- **lint** — style and error linting across `src/`, `tests/`, and static assets; no findings permitted.
- **typecheck** — static type checking of `src/delivery_ops/`; no errors permitted.
- **test** — the three suites above run to a green result.
- **build** — `python -m compileall src` plus an asset manifest that hashes each file in `web/` and confirms `index.html` references `app.js` and `styles.css`.
- **smoke** — start the server on an ephemeral loopback port, confirm `GET /api/health` is `200`, create one release with a valid token and confirm `201`, read it back and confirm `200`, assert the security headers and `no-store`, then stop the server.
- **evidence validation** — the strict validator in section 11 confirms every model-execution record is present, well-formed, references existing files, and matches recomputed hashes.

**Acceptance (human, both form factors).** On a desktop browser and on a mobile browser, the operator: enters the token; creates a release; adds required gates; marks gates `passed`; adds a blocking risk and confirms the release cannot reach `ready`; resolves the risk; advances to `ready` then `released`; records a `rolled_back`; and reads the audit history reflecting each step. Both runs must complete without horizontal scrolling and without a broken state.

---

## 10. ordered implementation tasks

The Codex worker executes these in order, pairing each module with its test suite before moving on.

1. **Domain core — `src/delivery_ops/domain.py`.** Entity shapes for release, gate, risk, and audit record; the enumerations; the transition maps and eligibility rules from section 4; field validators; id and UTC-timestamp helpers. Pure logic with no input/output.
2. **Domain tests — `tests/test_domain.py`.** Cover every clause in section 4 and the corresponding row in section 9.
3. **Store — `src/delivery_ops/store.py`.** The data-directory store: load and recover, atomic `state.json` writes via the staging sidecar and `os.replace`, append-only `audit.jsonl`, the serializing lock, and the read-modify-write mutation path.
4. **Store tests — `tests/test_store.py`.** Atomicity, no partial file on success, append-only growth, round-trip, recovery, and serialized-write behavior.
5. **Server — `src/delivery_ops/server.py`.** The threading HTTP server bound to `127.0.0.1`; the router for the section 5 table; bearer checks with `hmac.compare_digest`; the 1 MiB limit and guarded JSON parse; the security headers and `no-store`; static serving confined to `web/`; and the wiring from transport through domain to store, plus `GET /api/health`.
6. **Server tests — `tests/test_server.py`.** Routing, auth, `400`/`404`/`405`/`409`/`413`/`415`, header presence, and health, driven over an ephemeral loopback port.
7. **UI structure — `web/index.html`.** Semantic shell, the four regions from section 8, no inline script or style so the CSP holds.
8. **UI styling — `web/styles.css`.** The responsive grid/flex layout, the 640 px breakpoint, and the visual treatment of every section 3 state.
9. **UI behavior — `web/app.js`.** The fetch client, `sessionStorage` token handling, the in-memory model, region rendering across all states, and the `401`/`409` handling.
10. **Runbook — `docs/operations-runbook.md`.** Start and stop, environment variables, health check, token rotation, backup and restore, rollback, the 1 MiB tuning note, and the additive-only migration policy.
11. **Pipeline and evidence.** The deterministic lint/typecheck/test/build/smoke commands and the strict evidence validator plus the model-execution records defined in section 11.
12. **Commit sequence.** One implementation commit containing tasks 1–11, then one evidence-only commit containing the captured model-execution records, prompts, artifacts, transcripts, and their hashes. No merge and no deploy follow.

---

## 11. model execution evidence plan

Every model run in this delivery — the Claude planner, the Claude reviewer, the Claude final judge, and the Codex worker — is recorded as one JSON record conforming to `schema_version: ai-delivery-model-execution/v1`. This section defines that schema and where the records live; it does not assert that any of these runs has yet occurred. The records are produced as each role executes and are committed in the evidence-only commit.

**Directory layout (committed in the evidence-only commit):**

```
evidence/
  models/
    claude-planner.json
    claude-reviewer.json
    claude-final.json
    codex-worker.json
  prompts/      # the exact prompt text handed to each role
  artifacts/    # the output each role produced (this plan is the planner artifact)
  transcripts/  # the run transcript for each role
  validate_evidence.py
```

**Record schema `ai-delivery-model-execution/v1`** — every field is required:

| Field | Type | Source / meaning |
| --- | --- | --- |
| `schema_version` | string | Constant `ai-delivery-model-execution/v1` |
| `role` | string | One of `claude-planner`, `claude-reviewer`, `claude-final`, `codex-worker` |
| `provider` | string | The model provider (`anthropic` or `openai`) |
| `model` | string | The exact model identifier used for the run |
| `interface` | string | The invocation surface the run went through |
| `run_id` | string | A uuid4 generated at invocation |
| `started_at` | string | RFC 3339 UTC captured when the run began |
| `completed_at` | string | RFC 3339 UTC captured when the run ended; not earlier than `started_at` |
| `exit_code` | integer | The process exit status (`0` on a clean run) |
| `prompt_path` | string | Repository-relative path to the prompt file |
| `prompt_sha256` | string | 64 hex characters over the prompt file |
| `artifact_path` | string | Repository-relative path to the produced artifact |
| `artifact_sha256` | string | 64 hex characters over the artifact file |
| `transcript_path` | string | Repository-relative path to the transcript |
| `transcript_sha256` | string | 64 hex characters over the transcript file |

**Role assignments** (the interface and model recorded per run at execution time):

| Role | provider | interface | Artifact it records |
| --- | --- | --- | --- |
| `claude-planner` | anthropic | Claude Agent SDK (Cowork) | This planning document |
| `claude-reviewer` | anthropic | Claude Agent SDK | The review of the implementation diff against sections 4–9 |
| `claude-final` | anthropic | Claude Agent SDK | The closing judgment against section 14 |
| `codex-worker` | openai | Codex CLI | The implementation diff across the section 10 paths |

**Hashing and time discipline.** Each `*_sha256` is computed with `sha256sum <path>` (or the standard-library `hashlib.sha256` equivalent) over the committed file bytes. Timestamps come from a UTC clock in RFC 3339 form. `run_id` is a uuid4 minted at invocation.

**Strict validation (`evidence/validate_evidence.py`).** The validator refuses the evidence set unless, for every role: the record exists and parses; `schema_version` equals `ai-delivery-model-execution/v1`; every required field is present and correctly typed; `provider`, `role`, and `interface` are among the permitted values; `completed_at` is not earlier than `started_at`; each referenced `prompt_path`, `artifact_path`, and `transcript_path` exists in the tree; and each recorded hash equals the hash recomputed over the referenced file. Any mismatch or missing field fails the whole set with a non-zero exit code, and this validator is the evidence-validation step of the section 9 pipeline.

---

## 12. rollback and operations

Captured in full in `docs/operations-runbook.md`; the shape is fixed here.

**Run and stop.** Start the server with `DELIVERY_OPS_TOKEN` set in the environment and the data directory reachable; it binds `127.0.0.1:<port>`. Stop it with a normal process signal; because writes are atomic, a stop between requests leaves `state.json` complete.

**Health.** `GET /api/health` returns `200` when the process is serving; the console header surfaces this to the operator.

**Token rotation.** Rotate by restarting the process with a new `DELIVERY_OPS_TOKEN`. No token is stored on disk by the server, so rotation leaves no residue; the operator updates the token in the console's token control.

**Backup and restore.** Because state is a single atomically-written JSON document plus an append-only log, a backup is a copy of the data directory. Restore is putting a known-good data directory back in place before start; a malformed `state.json` halts start rather than overwriting, which preserves the failing file for inspection.

**Rollback semantics.** Operational rollback of a shipped release is the audited, forward-only `released → rolled_back` transition — history is never rewritten to "undo" a release. Rolling back the software delivery itself is reverting the branch's commits through the normal review process; the build performs no automatic merge or deploy, so there is nothing to auto-revert.

**Migration policy.** `state.json` carries `schema_version`. Schema changes are additive and forward-only: a migration reads the old document, writes a new one atomically, and takes a backup copy first. No migration drops or rewrites audit history.

---

## 13. blockers

None block the start of implementation. The following must be resolved by the phases that consume them, and are recorded so they are not lost:

1. **Operator token supply.** The `DELIVERY_OPS_TOKEN` value is provided out of band by the operator; the repository ships none. Until it is set, mutations return `401` by design.
2. **Codex worker interface.** The Codex worker's provider, model identifier, and interface must be captured into `evidence/models/codex-worker.json` at run time per section 11; this plan fixes the schema, not the runtime values.
3. **Development toolchain confirmation.** Lint and type-check tools are dev-only and never enter `src/`; the reviewer confirms the runtime import set stays standard-library only.
4. **Port selection.** The default loopback port is set in the runbook; a conflict on the operator's machine is resolved there, not in code.

---

## 14. final decision

**Decision: APPROVE THE IMPLEMENTATION PHASE AND HAND OFF TO THE CODEX WORKER.** The plan defines a single-operator, loopback-only browser console with a standard-library backend; a decidable release/gate/risk domain with an append-only audit trail; atomic JSON persistence through a staging sidecar and `os.replace`; bearer-gated mutations with no committed and no self-generated token; a 1 MiB body cap with guarded JSON handling; the required CSP, `X-Content-Type-Options`, `Referrer-Policy`, and `no-store` headers; a responsive desktop-and-mobile UI; a deterministic lint/typecheck/test/build/smoke pipeline with strict evidence validation; the exact task order over the named repository paths; and an implementation-commit-then-evidence-commit sequence.

**Scope of this decision.** It authorizes writing the code, tests, UI, runbook, and evidence tooling described above. It does not certify that any of them exist yet, that any test or smoke run has passed, that a pull request or continuous-integration result is present, or that the product is commercially ready. Those judgments belong to the Codex worker's output and to the Claude reviewer and Claude final roles, each recorded under the section 11 evidence plan. No internet-facing deployment, automatic secret, billing surface, destructive migration, or automatic merge is authorized now or by later phases.
