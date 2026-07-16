#!/usr/bin/env python3
"""Validate an AI delivery evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_TOP_LEVEL = [
    "manifest_version",
    "issue_id",
    "pr_id",
    "base_sha",
    "commit_sha",
    "created_at",
    "actor",
    "approval_status",
    "commands",
    "artifacts",
    "rollback",
]

REQUIRED_COMMANDS = ["lint", "typecheck", "test", "build", "smoke"]
REQUIRED_ARTIFACT_TYPES = ["diff", "logs", "tests", "surface-evidence", "rollback"]
LEGACY_ARTIFACT_ALIASES = {"screenshots": "surface-evidence"}
ALLOWED_APPROVAL_STATUS = {
    "draft",
    "ready_for_claude_review",
    "changes_requested",
    "approved_for_final_gate",
    "approved_for_human_merge",
    "blocked_for_human_decision",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ISSUE_RE = re.compile(r"^GH-\d+$")
PR_RE = re.compile(r"^PR-\d+$")
UTC_CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass
class ValidationResult:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_created_at(value: object, result: ValidationResult) -> None:
    result.require(isinstance(value, str) and bool(value), "created_at must be non-empty")
    if not isinstance(value, str) or not value:
        return
    result.require(
        UTC_CREATED_AT_RE.match(value) is not None,
        "created_at must use UTC ISO8601 format YYYY-MM-DDTHH:MM:SSZ",
    )
    if UTC_CREATED_AT_RE.match(value) is None:
        return
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        result.failures.append(f"created_at is not a valid UTC timestamp: {exc}")
        return
    result.require(parsed.tzinfo == UTC, "created_at must be UTC")


def validate_local_path(
    path_value: str,
    repo_root: Path,
    schema_only: bool,
    result: ValidationResult,
) -> Path | None:
    raw_path = Path(path_value)
    result.require(not raw_path.is_absolute(), f"local artifact path must be relative to repo root: {path_value}")
    result.require(".." not in raw_path.parts, f"local artifact path must not contain '..': {path_value}")
    resolved = (repo_root / raw_path).resolve()
    result.require(is_relative_to(resolved, repo_root), f"local artifact path escapes repo root: {path_value}")
    if raw_path.is_absolute() or ".." in raw_path.parts or not is_relative_to(resolved, repo_root):
        return None
    if not schema_only:
        result.require(resolved.exists(), f"artifact path does not exist: {path_value}")
        if not resolved.exists():
            return None
    return resolved


def evidence_root_for_manifest(manifest_path: Path, repo_root: Path, issue_id: object) -> Path | None:
    """Return the evidence directory that is allowed to back this manifest."""
    if not isinstance(issue_id, str):
        return None
    try:
        rel = manifest_path.relative_to(repo_root)
    except ValueError:
        return None
    if rel.parts == ("evidence", issue_id, "manifest.json"):
        return repo_root / "evidence" / issue_id
    if rel.parts == ("examples", "evidence", issue_id, "manifest.json"):
        return repo_root / "examples" / "evidence" / issue_id
    return None


def validate_issue_bound_path(
    *,
    path_value: str,
    local_path: Path | None,
    evidence_root: Path | None,
    strict: bool,
    schema_only: bool,
    field_name: str,
    result: ValidationResult,
) -> None:
    """In strict mode, every manifest path must stay inside this issue's evidence dir."""
    if not strict or schema_only:
        return
    if evidence_root is None:
        result.failures.append(
            f"strict mode requires manifest under evidence/<issue_id>/manifest.json before checking {field_name}: {path_value}"
        )
        return
    if local_path is None:
        return
    result.require(
        is_relative_to(local_path, evidence_root.resolve()),
        f"{field_name} must stay under this issue evidence directory {evidence_root.relative_to(evidence_root.parents[1]).as_posix()}: {path_value}",
    )


def validate_sha_field(
    item: dict,
    field_name: str,
    repo_root: Path,
    schema_only: bool,
    strict: bool,
    evidence_root: Path | None,
    result: ValidationResult,
) -> Path | None:
    path_value = item.get(field_name)
    sha_value = item.get("sha256")

    result.require(isinstance(path_value, str) and bool(path_value), f"missing {field_name}")
    result.require(isinstance(sha_value, str) and bool(sha_value), f"missing sha256 for {path_value}")

    if not isinstance(path_value, str) or not isinstance(sha_value, str):
        return None

    if is_url(path_value):
        if strict:
            result.failures.append(
                f"strict mode forbids URL artifact/log paths; mirror external evidence under evidence/<issue_id>/ and use a real sha256: {path_value}"
            )
            return None
        result.require(sha_value == "external", f"url artifact must use sha256 external: {path_value}")
        return None

    result.require(
        sha_value != "external",
        f"local artifact must use a real 64-char sha256, not external: {path_value}",
    )
    result.require(
        SHA256_RE.match(sha_value) is not None,
        f"sha256 for local artifact must be 64 lowercase hex chars: {path_value}",
    )
    local_path = validate_local_path(path_value, repo_root, schema_only, result)
    validate_issue_bound_path(
        path_value=path_value,
        local_path=local_path,
        evidence_root=evidence_root,
        strict=strict,
        schema_only=schema_only,
        field_name=field_name,
        result=result,
    )
    if schema_only or local_path is None or not local_path.exists() or SHA256_RE.match(sha_value) is None:
        return local_path

    actual = sha256_file(local_path)
    result.require(
        sha_value == actual,
        f"sha256 mismatch for {path_value}: expected {sha_value}, actual {actual}",
    )
    return local_path


def read_text_artifact(path: Path, result: ValidationResult, label: str) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        result.failures.append(f"{label} must be UTF-8 text for strict semantic validation: {path}")
    except OSError as exc:
        result.failures.append(f"could not read {label} for strict semantic validation: {path}: {exc}")
    return None


def has_key_value(text: str, key: str, expected: str) -> bool:
    patterns = [
        rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*{re.escape(expected)}\s*$",
        rf'"{re.escape(key)}"\s*:\s*"{re.escape(expected)}"',
    ]
    return any(re.search(pattern, text) is not None for pattern in patterns)


def has_zero_exit_code(text: str) -> bool:
    return (
        re.search(r"(?im)^\s*exit_code\s*[:=]\s*0\s*$", text) is not None
        or re.search(r'"exit_code"\s*:\s*0\b', text) is not None
    )


def validate_strict_command_log(
    *,
    path: Path,
    command_name: str,
    issue_id: str,
    pr_id: str,
    base_sha: str,
    commit_sha: str,
    result: ValidationResult,
) -> None:
    text = read_text_artifact(path, result, f"{command_name} command log")
    if text is None:
        return
    if not text.strip():
        result.failures.append(f"command log must be non-empty for {command_name}: {path}")
        return
    required_values = {
        "issue_id": issue_id,
        "pr_id": pr_id,
        "base_sha": base_sha,
        "commit_sha": commit_sha,
        "actual_head_sha": commit_sha,
        "clean_except_issue_evidence": "true",
        "command_name": command_name,
    }
    for key, expected in required_values.items():
        if not has_key_value(text, key, expected):
            result.failures.append(
                f"command log for {command_name} must contain provenance {key}={expected}: {path}"
            )
    if not has_zero_exit_code(text):
        result.failures.append(f"command log for {command_name} must contain exit_code=0 provenance: {path}")


def run_git_bytes(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=False,
    )


def validate_git_commit_exists(repo_root: Path, sha: str, label: str, result: ValidationResult) -> bool:
    check = run_git_bytes(repo_root, "cat-file", "-e", f"{sha}^{{commit}}")
    if check.returncode != 0:
        stderr = check.stderr.decode("utf-8", errors="replace").strip()
        result.failures.append(f"{label} must exist as a commit in repo_root: {sha}" + (f" ({stderr})" if stderr else ""))
        return False
    return True


def canonical_git_diff(repo_root: Path, base_sha: str, commit_sha: str, result: ValidationResult) -> bytes | None:
    diff = run_git_bytes(
        repo_root,
        "diff",
        "--no-ext-diff",
        "--binary",
        base_sha,
        commit_sha,
        "--",
        ".",
        ":!evidence/**",
    )
    if diff.returncode != 0:
        stderr = diff.stderr.decode("utf-8", errors="replace").strip()
        result.failures.append(f"could not compute canonical implementation diff for strict validation: {stderr}")
        return None
    return diff.stdout


def validate_diff_matches_git_range(
    *,
    path: Path,
    repo_root: Path,
    base_sha: str,
    commit_sha: str,
    result: ValidationResult,
) -> None:
    expected = canonical_git_diff(repo_root, base_sha, commit_sha, result)
    if expected is None:
        return
    try:
        actual = path.read_bytes()
    except OSError as exc:
        result.failures.append(f"could not read diff artifact for canonical comparison: {path}: {exc}")
        return
    if actual != expected:
        result.failures.append(
            "diff artifact must exactly match canonical git diff --no-ext-diff --binary "
            f"{base_sha} {commit_sha} -- . :!evidence/**: {path}"
        )


def numeric_field(payload: dict, names: list[str]) -> int | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def numeric_fields(payload: dict, names: list[str]) -> dict[str, int]:
    values: dict[str, int] = {}
    for name in names:
        value = payload.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            values[name] = value
    return values


def validate_test_summary(path: Path, result: ValidationResult) -> None:
    text = read_text_artifact(path, result, "tests artifact")
    if text is None:
        return
    if not text.strip():
        result.failures.append(f"tests artifact must be non-empty JSON: {path}")
        return
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        result.failures.append(f"tests artifact must be valid JSON: {path}: {exc}")
        return
    if not isinstance(payload, dict):
        result.failures.append(f"tests artifact JSON root must be an object: {path}")
        return

    count_fields = ["failed", "failures", "errors", "passed", "passes", "successes", "tests", "total", "total_tests"]
    for field_name in count_fields:
        if isinstance(payload.get(field_name), bool):
            result.failures.append(f"tests artifact field {field_name} must be an integer, not a boolean: {path}")

    status = payload.get("status")
    failure_counts = numeric_fields(payload, ["failed", "failures", "errors"])
    failed = next(iter(failure_counts.values()), None)
    passed = numeric_field(payload, ["passed", "passes", "successes"])
    total = numeric_field(payload, ["tests", "total", "total_tests"])

    has_explicit_result = status is not None or failed is not None or passed is not None
    if not has_explicit_result:
        result.failures.append(
            f"tests artifact must explicitly report status or passed/failed counts: {path}"
        )
    if isinstance(status, str) and status.strip().lower() not in {"pass", "passed", "success", "successful", "ok"}:
        result.failures.append(f"tests artifact status is not passing: {path}: {status}")
    elif status is not None and not isinstance(status, str):
        result.failures.append(f"tests artifact status must be a string when present: {path}")
    if not failure_counts:
        result.failures.append(f"tests artifact must explicitly report failed/failures/errors count of 0: {path}")
    for field_name, value in failure_counts.items():
        if value != 0:
            result.failures.append(f"tests artifact reports failing tests: {path}: {field_name}={value}")
    executed = total if total is not None else passed
    if executed is None:
        result.failures.append(f"tests artifact must report a non-zero total/tests or passed count: {path}")
    elif executed <= 0:
        result.failures.append(f"tests artifact reports zero executed/passed tests: {path}")


def validate_diff_artifact(path: Path, result: ValidationResult) -> None:
    text = read_text_artifact(path, result, "diff artifact")
    if text is None:
        return
    if not text.strip():
        result.failures.append(f"diff artifact must be non-empty: {path}")
        return
    lines = text.splitlines()
    has_diff_header = any(line.startswith("diff --git ") for line in lines)
    has_hunk = any(line.startswith("@@") for line in lines)
    has_changed_body = any(
        (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
        for line in lines
    )
    if not has_diff_header:
        result.failures.append(f"diff artifact must contain a git diff header: {path}")
    if not has_hunk or not has_changed_body:
        result.failures.append(f"diff artifact must contain at least one hunk with changed lines: {path}")


def validate_rollback_artifact(path: Path, result: ValidationResult) -> None:
    text = read_text_artifact(path, result, "rollback artifact")
    if text is None:
        return
    stripped = text.strip()
    if not stripped:
        result.failures.append(f"rollback artifact must be non-empty: {path}")
        return
    if len(stripped) < 40:
        result.failures.append(f"rollback artifact must include concrete rollback steps, not a stub: {path}")
    if re.search(r"\b(gh\s+pr\s+revert|git\s+revert|rollback|roll\s+back|revert|restore)\b", stripped, re.I) is None:
        result.failures.append(f"rollback artifact must include a rollback/revert command or step: {path}")


SURFACE_PLACEHOLDER_RE = re.compile(
    r"\b(placeholder|lorem ipsum|dummy|fake evidence|replace me|screenshot here|surface evidence placeholder)\b",
    re.I,
)


def validate_surface_evidence_artifact(path: Path, result: ValidationResult) -> None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        result.failures.append(f"could not read surface evidence artifact: {path}: {exc}")
        return
    if len(data) < 20:
        result.failures.append(f"surface evidence artifact is too small to be meaningful: {path}")
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    stripped = text.strip()
    if len(stripped) < 40:
        result.failures.append(f"surface evidence text must describe the observed result: {path}")
    if SURFACE_PLACEHOLDER_RE.search(stripped):
        result.failures.append(f"surface evidence text looks like a stub or placeholder: {path}")


def validate_strict_artifact_file(
    *,
    path: Path,
    artifact_type: str,
    repo_root: Path,
    base_sha: str | None,
    commit_sha: str | None,
    result: ValidationResult,
) -> None:
    if artifact_type == "tests":
        validate_test_summary(path, result)
    elif artifact_type == "diff":
        validate_diff_artifact(path, result)
        if base_sha is not None and commit_sha is not None:
            validate_diff_matches_git_range(
                path=path,
                repo_root=repo_root,
                base_sha=base_sha,
                commit_sha=commit_sha,
                result=result,
            )
    elif artifact_type == "rollback":
        validate_rollback_artifact(path, result)
    elif artifact_type == "surface-evidence":
        validate_surface_evidence_artifact(path, result)
    elif artifact_type == "logs":
        text = read_text_artifact(path, result, "logs artifact")
        if text is not None and not text.strip():
            result.failures.append(f"logs artifact must be non-empty: {path}")


def canonical_artifact_type(value: object, strict: bool, result: ValidationResult) -> str | object:
    if isinstance(value, str) and value in LEGACY_ARTIFACT_ALIASES:
        if strict:
            result.failures.append(
                f"strict mode forbids legacy artifact type '{value}'; use surface-evidence"
            )
            return value
        canonical = LEGACY_ARTIFACT_ALIASES[value]
        result.warn(f"legacy artifact type '{value}' treated as '{canonical}'; migrate manifests to surface-evidence")
        return canonical
    return value


def validate_manifest_path_binding(
    manifest_path: Path,
    repo_root: Path,
    issue_id: object,
    schema_only: bool,
    result: ValidationResult,
) -> None:
    if schema_only or not isinstance(issue_id, str):
        return
    if not is_relative_to(manifest_path, repo_root):
        result.failures.append(f"manifest path escapes repo root: {manifest_path}")
        return
    rel = manifest_path.relative_to(repo_root).as_posix()
    allowed = {
        f"evidence/{issue_id}/manifest.json",
        f"examples/evidence/{issue_id}/manifest.json",
    }
    result.require(
        rel in allowed,
        "manifest path must match evidence/<issue_id>/manifest.json "
        "or examples/evidence/<issue_id>/manifest.json; actual: " + rel,
    )


def validate_manifest(
    manifest_path: Path,
    repo_root: Path,
    schema_only: bool,
    strict: bool,
    expected_base_sha: str | None,
    expected_commit_sha: str | None,
    expected_issue_id: str | None,
    expected_pr_id: str | None,
) -> ValidationResult:
    result = ValidationResult()

    result.require(manifest_path.exists(), f"manifest not found: {manifest_path}")
    if not manifest_path.exists():
        return result

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.failures.append(f"invalid json: {exc}")
        return result

    if not isinstance(manifest, dict):
        result.failures.append("manifest root must be an object")
        return result

    for field_name in REQUIRED_TOP_LEVEL:
        result.require(field_name in manifest, f"missing top-level field: {field_name}")

    result.require(manifest.get("manifest_version") == "1.0", "manifest_version must be 1.0")

    issue_id = manifest.get("issue_id")
    pr_id = manifest.get("pr_id")
    result.require(isinstance(issue_id, str) and ISSUE_RE.match(issue_id) is not None, "issue_id must match GH-<number>")
    result.require(isinstance(pr_id, str) and PR_RE.match(pr_id) is not None, "pr_id must match PR-<number>")
    if expected_issue_id:
        result.require(issue_id == expected_issue_id, "issue_id does not match expected issue id")
    if expected_pr_id:
        result.require(pr_id == expected_pr_id, "pr_id does not match expected PR id")

    result.require(isinstance(manifest.get("actor"), str) and bool(manifest.get("actor")), "actor must be non-empty")
    result.require(manifest.get("approval_status") in ALLOWED_APPROVAL_STATUS, "approval_status is not allowed")
    validate_created_at(manifest.get("created_at"), result)
    validate_manifest_path_binding(manifest_path, repo_root, issue_id, schema_only, result)
    issue_evidence_root = evidence_root_for_manifest(manifest_path, repo_root, issue_id)

    for field_name in ["base_sha", "commit_sha"]:
        value = manifest.get(field_name)
        result.require(
            isinstance(value, str) and SHA_RE.match(value) is not None,
            f"{field_name} must be a 40-char lowercase hex commit sha",
        )

    if expected_base_sha:
        result.require(manifest.get("base_sha") == expected_base_sha, "base_sha does not match expected PR base sha")
    if expected_commit_sha:
        result.require(manifest.get("commit_sha") == expected_commit_sha, "commit_sha does not match expected implementation commit sha")

    base_sha_value = manifest.get("base_sha") if isinstance(manifest.get("base_sha"), str) else None
    commit_sha_value = manifest.get("commit_sha") if isinstance(manifest.get("commit_sha"), str) else None
    if strict and not schema_only and base_sha_value and commit_sha_value:
        base_exists = validate_git_commit_exists(repo_root, base_sha_value, "base_sha", result)
        commit_exists = validate_git_commit_exists(repo_root, commit_sha_value, "commit_sha", result)
        if base_exists and commit_exists:
            merge_base = run_git_bytes(repo_root, "merge-base", "--is-ancestor", base_sha_value, commit_sha_value)
            result.require(
                merge_base.returncode == 0,
                "base_sha must be an ancestor of commit_sha for strict evidence validation",
            )

    commands = manifest.get("commands")
    result.require(isinstance(commands, list) and bool(commands), "commands must be a non-empty list")
    command_names: list[object] = []
    if isinstance(commands, list):
        for index, command in enumerate(commands):
            result.require(isinstance(command, dict), f"commands[{index}] must be an object")
            if not isinstance(command, dict):
                continue
            name = command.get("name")
            command_names.append(name)
            result.require(name in REQUIRED_COMMANDS, f"unknown command name: {name}")
            result.require(isinstance(command.get("command"), str) and bool(command.get("command")), f"command text missing for {name}")
            result.require(command.get("exit_code") == 0, f"command exit_code must be 0 for {name}")
            log_path = validate_sha_field(command, "log_path", repo_root, schema_only, strict, issue_evidence_root, result)
            if (
                strict
                and not schema_only
                and log_path is not None
                and isinstance(name, str)
                and isinstance(issue_id, str)
                and isinstance(pr_id, str)
                and isinstance(manifest.get("base_sha"), str)
                and isinstance(manifest.get("commit_sha"), str)
            ):
                validate_strict_command_log(
                    path=log_path,
                    command_name=name,
                    issue_id=issue_id,
                    pr_id=pr_id,
                    base_sha=manifest["base_sha"],
                    commit_sha=manifest["commit_sha"],
                    result=result,
                )

    for required in REQUIRED_COMMANDS:
        result.require(required in command_names, f"missing command: {required}")

    artifacts = manifest.get("artifacts")
    result.require(isinstance(artifacts, list) and bool(artifacts), "artifacts must be a non-empty list")
    artifact_types: list[object] = []
    if isinstance(artifacts, list):
        for index, artifact in enumerate(artifacts):
            result.require(isinstance(artifact, dict), f"artifacts[{index}] must be an object")
            if not isinstance(artifact, dict):
                continue
            artifact_type = canonical_artifact_type(artifact.get("type"), strict, result)
            artifact_types.append(artifact_type)
            result.require(artifact_type in REQUIRED_ARTIFACT_TYPES, f"unknown artifact type: {artifact.get('type')}")
            artifact_path = validate_sha_field(artifact, "path", repo_root, schema_only, strict, issue_evidence_root, result)
            if (
                strict
                and not schema_only
                and artifact_path is not None
                and isinstance(artifact_type, str)
                and artifact_type in REQUIRED_ARTIFACT_TYPES
            ):
                validate_strict_artifact_file(
                    path=artifact_path,
                    artifact_type=artifact_type,
                    repo_root=repo_root,
                    base_sha=base_sha_value,
                    commit_sha=commit_sha_value,
                    result=result,
                )

    for required in REQUIRED_ARTIFACT_TYPES:
        result.require(required in artifact_types, f"missing artifact type: {required}")

    rollback = manifest.get("rollback")
    result.require(isinstance(rollback, dict), "rollback must be an object")
    if isinstance(rollback, dict):
        for field_name in ["strategy", "command", "data_notes"]:
            result.require(isinstance(rollback.get(field_name), str) and bool(rollback.get(field_name)), f"rollback.{field_name} must be non-empty")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an AI delivery evidence manifest.")
    parser.add_argument("manifest", help="Path to evidence manifest json.")
    parser.add_argument("--repo-root", default=".", help="Repository root for local artifact paths.")
    parser.add_argument("--schema-only", action="store_true", help="Validate structure without checking local file existence or hashes.")
    parser.add_argument("--strict", action="store_true", help="Reject legacy artifact aliases such as screenshots.")
    parser.add_argument("--expected-base-sha", help="Expected PR base commit sha.")
    parser.add_argument("--expected-commit-sha", help="Expected verified implementation commit sha, usually the commit immediately before the evidence-only final commit.")
    parser.add_argument("--expected-issue-id", help="Expected issue id such as GH-123.")
    parser.add_argument("--expected-pr-id", help="Expected PR id such as PR-456.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    repo_root = Path(args.repo_root).resolve()
    result = validate_manifest(
        manifest_path=manifest_path,
        repo_root=repo_root,
        schema_only=args.schema_only,
        strict=args.strict,
        expected_base_sha=args.expected_base_sha,
        expected_commit_sha=args.expected_commit_sha,
        expected_issue_id=args.expected_issue_id,
        expected_pr_id=args.expected_pr_id,
    )

    print("AI evidence manifest validation")
    print(f"manifest: {manifest_path}")
    print(f"repo_root: {repo_root}")
    print(f"strict_mode: {str(args.strict).lower()}")
    print("required_commands_checked: " + ",".join(REQUIRED_COMMANDS))
    print("required_artifacts_checked: " + ",".join(REQUIRED_ARTIFACT_TYPES))

    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- {warning}")

    if result.failures:
        print("result: FAIL")
        for failure in result.failures:
            print(f"- {failure}")
        return 1

    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
