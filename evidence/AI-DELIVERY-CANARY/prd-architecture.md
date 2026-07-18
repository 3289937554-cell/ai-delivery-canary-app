# S1 PRD and Architecture Decision

Status: PASS.

The product is a local Delivery Operations Console for one release operator. It combines a Python 3.12 standard-library HTTP service, vanilla HTML/CSS/JavaScript UI, crash-consistent journaled JSON persistence, and an append-only audit log.

The service binds only to `127.0.0.1`. Reads are available locally; mutations require a runtime bearer token. Request bodies are capped at 1 MiB, static paths are confined to `web/`, and API responses include restrictive security and caching headers.

The domain owns release, gate, and risk state transitions. The store serializes mutations, writes recoverable journal state, and verifies audit-prefix consistency during recovery. The browser surface supports desktop and mobile release operations without requiring an external framework or database.

Delivery governance remains GitHub-first: Issue #3 defines acceptance, PR #4 carries one implementation commit followed by one evidence-only commit, CI runs six required checks, and merge remains a human or merge-queue action.
