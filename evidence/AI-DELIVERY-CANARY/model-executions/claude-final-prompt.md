# Claude Final Gate Prompt

You are the final Claude gate for GitHub Issue GH-3 and PR #4, Delivery Operations Console.

Review only the authoritative packet below. Do not call tools. Do not use external knowledge. Decide whether the GH-3 application delivery may proceed to human-controlled merge after all required GitHub checks and Code Owner review are satisfied. This decision must not authorize automatic production deployment, production secrets, billing changes, or bypassing branch protection.

Return Markdown with exactly:

1. `# Claude Final Decision`
2. `approval_status: approved_for_human_merge` or `approval_status: blocked_for_human_decision`
3. `handoff_decision: approved_for_human_merge_after_required_checks` or a blocking route
4. `## Evidence Assessment`
5. `## Remaining Conditions`
6. `## Final Boundary`

Consistency requirements:

- Put the two machine decision lines in backticks exactly as specified above.
- Keep lint, Mypy typecheck, Python unittest (73 tests), build, smoke, and manifest validation as separate facts.
- If you number remaining conditions, every summary count must equal the number of listed conditions.
- Proofread the final response for count, gate-name, and current-state contradictions before returning it.

# Authoritative Packet

## Repository And Frozen Implementation

- Repository: 3289937554-cell/ai-delivery-canary-app
- Issue: GH-3
- PR: https://github.com/3289937554-cell/ai-delivery-canary-app/pull/4
- Branch: ai/GH-3-delivery-operations-console
- Base SHA: 9abade1930293e19b86c08e65c817c439fe84b21
- Frozen implementation SHA: 6bb9497b3e4d19866e7201aca08c20b8d180033a
- Previous remote evidence head: b28fa1b04b6b251af69e02260772dbbb3b145017
- The refreshed evidence-only commit has not yet been created. Control-plane final-check and fresh GitHub CI intentionally run after that clean evidence head exists.

## Product Scope And Boundaries

Delivery Operations Console is a single-operator local browser console for managing releases, delivery gates, risks, lifecycle decisions, and append-only audit history.

Required and verified boundaries:

- Python 3.12 standard-library backend bound only to 127.0.0.1.
- Vanilla HTML, CSS, and JavaScript frontend.
- Atomic local JSON persistence with transaction-journal recovery and append-only audit events.
- Runtime bearer token for mutations; no committed default and no token CLI option.
- 1 MiB body limit, malformed/incomplete JSON rejection, static-file confinement, security headers, and sanitized request logging.
- This is not internet-facing SaaS, an automatic merge/deploy system, or a production secret/billing manager.

## Fresh Deterministic Verification

Codex regenerated evidence against the frozen implementation SHA on 2026-07-18:

- Ruff lint: PASS.
- Strict Mypy typecheck: PASS.
- Python unittest: PASS, 73 tests.
- Build: PASS.
- Real service smoke: PASS.
- Strict manifest validation: PASS with the expected base SHA, implementation SHA, GH-3, and PR-4.
- Model execution validation: PASS for all four real Claude/Codex execution records.

## Readiness-Invariant Defect And Fix

During automated review, Codex found that a release already in `ready` or `released` could be made non-ready by:

- adding a pending required gate;
- resetting a passed required gate to pending;
- adding an open blocking risk;
- reopening an accepted blocking risk.

New regression tests first failed for all four mutations. The implementation now continuously enforces readiness requirements for both statuses, all four mutations are rejected, and the full 73-test suite passes. Optional gates and non-blocking risks remain allowed.

## Fresh Claude Reviewer Evidence

A fresh, tool-less Claude Code CLI review was run against implementation SHA `6bb9497`.

- Provider: Anthropic
- Model: claude-opus-4-7
- Session: ba662d7f-7060-43ff-b8b0-8c4a38c51a4f
- Decision: `approval_status: approved_for_final_gate`
- Findings: No blocking findings.
- Reviewer confirmed implementation completeness, all five deterministic gates, the readiness-invariant fix, desktop/mobile product acceptance, persistence behavior, security controls, and documented residual risks.
- Reviewer explicitly did not claim commercial readiness or authorize production deployment.

## Product Acceptance

The retained browser acceptance evidence covers:

- desktop 1440 x 1000 and mobile 390 x 844 layouts;
- release creation and lifecycle transitions;
- required gate and blocking-risk workflows;
- seven ordered audit events;
- persisted state across restart;
- no horizontal overflow;
- zero browser console warnings or errors.

The persistence suite covers journal recovery, exact-once roll-forward, rollback after partial writes, concurrent writers, malformed state rejection, and preserved audit prefixes.

The operations runbook covers start/stop, health checks, token rotation, data layout, backup/restore procedure, incident recovery, logging, and migration policy. A real backup-and-restore rehearsal is not included and remains an operator condition before production dependency.

## GitHub Governance State

- The previous remote evidence head passed all six required checks: lint, typecheck, test, build, smoke, and validate-evidence.
- Auto-merge is queued, but branch protection correctly keeps the PR blocked until a valid approving Code Owner review exists.
- The PR author, sole collaborator, and sole Code Owner are the same GitHub identity. No independent human review exists and none is claimed.
- GitHub does not permit the PR author to satisfy the required approval by approving their own PR. A valid Code Owner approval therefore requires onboarding a different real human GitHub identity as an authorized collaborator and Code Owner, then obtaining that person's approving review.
- This model decision is evidence for the final gate; it is not a GitHub human approval and cannot satisfy the Code Owner rule.
- Branch protection must not be weakened and admin merge must not be used.

## Commercial Readiness State

The previous evidence head reached governed commercial-canary `GO` after real model source-log provenance was bound. Because the implementation and reviewer evidence have changed, the commercial contract, final-check, readiness result, and readiness packet must be regenerated and checked after the refreshed evidence-only commit. Do not carry the previous GO forward without those fresh checks.

## Final Boundary

You may approve application delivery for human-controlled merge after refreshed evidence, all required CI checks, and valid Code Owner approval. You must not:

- claim that the PR is currently mergeable;
- treat model review as human GitHub approval;
- authorize an admin bypass or weaker branch protection;
- claim production deployment, production secrets, or billing setup;
- claim an unsupervised commercial application factory.

Do not state or imply that the current sole Code Owner can provide the valid approval on their own PR.
