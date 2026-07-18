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

Run the non-evidence gates from the repository root:

```bash
./scripts/lint.sh
./scripts/typecheck.sh
python3 -m unittest discover -s tests -v
./scripts/build.sh
./scripts/smoke.sh
python3 -m py_compile src/aid_canary_app.py
python3 src/aid_canary_app.py --smoke
```
