# Claude Reviewer Prompt

You are the independent Claude reviewer for GitHub Issue GH-3, Delivery Operations Console.

Review only the authoritative packet in this prompt. Do not call tools. Do not use external knowledge. Assess whether the local-first browser application implementation and evidence are complete enough to proceed to the final gate. Do not claim commercial readiness or automatic deployment.

Return Markdown with exactly these sections:

1. `# Claude Reviewer Decision`
2. `approval_status: approved_for_final_gate` or `approval_status: changes_requested`
3. `## Findings` ordered by severity, or `No blocking findings.`
4. `## Verification Assessment`
5. `## Residual Risks`
6. `## Handoff Decision`

# Authoritative Packet

## Repository And PR

- Repository: 3289937554-cell/ai-delivery-canary-app
- Issue: GH-3
- PR: https://github.com/3289937554-cell/ai-delivery-canary-app/pull/4
- Branch: ai/GH-3-delivery-operations-console
- Base SHA: 9abade1930293e19b86c08e65c817c439fe84b21
- Implementation SHA: 6bb9497b3e4d19866e7201aca08c20b8d180033a
- PR head before this evidence refresh: b28fa1b04b6b251af69e02260772dbbb3b145017

## Product Scope

Delivery Operations Console is a single-operator local browser console for managing releases, delivery gates, risks, lifecycle decisions, and append-only audit history. It is explicitly loopback-only, not an internet deployment, not multi-user SaaS, and not an automatic merge/deploy system.

Required implementation boundaries:
- Python 3.12 standard-library runtime backend bound only to 127.0.0.1.
- Vanilla HTML, CSS, and JavaScript frontend.
- Releases, gates, risks, and audit history.
- Atomic local JSON persistence and append-only audit log.
- Runtime bearer token for mutations; no committed default token and no token CLI option.
- 1 MiB request body limit, malformed/incomplete JSON handling, and security headers.
- Deterministic lint, typecheck, test, build, smoke, and strict evidence validation.
- Desktop and mobile browser acceptance evidence.

## Changed Paths In Implementation Range

```text
.github/workflows/ai-delivery-ci.yml
.gitignore
README.md
docs/operations-runbook.md
pyproject.toml
requirements-dev.txt
scripts/build.sh
scripts/generate_evidence_manifest.py
scripts/lint.sh
scripts/smoke.sh
scripts/typecheck.sh
scripts/validate_evidence_manifest.py
scripts/validate_model_execution.py
src/aid_canary_app.py
src/delivery_ops/__init__.py
src/delivery_ops/domain.py
src/delivery_ops/server.py
src/delivery_ops/store.py
tests/test_aid_canary_app.py
tests/test_domain.py
tests/test_evidence_manifest_validator.py
tests/test_model_execution_validator.py
tests/test_server.py
tests/test_store.py
tests/test_tooling_contract.py
tests/test_web_contract.py
web/app.js
web/index.html
web/styles.css
```

## Fresh Verification Already Performed By Codex On 2026-07-18

- `python3 -m py_compile src/aid_canary_app.py`: exit 0.
- `python3 -m unittest discover -s tests -v`: exit 0, 73 tests passed.
- `python3 src/aid_canary_app.py --smoke`: exit 0, returned status ok.
- `python3 scripts/validate_evidence_manifest.py evidence/GH-3/manifest.json --repo-root . --strict --expected-base-sha 9abade1930293e19b86c08e65c817c439fe84b21 --expected-commit-sha 6bb9497b3e4d19866e7201aca08c20b8d180033a --expected-issue-id GH-3 --expected-pr-id PR-4`: PASS.
- `python3 scripts/validate_model_execution.py --repo-root . --discover --require-all`: validated 4 records.
- GitHub PR #4 required checks at the previous evidence head `b28fa1b`: lint, typecheck, test, build, smoke, validate-evidence all SUCCESS. Fresh checks will run after the refreshed evidence-only commit is pushed.
- The control-plane final-check is intentionally deferred until the refreshed evidence-only commit is created, because it rejects a dirty worktree and binds the evidence head to the implementation parent.
- The refreshed evidence-only commit and local control-plane final-check occur before pushing the branch. Fresh GitHub CI occurs after the push.
- Real Claude/Codex source logs already exist. Repository-local evidence is staged for the final evidence-only commit, external audit locations are bound by hash, and all source hashes will be rebound after this fresh review and final execution.
- Do not infer or invent git-status output, untracked paths, missing provenance, or process ordering that is not stated in this packet.

## Fresh Readiness-Invariant Fix

Codex found a post-approval domain integrity defect during review: a release already in `ready` or `released` could be made non-ready by adding a pending required gate, resetting a passed required gate to pending, adding an open blocking risk, or reopening an accepted blocking risk. The implementation now validates readiness continuously for both statuses and rejects all four mutations. New regression tests first failed in the expected four cases, then passed after the fix. Optional gates and non-blocking risks remain allowed, preserving the intended operator workflow.

## Product Acceptance Evidence

# Product Acceptance Record

## Result

`PASS` for the local-first Delivery Operations Console acceptance scope.

## Workflow Evidence

1. Loaded the application and observed the `Connected` state with no console errors.
2. Saved a runtime-only bearer token and created `Release 2026.07` version `2026.07.16`.
3. Added the required `Production readiness` gate.
4. Added the blocking high-severity `Rollback rehearsal pending` risk.
5. Moved the release to `validating`, passed the gate, closed the risk, and moved the release to `ready`.
6. Verified the release table reported `1/1 cleared` and `0` open risks.
7. Verified seven audit events were visible for the selected release.
8. Rechecked desktop and mobile layouts with no horizontal overflow.

## Deterministic Gates

- Ruff lint: PASS
- Strict Mypy typecheck: PASS
- Python unittest: PASS, 73 tests
- Build: PASS
- Real service smoke: PASS
- Browser console: PASS, zero warnings or errors

## Evidence Files

- `evidence/AI-DELIVERY-CANARY/product/acceptance-desktop.png`
- `evidence/AI-DELIVERY-CANARY/product/acceptance-mobile.png`
- `evidence/AI-DELIVERY-CANARY/product/ui-surface.md`
- `evidence/AI-DELIVERY-CANARY/product/persistence.md`
- `evidence/AI-DELIVERY-CANARY/product/security-review.md`


## UI Surface Evidence

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


## Persistence Evidence

# Persistence Verification

The application stores state in a caller-selected local directory. Mutations are serialized with a lock, staged through a transaction journal, flushed, and replaced atomically. Audit events are append-only and state validation runs during load and recovery.

Verification covered:

- accepted mutations surviving a process restart;
- interrupted journal recovery;
- exact-once roll-forward for a durable audit event;
- rollback after partial audit append or state replacement failure;
- two store instances serializing competing writes;
- schema rejection for malformed or duplicate state;
- preserved audit prefix across failed writes;
- real browser-created release, gate, risk, and audit data persisted under `/tmp/delivery-ops-qa-019f6b32` during acceptance.

The automated persistence suite passed as part of the 73-test full run.


## Security Boundary Evidence

# Application Boundary Review

## Accepted Controls

- The service factory and CLI reject non-loopback bindings.
- Read endpoints are available locally; all mutations require a runtime bearer token.
- The token is read from `DELIVERY_OPS_TOKEN`, is not accepted as a command-line option, and is not committed.
- Authentication runs before request-body parsing.
- Request bodies are bounded to 1 MiB and malformed, incomplete, or unsupported bodies fail closed.
- Static file resolution remains inside the configured web root.
- Responses apply CSP, `X-Content-Type-Options`, `Referrer-Policy`, and no-store API headers.
- Structured request logs omit authorization values and request bodies.
- Model execution records require successful completion, structured transcript metadata, repository-confined paths, and matching SHA-256 values.
- Test summaries reject boolean values where numeric counts are required.
- GitHub Actions dependencies are pinned to immutable commits.

## Residual Boundaries

- This is a single-operator local application, not an internet-facing or multi-user service.
- Runtime token distribution and host account security remain operator responsibilities.
- Repository evidence proves internal consistency and retained run metadata; it is not a provider-issued cryptographic attestation.
- Backup storage, restore rehearsal, merge approval, and production deployment remain human-controlled operations.

No unresolved blocker remained in the local application acceptance scope after the 73-test, build, smoke, and browser verification run.


## Operations Runbook Excerpt

# Delivery Operations Console Runbook

## Start and stop

1. Choose a local data directory and a loopback port.
2. Start the console without a token when read-only access is acceptable, or set `DELIVERY_OPS_TOKEN` for mutations.

```bash
export DELIVERY_OPS_TOKEN='set-a-strong-local-token'
python3 src/aid_canary_app.py \
  --host 127.0.0.1 \
  --port 8080 \
  --data-dir ./.ai-delivery/runtime/delivery-ops-data
```

3. Open `http://127.0.0.1:8080/`.
4. Stop the server with `Ctrl+C`.

## Health and normal operation

- Health: `GET /api/health` returns `{"status":"ok"}` with the required security headers and `Cache-Control: no-store`.
- Read endpoints stay available on `127.0.0.1` even when no token is configured.
- Mutations require `Authorization: Bearer <token>` and return `401` when the token is missing or wrong.
- Operator flow:
  1. Create a release with a title and version.
  2. Move the release from `planned` to `validating`.
  3. Add delivery gates and risks as the release changes.
  4. Move the release to `ready` only when every required gate is `passed` or `waived` and no blocking risk is `open` or `mitigated`.
  5. Review release-local or cross-release audit history before `released` or `rolled_back`.

## Token rotation

- Token rotation is manual by design. Set a new `DELIVERY_OPS_TOKEN` value and restart the process.
- Existing browser tabs keep the old in-memory session token until the operator updates the Token control.
- After rotation, retrying a mutation with the old token should return `401`; the operator must enter the new token and repeat the change.
- No token value is written to disk by the server, and the browser stores it only in `sessionStorage`.

## Data layout and limits

- The data directory contains `state.json` and `audit.jsonl`. `transaction.json` exists only while a cross-file mutation is being committed or recovered.
- `state.json` must contain exactly `schema_version: "delivery-ops-state/v1"` and `releases`.
- `audit.jsonl` is append-only and stores one immutable audit event per accepted mutation.
- Recovery checks the durable transaction journal against the recorded audit prefix. If the exact event line is durable, recovery writes the candidate state and keeps that single event; otherwise it restores the old state and removes only the interrupted suffix after the unchanged audit prefix.
- Request bodies are capped at 1 MiB. Keep release metadata, gate reasons, and risk notes comfortably below that limit; this cap is not intended to be tuned upward in place during an incident.

## Backup and restore

- Backup:
  1. Stop the process or ensure no operator mutations are in flight.
  2. Copy the full data directory, including both `state.json` and `audit.jsonl`.
  3. Record the backup time and the operator performing it.
- Restore:
  1. Stop the process.
  2. Replace the current data directory with the chosen backup copy.
  3. Start the server and confirm `GET /api/health`, `GET /api/releases`, and `GET /api/audit` return the expected data.
- Future additive migrations must take a pre-write backup of `state.json` before writing a new schema shape.

## Rollback and incident recovery

- Operational rollback means changing release status from `released` to `rolled_back` when the domain rules allow it; this preserves the audit trail.
- Software rollback means restarting the console from an earlier application checkout against the same on-disk data only when that build understands `delivery-ops-state/v1`.
- Incident recovery:
  1. Preserve `state.json`, `audit.jsonl`, and the server log before attempting manual repair.
  2. If `state.json` is malformed, the server exits with a clear error and does not overwrite the file.
  3. Remove only the leftover `state.json.tmp` sidecar when startup reports it; do not hand-edit the primary files unless recovery has been approved.
  4. Restore from backup if the persisted state cannot be validated safely.

## Operational logging

- The service emits one structured stderr JSON record per response containing only `method`, normalized `path`, and `status`.
- Authorization headers, token values, query strings, and request bodies are never included in operational logs.
- Redirect stderr to a local operator-controlled file when retention is required, and protect that file with the same access controls as the data directory.

## Migration policy

- The persistence contract is additive-only migration. Existing keys remain valid, and new fields must be optional for older data readers until the schema version is intentionally advanced.
- Before any future additive-only migration writes a changed `state.json`, take a same-directory backup copy and keep `audit.jsonl` unchanged.
- A malformed `state.json` is a stop condition, not a trigger to rewrite or normalize the file automatically.

## Local verification

## Reviewer Boundary

Approve only the application/evidence handoff if the packet supports it. Record residual risks clearly. Do not state that commercial readiness is GO: separate commercial contract validation still requires raw model source-log provenance.
