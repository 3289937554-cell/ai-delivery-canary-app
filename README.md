# AI Delivery Canary App

Commercial-reference canary implementation of a local Delivery Operations Console for one software operator.

## Start

```bash
export DELIVERY_OPS_TOKEN='set-a-strong-local-token'
python3 src/aid_canary_app.py --host 127.0.0.1 --port 8080
```

The server binds only to `127.0.0.1` and serves the console at `http://127.0.0.1:8080/`.

## Checks

```bash
./scripts/lint.sh
./scripts/typecheck.sh
python3 -m unittest discover -s tests -v
./scripts/build.sh
./scripts/smoke.sh
python3 -m py_compile src/aid_canary_app.py
python3 src/aid_canary_app.py --smoke
```

## Runtime

- Persistent release state lives in the configured data directory as `state.json`.
- Immutable audit events are appended to `audit.jsonl`.
- The browser UI is plain HTML, CSS, and JavaScript served from `web/`.
- Authenticated mutations require `Authorization: Bearer <token>`.
