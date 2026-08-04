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
    "deepseek-planner": ("deepseek", "deepseek-anthropic-api"),
    "deepseek-reviewer": ("deepseek", "deepseek-anthropic-api"),
    "deepseek-final": ("deepseek", "deepseek-anthropic-api"),
    "codex-worker": ("openai", "Codex Desktop"),
}
LEGACY_ROLE_ASSIGNMENTS = {
    "claude-planner": ("anthropic", "Claude Agent SDK (Cowork)"),
    "claude-reviewer": ("anthropic", "Claude Code CLI"),
    "claude-final": ("anthropic", "Claude Code CLI"),
}
ACCEPTED_ROLE_ASSIGNMENTS = {**LEGACY_ROLE_ASSIGNMENTS, **ROLE_ASSIGNMENTS}
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
DEEPSEEK_REQUIRED_FIELDS = (REQUIRED_FIELDS - {"prompt_path"}) | {"source_log_path", "source_log_sha256"}
DEEPSEEK_OPTIONAL_FIELDS = {"prompt_path"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RFC3339_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
DEEPSEEK_RUN_ID_PATTERN = re.compile(r"^deepseek-(?:s1|s8|s10)-\d{8}-[0-9a-f]{12}$")


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
        required_fields = DEEPSEEK_REQUIRED_FIELDS if str(record.get("role", "")).startswith("deepseek-") else REQUIRED_FIELDS
        missing = sorted(required_fields - set(record))
        allowed_fields = required_fields | (DEEPSEEK_OPTIONAL_FIELDS if str(record.get("role", "")).startswith("deepseek-") else set())
        unknown = sorted(set(record) - allowed_fields)
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
    if not isinstance(role, str) or role not in ACCEPTED_ROLE_ASSIGNMENTS:
        failures.append(f"{record_path}: role is not permitted: {role!r}")
    else:
        if role in seen_roles:
            failures.append(f"{record_path}: duplicate role: {role}")
        seen_roles.add(role)
        expected_provider, expected_interface = ACCEPTED_ROLE_ASSIGNMENTS[role]
        if record["provider"] != expected_provider:
            failures.append(f"{record_path}: provider for {role} must be {expected_provider}")
        if record["interface"] != expected_interface:
            failures.append(f"{record_path}: interface for {role} must be {expected_interface}")
        if role.startswith("deepseek-") and record["model"] != "deepseek-v4-pro":
            failures.append(f"{record_path}: model for {role} must be deepseek-v4-pro")

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
    prefixes: tuple[str, ...] = ("prompt", "artifact", "transcript")
    if isinstance(role, str) and role.startswith("deepseek-"):
        prefixes = ("artifact", "transcript")
        if "prompt_path" in record:
            prefixes = ("prompt",) + prefixes
        prefixes += ("source_log",)
    for prefix in prefixes:
        resolved = _validate_artifact(repo_root, record_path, record, prefix, failures)
        if resolved is not None:
            resolved_artifacts[prefix] = resolved
    transcript_path = resolved_artifacts.get("transcript")
    if transcript_path is not None:
        _validate_transcript(record_path, record, transcript_path, failures, resolved_artifacts.get("source_log"))


def _validate_run_id(record_path: Path, role: Any, value: Any, failures: list[str]) -> None:
    if not isinstance(value, str):
        failures.append(f"{record_path}: run_id must be a provider-issued identifier")
        return
    if isinstance(role, str) and role.startswith("deepseek-"):
        if not DEEPSEEK_RUN_ID_PATTERN.fullmatch(value):
            failures.append(f"{record_path}: DeepSeek run_id must identify the governed stage and date")
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
    source_log_path: Path | None = None,
) -> None:
    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{record_path}: transcript must be valid structured JSON: {exc}")
        return
    if not isinstance(transcript, dict):
        failures.append(f"{record_path}: transcript must be valid structured JSON object")
        return

    role = record["role"]
    if isinstance(role, str) and role.startswith("deepseek-"):
        _validate_deepseek_transcript(record_path, record, transcript, source_log_path, failures)
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


def _validate_deepseek_transcript(
    record_path: Path,
    record: dict[str, Any],
    transcript: dict[str, Any],
    source_log_path: Path | None,
    failures: list[str],
) -> None:
    required = {
        "schema_version",
        "role",
        "provider",
        "session_id",
        "model",
        "source_log_path",
        "source_log_sha256",
        "result",
        "endpoint",
        "usage",
        "cost_usd",
    }
    missing = sorted(required - set(transcript))
    if missing:
        failures.append(f"{record_path}: DeepSeek transcript missing execution fields: {missing}")
        return
    for field_name in ("role", "provider", "model"):
        if transcript[field_name] != record[field_name]:
            failures.append(f"{record_path}: DeepSeek transcript {field_name} must match execution record")
    if transcript["schema_version"] != TRANSCRIPT_SCHEMA_VERSION:
        failures.append(f"{record_path}: DeepSeek transcript schema_version must be {TRANSCRIPT_SCHEMA_VERSION}")
    if transcript["session_id"] != record["run_id"]:
        failures.append(f"{record_path}: DeepSeek transcript session_id must match run_id")
    if transcript["source_log_path"] != record["source_log_path"]:
        failures.append(f"{record_path}: DeepSeek transcript source_log_path must match execution record")
    if transcript["source_log_sha256"] != record["source_log_sha256"]:
        failures.append(f"{record_path}: DeepSeek transcript source_log_sha256 must match execution record")
    if source_log_path is None:
        return
    try:
        lines = [json.loads(line) for line in source_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"{record_path}: DeepSeek source log must contain structured JSON lines: {exc}")
        return
    if not lines:
        failures.append(f"{record_path}: DeepSeek source log must not be empty")
    for event in lines:
        if not isinstance(event, dict):
            failures.append(f"{record_path}: DeepSeek source log events must be JSON objects")
            continue
        if event.get("provider") != "deepseek" or event.get("model") != "deepseek-v4-pro":
            failures.append(f"{record_path}: DeepSeek source log identity is invalid")
        if event.get("run_id") != record["run_id"] and event.get("sessionId") != record["run_id"]:
            failures.append(f"{record_path}: DeepSeek source log run identity must match run_id")
    if not isinstance(transcript["result"], str) or not transcript["result"].strip():
        failures.append(f"{record_path}: DeepSeek transcript result must be non-empty")
    if transcript["endpoint"] != "https://api.deepseek.com/anthropic/v1/messages":
        failures.append(f"{record_path}: DeepSeek transcript endpoint is not the governed endpoint")
    usage = transcript["usage"]
    if not isinstance(usage, dict) or any(
        not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool) or usage[key] < 0
        for key in ("input_tokens", "output_tokens")
    ):
        failures.append(f"{record_path}: DeepSeek transcript usage must contain non-negative token counts")
    cost = transcript["cost_usd"]
    if isinstance(cost, bool) or not isinstance(cost, int | float) or cost < 0:
        failures.append(f"{record_path}: DeepSeek transcript cost_usd must be non-negative")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI delivery model execution records")
    parser.add_argument("records", nargs="*", type=Path, help="record paths relative to the repository root")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--discover", action="store_true", help="discover model records under evidence")
    parser.add_argument("--require-all", action="store_true", help="require the current DeepSeek and Codex delivery roles")
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
