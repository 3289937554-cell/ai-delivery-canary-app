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
