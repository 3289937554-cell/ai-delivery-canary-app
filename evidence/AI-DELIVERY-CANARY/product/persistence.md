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
