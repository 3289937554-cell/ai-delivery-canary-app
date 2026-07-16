# S2 Task Breakdown Packet

## Tasks
1. Branch and worktree control
   - Use ai/GH-1-managed-status.
   - Verify git status before implementation and before final evidence.

2. Implementation
   - Add managed delivery status behavior in the application code.
   - Keep the change minimal and deterministic.

3. Verification
   - Run bash scripts/lint.sh.
   - Run bash scripts/typecheck.sh.
   - Run python3 -B -m unittest discover -s tests -v.
   - Run bash scripts/build.sh.
   - Run bash scripts/smoke.sh.

4. Evidence
   - Generate diff.patch, manifest.json, run-log.md, rollback.md, test-summary.json, and surface observation.
   - Preserve command logs under evidence/GH-1/logs.

5. Review and final gate
   - Provide Claude reviewer and final packets with structured status.
   - Run aid delivery final-check.
   - Leave merge and deploy as human-only decisions.
