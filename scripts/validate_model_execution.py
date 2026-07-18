#!/usr/bin/env python3
"""Validate repository-bound AI delivery model execution records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "ai-delivery-model-execution/v1"
TRANSCRIPT_SCHEMA_VERSION = "ai-delivery-model-transcript/v1"
ROLE_ASSIGNMENTS = {
    "claude-planner": ("anthropic", "Claude Agent SDK (Cowork)"),
    "claude-reviewer": ("anthropic", "Claude Code CLI"),
    "claude-final": ("anthropic", "Claude Code CLI"),
    "codex-worker": ("openai", "Codex Desktop"),
}
REQUIRED_FIELDS = {
    "schema_version",
    "role",
    "provider",
    "model",
    "interface",
    "run_id",
    "started_at",
    "completed_at",
    "exit_code",
    "placeholder",
    "prompt_path",
    "prompt_sha256",
    "artifact_path",
    "artifact_sha256",
    "transcript_path",
    "transcript_sha256",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RFC3339_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


def discover_record_paths(repo_root: Path) -> list[Path]:
    evidence_root = repo_root.resolve() / "evidence"
    if not evidence_root.is_dir():
        return []
    discovered = set(evidence_root.glob("models/*.json"))
    discovered.update(evidence_root.glob("**/model-executions/*.json"))
    sidecar_suffixes = ("-transcript.json", "-source-audit.json")
    return sorted(path.resolve() for path in discovered if path.is_file() and not path.name.endswith(sidecar_suffixes))


def validate_records(repo_root: Path, record_paths: list[Path], *, require_all_roles: bool) -> list[str]:
    root = repo_root.resolve()
    failures: list[str] = []
    seen_roles: set[str] = set()

    for supplied_path in sorted(record_paths):
        record_path = supplied_path if supplied_path.is_absolute() else root / supplied_path
        record_path = record_path.resolve()
        try:
            record_path.relative_to(root)
        except ValueError:
            failures.append(f"record path escapes repo root: {supplied_path}")
            continue
        try:
            raw = json.loads(record_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            failures.append(f"record path does not exist: {record_path}")
            continue
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"could not parse record {record_path}: {exc}")
            continue
        if not isinstance(raw, dict):
            failures.append(f"record must be a JSON object: {record_path}")
            continue
        record = raw
        missing = sorted(REQUIRED_FIELDS - set(record))
        unknown = sorted(set(record) - REQUIRED_FIELDS)
        if missing:
            failures.append(f"{record_path}: missing fields: {missing}")
        if unknown:
            failures.append(f"{record_path}: unknown fields: {unknown}")
        if missing:
            continue
        _validate_record(root, record_path, record, seen_roles, failures)

    if require_all_roles:
        missing_roles = sorted(set(ROLE_ASSIGNMENTS) - seen_roles)
        if missing_roles:
            failures.append(f"missing roles: {missing_roles}")
    return failures


def _validate_record(
    repo_root: Path,
    record_path: Path,
    record: dict[str, Any],
    seen_roles: set[str],
    failures: list[str],
) -> None:
    if record["schema_version"] != SCHEMA_VERSION:
        failures.append(f"{record_path}: schema_version must be {SCHEMA_VERSION}")
    if record["placeholder"] is not False:
        failures.append(f"{record_path}: placeholder must be false")

    role = record["role"]
    if not isinstance(role, str) or role not in ROLE_ASSIGNMENTS:
        failures.append(f"{record_path}: role is not permitted: {role!r}")
    else:
        if role in seen_roles:
            failures.append(f"{record_path}: duplicate role: {role}")
        seen_roles.add(role)
        expected_provider, expected_interface = ROLE_ASSIGNMENTS[role]
        if record["provider"] != expected_provider:
            failures.append(f"{record_path}: provider for {role} must be {expected_provider}")
        if record["interface"] != expected_interface:
            failures.append(f"{record_path}: interface for {role} must be {expected_interface}")

    for field_name in ("provider", "model", "interface"):
        value = record[field_name]
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{record_path}: {field_name} must be a non-empty string")

    _validate_run_id(record_path, role, record["run_id"], failures)
    started_at = _parse_timestamp(record_path, "started_at", record["started_at"], failures)
    completed_at = _parse_timestamp(record_path, "completed_at", record["completed_at"], failures)
    if started_at is not None and completed_at is not None and completed_at < started_at:
        failures.append(f"{record_path}: completed_at must not be earlier than started_at")

    exit_code = record["exit_code"]
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        failures.append(f"{record_path}: exit_code must be an integer")
    elif exit_code != 0:
        failures.append(f"{record_path}: exit_code must be zero for a successful execution")

    resolved_artifacts: dict[str, Path] = {}
    for prefix in ("prompt", "artifact", "transcript"):
        resolved = _validate_artifact(repo_root, record_path, record, prefix, failures)
        if resolved is not None:
            resolved_artifacts[prefix] = resolved
    transcript_path = resolved_artifacts.get("transcript")
    if transcript_path is not None:
        _validate_transcript(record_path, record, transcript_path, failures)


def _validate_run_id(record_path: Path, role: Any, value: Any, failures: list[str]) -> None:
    if not isinstance(value, str):
        failures.append(f"{record_path}: run_id must be a provider-issued identifier")
        return
    uuid_value = value.removeprefix("local_") if isinstance(role, str) and role.startswith("claude-") else value
    try:
        parsed = uuid.UUID(uuid_value)
    except ValueError:
        failures.append(f"{record_path}: run_id must be a provider-issued identifier")
        return
    if isinstance(role, str) and role.startswith("claude-"):
        if not value.startswith("local_") or parsed.version != 4 or f"local_{parsed}" != value.lower():
            failures.append(f"{record_path}: Claude Cowork run_id must be local_<canonical UUID4>")
    elif role == "codex-worker" and (parsed.version != 7 or str(parsed) != value.lower()):
        failures.append(f"{record_path}: Codex run_id must be a canonical UUID7 thread id")


def _parse_timestamp(record_path: Path, field_name: str, value: Any, failures: list[str]) -> datetime | None:
    if not isinstance(value, str) or RFC3339_UTC_PATTERN.fullmatch(value) is None:
        failures.append(f"{record_path}: {field_name} must be RFC3339 UTC")
        return None
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        failures.append(f"{record_path}: {field_name} must be RFC3339 UTC")
        return None
    if parsed.tzinfo != UTC:
        failures.append(f"{record_path}: {field_name} must be RFC3339 UTC")
        return None
    return parsed


def _validate_artifact(
    repo_root: Path,
    record_path: Path,
    record: dict[str, Any],
    prefix: str,
    failures: list[str],
) -> Path | None:
    path_field = f"{prefix}_path"
    hash_field = f"{prefix}_sha256"
    path_value = record[path_field]
    hash_value = record[hash_field]
    if not isinstance(path_value, str) or not path_value:
        failures.append(f"{record_path}: {path_field} must be a non-empty repo-relative path")
        return None
    pure_path = PurePosixPath(path_value)
    if pure_path.is_absolute() or ".." in pure_path.parts or "\\" in path_value:
        failures.append(f"{record_path}: {path_field} escapes repo root: {path_value}")
        return None
    resolved = (repo_root / Path(*pure_path.parts)).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        failures.append(f"{record_path}: {path_field} escapes repo root: {path_value}")
        return None
    if not resolved.is_file():
        failures.append(f"{record_path}: {path_field} does not exist: {path_value}")
        return None
    if not isinstance(hash_value, str) or not SHA256_PATTERN.fullmatch(hash_value):
        failures.append(f"{record_path}: {hash_field} must be 64 lowercase hex characters")
        return None
    actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if actual_hash != hash_value:
        failures.append(f"{record_path}: {hash_field} mismatch for {path_value}: expected {hash_value}, actual {actual_hash}")
        return None
    return resolved


def _validate_transcript(
    record_path: Path,
    record: dict[str, Any],
    transcript_path: Path,
    failures: list[str],
) -> None:
    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{record_path}: transcript must be valid structured JSON: {exc}")
        return
    if not isinstance(transcript, dict):
        failures.append(f"{record_path}: transcript must be valid structured JSON object")
        return

    required = {
        "schema_version",
        "role",
        "provider",
        "model",
        "interface",
        "run_id",
        "started_at",
        "completed_at",
        "exit_code",
        "source_audit_event_count",
        "source_audit_sha256",
        "source_audit_retained_locally",
    }
    missing = sorted(required - set(transcript))
    if missing:
        failures.append(f"{record_path}: transcript missing execution fields: {missing}")
        return
    if transcript["schema_version"] != TRANSCRIPT_SCHEMA_VERSION:
        failures.append(f"{record_path}: transcript schema_version must be {TRANSCRIPT_SCHEMA_VERSION}")

    for field_name in (
        "role",
        "provider",
        "model",
        "interface",
        "run_id",
        "started_at",
        "completed_at",
        "exit_code",
    ):
        if transcript[field_name] != record[field_name]:
            failures.append(f"{record_path}: transcript {field_name} must match execution record")

    event_count = transcript["source_audit_event_count"]
    if not isinstance(event_count, int) or isinstance(event_count, bool) or event_count <= 0:
        failures.append(f"{record_path}: transcript source_audit_event_count must be a positive integer")
    source_hash = transcript["source_audit_sha256"]
    if not isinstance(source_hash, str) or SHA256_PATTERN.fullmatch(source_hash) is None:
        failures.append(f"{record_path}: transcript source_audit_sha256 must be 64 lowercase hex characters")
    if transcript["source_audit_retained_locally"] is not True:
        failures.append(f"{record_path}: transcript source audit must be retained locally")

    role = record["role"]
    if isinstance(role, str) and role.startswith("claude-"):
        session_id = transcript.get("sdk_session_id")
        try:
            uuid.UUID(session_id) if isinstance(session_id, str) else None
        except ValueError:
            session_id = None
        if not isinstance(session_id, str):
            failures.append(f"{record_path}: Claude transcript must include a canonical sdk_session_id")
    elif role == "codex-worker" and transcript.get("thread_id") != record["run_id"]:
        failures.append(f"{record_path}: Codex transcript thread_id must match run_id")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI delivery model execution records")
    parser.add_argument("records", nargs="*", type=Path, help="record paths relative to the repository root")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--discover", action="store_true", help="discover model records under evidence")
    parser.add_argument("--require-all", action="store_true", help="require all four delivery roles")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    record_paths = list(args.records)
    if args.discover:
        record_paths.extend(discover_record_paths(repo_root))
    unique_paths = sorted(set(record_paths))
    failures = validate_records(repo_root, unique_paths, require_all_roles=args.require_all)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"validated_model_execution_records={len(unique_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
