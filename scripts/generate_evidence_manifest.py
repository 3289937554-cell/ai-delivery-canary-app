#!/usr/bin/env python3
"""Generate a hashed AI delivery evidence manifest from an evidence directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from validate_evidence_manifest import (
    PRODUCT_DESIGN_ARTIFACT_PATHS,
    project_requires_product_design_evidence,
    validate_manifest,
)

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


def generate_product_design_package_evidence(
    *,
    repo_root: Path,
    evidence_dir: Path,
    issue_id: str,
    failures: list[str],
) -> None:
    control_plane_root = Path(__file__).resolve().parents[1]
    if str(control_plane_root) not in sys.path:
        sys.path.insert(0, str(control_plane_root))
    try:
        from control_api.product_design import assess_product_design
    except ImportError as exc:
        failures.append(f"canonical product design assessor is unavailable: {exc}")
        return

    assessment = assess_product_design(repo_root, issue_id, stage="approval")
    if not assessment.ready:
        failures.append(
            "approved product design package is required before evidence generation: "
            + "; ".join(
                assessment.failures
                + assessment.missing_artifacts
                + assessment.next_actions
            )
        )
        return
    if assessment.selected_variant is None or assessment.profile is None:
        failures.append("approved product design package is missing variant or profile")
        return

    source_paths = {
        "design_package": f"docs/product-design/{issue_id}/design-package.json",
        "functional_approval": f"docs/product-design/{issue_id}/approvals/functional.json",
        "concept_approval": f"docs/product-design/{issue_id}/approvals/concept.json",
        "final_approval": f"docs/product-design/{issue_id}/approvals/final.json",
    }
    for source_path in source_paths.values():
        if not (repo_root / source_path).is_file():
            failures.append(f"product design evidence source is missing: {source_path}")
    if failures:
        return

    lines = [
        "# Product Design Package Evidence",
        "",
        "schema_version: product-design-evidence/v1",
        f"issue_id: {issue_id}",
        "assessment_ready: true",
        f"current_state: {assessment.current_state}",
        f"selected_variant: {assessment.selected_variant}",
        f"profile: {assessment.profile}",
    ]
    for label, source_path in source_paths.items():
        lines.extend(
            [
                f"{label}_path: {source_path}",
                f"{label}_sha256: {sha256_file(repo_root / source_path)}",
            ]
        )
    lines.extend(
        [
            "functional_approval_fresh: true",
            "concept_approval_fresh: true",
            "final_approval_fresh: true",
            "",
        ]
    )
    output = evidence_dir / PRODUCT_DESIGN_ARTIFACT_PATHS["product-design-package"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


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
    product_design_required = project_requires_product_design_evidence(repo_root)
    if product_design_required:
        generate_product_design_package_evidence(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            issue_id=args.issue_id,
            failures=failures,
        )
        require_file(
            evidence_dir / PRODUCT_DESIGN_ARTIFACT_PATHS["accessibility"],
            "accessibility evidence",
            failures,
        )
        require_file(
            evidence_dir / PRODUCT_DESIGN_ARTIFACT_PATHS["visual-regression"],
            "visual regression evidence",
            failures,
        )

    if failures:
        print("AI evidence manifest generation")
        print("result: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    created_at = args.created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    if product_design_required:
        for artifact_type, relative_path in PRODUCT_DESIGN_ARTIFACT_PATHS.items():
            artifact_path = evidence_dir / relative_path
            if artifact_path.is_file():
                artifacts.append(
                    {
                        "type": artifact_type,
                        "path": relative_to_root(artifact_path, repo_root),
                        "sha256": sha256_file(artifact_path),
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
