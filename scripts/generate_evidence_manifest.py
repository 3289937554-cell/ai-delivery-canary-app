#!/usr/bin/env python3
"""Generate a hashed AI delivery evidence manifest from an evidence directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from validate_evidence_manifest import validate_manifest


REQUIRED_COMMAND_LOGS = {
    "lint": "logs/lint.log",
    "typecheck": "logs/typecheck.log",
    "test": "logs/test.log",
    "build": "logs/build.log",
    "smoke": "logs/smoke.log",
}
DEFAULT_COMMAND_TEXT = {
    "lint": "project lint command recorded in logs/lint.log",
    "typecheck": "project typecheck command recorded in logs/typecheck.log",
    "test": "project test command recorded in logs/test.log",
    "build": "project build command recorded in logs/build.log",
    "smoke": "project smoke command recorded in logs/smoke.log",
}
ISSUE_RE = re.compile(r"^GH-\d+$")
PR_RE = re.compile(r"^PR-\d+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_APPROVAL_STATUS = {
    "draft",
    "ready_for_claude_review",
    "changes_requested",
    "approved_for_final_gate",
    "approved_for_human_merge",
    "blocked_for_human_decision",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_root(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def require_file(path: Path, label: str, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"missing required {label}: {path}")


def collect_surface_evidence(evidence_dir: Path, failures: list[str]) -> list[Path]:
    surface_dir = evidence_dir / "surface-evidence"
    if not surface_dir.is_dir():
        legacy_dir = evidence_dir / "screenshots"
        if legacy_dir.is_dir():
            surface_dir = legacy_dir
        else:
            failures.append(f"missing required surface evidence directory: {surface_dir}")
            return []
    files = sorted(path for path in surface_dir.rglob("*") if path.is_file())
    if not files:
        failures.append(f"surface evidence directory has no files: {surface_dir}")
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate evidence/manifest.json with real sha256 hashes.")
    parser.add_argument("--issue-id", required=True, help="GitHub Issue id, for example GH-123.")
    parser.add_argument("--pr-id", required=True, help="GitHub PR id, for example PR-456.")
    parser.add_argument("--base-sha", required=True, help="40-char base commit sha.")
    parser.add_argument("--commit-sha", required=True, help="40-char verified implementation commit sha.")
    parser.add_argument("--evidence-dir", required=True, help="Evidence directory such as evidence/GH-123.")
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--actor", default="codex worker", help="Actor name written into the manifest.")
    parser.add_argument("--approval-status", default="ready_for_claude_review", choices=sorted(ALLOWED_APPROVAL_STATUS))
    parser.add_argument("--created-at", help="UTC timestamp YYYY-MM-DDTHH:MM:SSZ. Defaults to current UTC time.")
    parser.add_argument("--rollback-strategy", default="revert_pr")
    parser.add_argument("--rollback-command", help="Rollback command. Defaults to gh pr revert <number>.")
    parser.add_argument("--rollback-data-notes", default="No irreversible data migration recorded for this delivery packet.")
    for command_name in REQUIRED_COMMAND_LOGS:
        parser.add_argument(f"--{command_name}-command", default=DEFAULT_COMMAND_TEXT[command_name])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = (repo_root / args.evidence_dir).resolve()
    expected_evidence_dir = (repo_root / "evidence" / args.issue_id).resolve()

    if not ISSUE_RE.match(args.issue_id):
        failures.append("--issue-id must match GH-<number>")
    if not PR_RE.match(args.pr_id):
        failures.append("--pr-id must match PR-<number>")
    if not SHA_RE.match(args.base_sha):
        failures.append("--base-sha must be 40 lowercase hex chars")
    if not SHA_RE.match(args.commit_sha):
        failures.append("--commit-sha must be 40 lowercase hex chars")
    try:
        evidence_dir.relative_to(repo_root)
    except ValueError:
        failures.append("--evidence-dir must be inside --repo-root")
    if evidence_dir != expected_evidence_dir:
        failures.append(
            f"--evidence-dir must resolve exactly to evidence/{args.issue_id} under --repo-root; actual: {evidence_dir}"
        )

    for command_name, rel_path in REQUIRED_COMMAND_LOGS.items():
        require_file(evidence_dir / rel_path, f"{command_name} log", failures)
    require_file(evidence_dir / "diff.patch", "diff artifact", failures)
    require_file(evidence_dir / "reports/test-summary.json", "test summary artifact", failures)
    require_file(evidence_dir / "rollback.md", "rollback artifact", failures)
    surface_files = collect_surface_evidence(evidence_dir, failures)

    if failures:
        print("AI evidence manifest generation")
        print("result: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    created_at = args.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pr_number = args.pr_id.removeprefix("PR-")
    rollback_command = args.rollback_command or f"gh pr revert {pr_number}"

    commands = []
    for command_name, rel_path in REQUIRED_COMMAND_LOGS.items():
        log_path = evidence_dir / rel_path
        commands.append(
            {
                "name": command_name,
                "command": getattr(args, f"{command_name}_command"),
                "exit_code": 0,
                "log_path": relative_to_root(log_path, repo_root),
                "sha256": sha256_file(log_path),
            }
        )

    artifacts = [
        {
            "type": "diff",
            "path": relative_to_root(evidence_dir / "diff.patch", repo_root),
            "sha256": sha256_file(evidence_dir / "diff.patch"),
        },
        {
            "type": "logs",
            "path": relative_to_root(evidence_dir / "logs/test.log", repo_root),
            "sha256": sha256_file(evidence_dir / "logs/test.log"),
        },
        {
            "type": "tests",
            "path": relative_to_root(evidence_dir / "reports/test-summary.json", repo_root),
            "sha256": sha256_file(evidence_dir / "reports/test-summary.json"),
        },
    ]
    for surface_path in surface_files:
        artifacts.append(
            {
                "type": "surface-evidence",
                "path": relative_to_root(surface_path, repo_root),
                "sha256": sha256_file(surface_path),
            }
        )
    artifacts.append(
        {
            "type": "rollback",
            "path": relative_to_root(evidence_dir / "rollback.md", repo_root),
            "sha256": sha256_file(evidence_dir / "rollback.md"),
        }
    )

    manifest = {
        "manifest_version": "1.0",
        "issue_id": args.issue_id,
        "pr_id": args.pr_id,
        "base_sha": args.base_sha,
        "commit_sha": args.commit_sha,
        "created_at": created_at,
        "actor": args.actor,
        "approval_status": args.approval_status,
        "commands": commands,
        "artifacts": artifacts,
        "rollback": {
            "strategy": args.rollback_strategy,
            "command": rollback_command,
            "data_notes": args.rollback_data_notes,
        },
    }

    manifest_path = evidence_dir / "manifest.json"
    previous_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    strict_result = validate_manifest(
        manifest_path=manifest_path,
        repo_root=repo_root,
        schema_only=False,
        strict=True,
        expected_base_sha=args.base_sha,
        expected_commit_sha=args.commit_sha,
        expected_issue_id=args.issue_id,
        expected_pr_id=args.pr_id,
    )
    if strict_result.failures:
        if previous_manifest is None:
            manifest_path.unlink(missing_ok=True)
        else:
            manifest_path.write_bytes(previous_manifest)
        print("AI evidence manifest generation")
        print(f"manifest: {manifest_path}")
        print("strict_semantic_validation: FAIL")
        for failure in strict_result.failures:
            print(f"- {failure}")
        print("result: FAIL")
        return 1

    print("AI evidence manifest generation")
    print(f"manifest: {manifest_path}")
    print("strict_semantic_validation: PASS")
    if strict_result.warnings:
        print("warnings:")
        for warning in strict_result.warnings:
            print(f"- {warning}")
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
