You are the Claude planner in a real dual-model commercial delivery audit.

Public repository: 3289937554-cell/ai-delivery-canary-app
GitHub Issue: https://github.com/3289937554-cell/ai-delivery-canary-app/issues/3
Branch: ai/GH-3-delivery-operations-console
Base commit: 9abade1930293e19b86c08e65c817c439fe84b21

Plan a product named Delivery Operations Console for one software operator. It must be a usable responsive browser app, not a CLI demo.

Required product scope:
- Python 3.12 standard-library backend bound only to 127.0.0.1
- vanilla HTML/CSS/JavaScript UI
- releases, delivery gates, risks, append-only audit history
- atomic JSON writes with temporary file plus os.replace
- Bearer authentication for mutations, no committed default token
- 1 MiB body limit, malformed JSON handling
- CSP, X-Content-Type-Options, Referrer-Policy, API no-store
- deterministic lint, typecheck, test, build, smoke and strict evidence validation
- desktop and mobile browser acceptance
- implementation commit followed by one evidence-only commit
- no internet-facing deployment, automatic secrets, billing, destructive migration or automatic merge

Repository paths to use:
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

Output a self-contained Markdown planning artifact with these sections:
1 approval_status and handoff_decision
2 product goal, user and measurable non-goals
3 workflows and UX states
4 domain invariants
5 API methods and status semantics
6 persistence and concurrency
7 security boundaries
8 responsive UI information architecture
9 test and acceptance matrix
10 ordered implementation tasks using the paths above
11 model execution evidence plan for Claude planner/reviewer/final and Codex worker, using schema_version ai-delivery-model-execution/v1 with provider, model, interface, run_id, timestamps, exit_code, prompt/artifact/transcript paths and SHA-256 hashes
12 rollback and operations
13 blockers
14 final decision

Planning may approve implementation only. Do not claim code, tests, GitHub PR, CI or commercial readiness are complete. Avoid the words commonly used for unfinished sample content because the artifact will pass a strict evidence scanner.
