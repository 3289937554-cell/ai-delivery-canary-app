from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

RFC3339_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RELEASE_STATUSES = {"planned", "validating", "blocked", "ready", "released", "rolled_back"}
GATE_STATUSES = {"pending", "passed", "failed", "waived"}
RISK_SEVERITIES = {"low", "medium", "high", "critical"}
RISK_STATUSES = {"open", "mitigated", "accepted", "closed"}
RELEASE_TRANSITIONS = {
    "planned": {"validating"},
    "validating": {"blocked", "ready"},
    "blocked": {"validating"},
    "ready": {"validating", "released"},
    "released": {"rolled_back"},
    "rolled_back": set(),
}
GATE_TRANSITIONS = {
    "pending": {"passed", "failed", "waived"},
    "passed": {"pending"},
    "failed": {"pending", "passed", "waived"},
    "waived": {"pending"},
}
RISK_TRANSITIONS = {
    "open": {"mitigated", "accepted", "closed"},
    "mitigated": {"open", "accepted", "closed"},
    "accepted": {"open", "closed"},
    "closed": {"open"},
}


class DomainError(ValueError):
    """Base error for domain validation failures."""


class ValidationError(DomainError):
    """Raised when payloads are malformed."""


class ConflictError(DomainError):
    """Raised when state transitions are not permitted."""


class NotFoundError(DomainError):
    """Raised when nested entities are missing."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime(RFC3339_FORMAT)


def _ensure_string(value: Any, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    trimmed = value.strip()
    if not trimmed:
        raise ValidationError(f"{field_name} must not be empty")
    if len(trimmed) > maximum:
        raise ValidationError(f"{field_name} must be <= {maximum} characters")
    return trimmed


def _ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a boolean")
    return value


def _ensure_choice(value: Any, field_name: str, choices: set[str]) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    if value not in choices:
        raise ValidationError(f"{field_name} must be one of {sorted(choices)}")
    return value


def _ensure_dict(payload: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError(f"{field_name} must be an object")
    return payload


def _ensure_list(payload: Any, field_name: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ValidationError(f"{field_name} must be a list")
    return payload


def _parse_timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    try:
        parsed = datetime.strptime(value, RFC3339_FORMAT)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be RFC3339 UTC") from exc
    if parsed.tzinfo is not None:
        raise ValidationError(f"{field_name} must be RFC3339 UTC")
    return value


def _ensure_monotonic_timestamp(current: dict[str, Any], timestamp: str) -> None:
    if timestamp < current["updated_at"]:
        raise ValidationError("updated_at must be >= prior updated_at")


def _ensure_uuid(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"{field_name} must be a UUID") from exc
    return str(parsed)


def _event(
    release_id: str,
    *,
    entity_type: str,
    entity_id: str,
    actor: str,
    action: str,
    prior_status: str | None,
    new_status: str | None,
    details: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "release_id": release_id,
        "entity_type": _ensure_choice(entity_type, "entity_type", {"release", "gate", "risk"}),
        "entity_id": _ensure_uuid(entity_id, "entity_id"),
        "actor": _ensure_string(actor, "actor", 120),
        "action": action,
        "prior_status": prior_status,
        "new_status": new_status,
        "details": copy.deepcopy(details),
        "created_at": _parse_timestamp(now, "created_at"),
    }


def create_release(payload: dict[str, Any], *, actor: str, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    data = _ensure_dict(payload, "release")
    extra = set(data) - {"id", "title", "version"}
    if extra:
        raise ValidationError(f"unknown release fields: {sorted(extra)}")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    release: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": _ensure_string(data.get("title"), "title", 200),
        "version": _ensure_string(data.get("version"), "version", 80),
        "status": "planned",
        "created_at": timestamp,
        "updated_at": timestamp,
        "gates": [],
        "risks": [],
    }
    validate_release(release)
    return release, _event(
        release["id"],
        entity_type="release",
        entity_id=release["id"],
        actor=actor,
        action="release.created",
        prior_status=None,
        new_status="planned",
        details={"status": "planned"},
        now=timestamp,
    )


def transition_release(
    release: dict[str, Any],
    changes: dict[str, Any],
    *,
    actor: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = validate_release(copy.deepcopy(release))
    payload = _ensure_dict(changes, "changes")
    extra = set(payload) - {"title", "version", "status"}
    if extra:
        raise ValidationError(f"unknown release fields: {sorted(extra)}")
    if not payload:
        raise ValidationError("changes must not be empty")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    _ensure_monotonic_timestamp(current, timestamp)
    updated = copy.deepcopy(current)
    details: dict[str, Any] = {}
    prior_status = updated["status"]
    new_status = updated["status"]
    if "title" in payload:
        updated["title"] = _ensure_string(payload["title"], "title", 200)
        details["title"] = updated["title"]
    if "version" in payload:
        updated["version"] = _ensure_string(payload["version"], "version", 80)
        details["version"] = updated["version"]
    if "status" in payload:
        target = _ensure_choice(payload["status"], "status", RELEASE_STATUSES)
        if target != updated["status"]:
            if target not in RELEASE_TRANSITIONS[updated["status"]]:
                raise ConflictError(f"release transition {updated['status']} -> {target} is not allowed")
            _ensure_ready_requirements(updated, target)
            updated["status"] = target
            details["status"] = target
        new_status = updated["status"]
        details["status"] = target
    updated["updated_at"] = timestamp
    validate_release(updated)
    return updated, _event(
        updated["id"],
        entity_type="release",
        entity_id=updated["id"],
        actor=actor,
        action="release.updated",
        prior_status=prior_status,
        new_status=new_status,
        details=details,
        now=timestamp,
    )


def add_gate(
    release: dict[str, Any],
    payload: dict[str, Any],
    *,
    actor: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = validate_release(copy.deepcopy(release))
    data = _ensure_dict(payload, "gate")
    extra = set(data) - {"id", "name", "required"}
    if extra:
        raise ValidationError(f"unknown gate fields: {sorted(extra)}")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    gate: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": _ensure_string(data.get("name"), "name", 120),
        "required": _ensure_bool(data.get("required"), "required"),
        "status": "pending",
        "waiver_reason": None,
    }
    _ensure_monotonic_timestamp(current, timestamp)
    updated = copy.deepcopy(current)
    updated["gates"].append(gate)
    updated["updated_at"] = timestamp
    _ensure_ready_requirements(updated, updated["status"])
    validate_release(updated)
    return updated, copy.deepcopy(gate), _event(
        updated["id"],
        entity_type="gate",
        entity_id=gate["id"],
        actor=actor,
        action="gate.created",
        prior_status=None,
        new_status=gate["status"],
        details={"gate_id": gate["id"]},
        now=timestamp,
    )


def update_gate(
    release: dict[str, Any],
    gate_id: str,
    changes: dict[str, Any],
    *,
    actor: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = validate_release(copy.deepcopy(release))
    payload = _ensure_dict(changes, "changes")
    extra = set(payload) - {"name", "required", "status", "waiver_reason"}
    if extra:
        raise ValidationError(f"unknown gate fields: {sorted(extra)}")
    if not payload:
        raise ValidationError("changes must not be empty")
    gate_key = _ensure_uuid(gate_id, "gate_id")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    _ensure_monotonic_timestamp(current, timestamp)
    updated = copy.deepcopy(current)
    gate = _find_by_id(updated["gates"], gate_key, "gate")
    original_status = gate["status"]
    if "name" in payload:
        gate["name"] = _ensure_string(payload["name"], "name", 120)
    if "required" in payload:
        gate["required"] = _ensure_bool(payload["required"], "required")
    if "status" in payload:
        target = _ensure_choice(payload["status"], "status", GATE_STATUSES)
        if target != original_status and target not in GATE_TRANSITIONS[original_status]:
            raise ConflictError(f"gate transition {original_status} -> {target} is not allowed")
        gate["status"] = target
    if gate["status"] == "waived":
        gate["waiver_reason"] = _ensure_string(payload.get("waiver_reason", gate.get("waiver_reason")), "waiver_reason", 500)
    elif "waiver_reason" in payload:
        gate["waiver_reason"] = None if payload["waiver_reason"] is None else _ensure_string(payload["waiver_reason"], "waiver_reason", 500)
    updated["updated_at"] = timestamp
    _ensure_ready_requirements(updated, updated["status"])
    validate_release(updated)
    return updated, copy.deepcopy(gate), _event(
        updated["id"],
        entity_type="gate",
        entity_id=gate["id"],
        actor=actor,
        action="gate.updated",
        prior_status=original_status,
        new_status=gate["status"],
        details={"gate_id": gate["id"]},
        now=timestamp,
    )


def add_risk(
    release: dict[str, Any],
    payload: dict[str, Any],
    *,
    actor: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = validate_release(copy.deepcopy(release))
    data = _ensure_dict(payload, "risk")
    extra = set(data) - {"id", "description", "severity", "blocking"}
    if extra:
        raise ValidationError(f"unknown risk fields: {sorted(extra)}")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    risk: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "description": _ensure_string(data.get("description"), "description", 500),
        "severity": _ensure_choice(data.get("severity"), "severity", RISK_SEVERITIES),
        "blocking": _ensure_bool(data.get("blocking"), "blocking"),
        "status": "open",
        "acceptance_reason": None,
    }
    _ensure_monotonic_timestamp(current, timestamp)
    updated = copy.deepcopy(current)
    updated["risks"].append(risk)
    updated["updated_at"] = timestamp
    _ensure_ready_requirements(updated, updated["status"])
    validate_release(updated)
    return updated, copy.deepcopy(risk), _event(
        updated["id"],
        entity_type="risk",
        entity_id=risk["id"],
        actor=actor,
        action="risk.created",
        prior_status=None,
        new_status=risk["status"],
        details={"risk_id": risk["id"]},
        now=timestamp,
    )


def update_risk(
    release: dict[str, Any],
    risk_id: str,
    changes: dict[str, Any],
    *,
    actor: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current = validate_release(copy.deepcopy(release))
    payload = _ensure_dict(changes, "changes")
    extra = set(payload) - {"description", "severity", "blocking", "status", "acceptance_reason"}
    if extra:
        raise ValidationError(f"unknown risk fields: {sorted(extra)}")
    if not payload:
        raise ValidationError("changes must not be empty")
    risk_key = _ensure_uuid(risk_id, "risk_id")
    timestamp = _parse_timestamp(now or utc_now(), "now")
    _ensure_monotonic_timestamp(current, timestamp)
    updated = copy.deepcopy(current)
    risk = _find_by_id(updated["risks"], risk_key, "risk")
    original_status = risk["status"]
    if "description" in payload:
        risk["description"] = _ensure_string(payload["description"], "description", 500)
    if "severity" in payload:
        risk["severity"] = _ensure_choice(payload["severity"], "severity", RISK_SEVERITIES)
    if "blocking" in payload:
        risk["blocking"] = _ensure_bool(payload["blocking"], "blocking")
    if "status" in payload:
        target = _ensure_choice(payload["status"], "status", RISK_STATUSES)
        if target != original_status and target not in RISK_TRANSITIONS[original_status]:
            raise ConflictError(f"risk transition {original_status} -> {target} is not allowed")
        risk["status"] = target
    if risk["status"] == "accepted":
        risk["acceptance_reason"] = _ensure_string(
            payload.get("acceptance_reason", risk.get("acceptance_reason")),
            "acceptance_reason",
            500,
        )
    elif "acceptance_reason" in payload:
        risk["acceptance_reason"] = None if payload["acceptance_reason"] is None else _ensure_string(
            payload["acceptance_reason"],
            "acceptance_reason",
            500,
        )
    updated["updated_at"] = timestamp
    _ensure_ready_requirements(updated, updated["status"])
    validate_release(updated)
    return updated, copy.deepcopy(risk), _event(
        updated["id"],
        entity_type="risk",
        entity_id=risk["id"],
        actor=actor,
        action="risk.updated",
        prior_status=original_status,
        new_status=risk["status"],
        details={"risk_id": risk["id"]},
        now=timestamp,
    )


def validate_release(release: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(release, "release")
    required_keys = {"id", "title", "version", "status", "created_at", "updated_at", "gates", "risks"}
    extra = set(data) - required_keys
    missing = required_keys - set(data)
    if missing:
        raise ValidationError(f"release missing fields: {sorted(missing)}")
    if extra:
        raise ValidationError(f"unknown release fields: {sorted(extra)}")
    data["id"] = _ensure_uuid(data["id"], "id")
    data["title"] = _ensure_string(data["title"], "title", 200)
    data["version"] = _ensure_string(data["version"], "version", 80)
    data["status"] = _ensure_choice(data["status"], "status", RELEASE_STATUSES)
    data["created_at"] = _parse_timestamp(data["created_at"], "created_at")
    data["updated_at"] = _parse_timestamp(data["updated_at"], "updated_at")
    if data["updated_at"] < data["created_at"]:
        raise ValidationError("updated_at must be >= created_at")
    data["gates"] = [_validate_gate(gate) for gate in _ensure_list(data["gates"], "gates")]
    data["risks"] = [_validate_risk(risk) for risk in _ensure_list(data["risks"], "risks")]
    _ensure_unique_ids(data["gates"], "gate")
    _ensure_unique_ids(data["risks"], "risk")
    return data


def validate_state(payload: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(payload, "state")
    required_keys = {"schema_version", "releases"}
    extra = set(data) - required_keys
    missing = required_keys - set(data)
    if missing:
        raise ValidationError(f"state missing fields: {sorted(missing)}")
    if extra:
        raise ValidationError(f"unknown state fields: {sorted(extra)}")
    if data["schema_version"] != "delivery-ops-state/v1":
        raise ValidationError("schema_version must be delivery-ops-state/v1")
    releases = [validate_release(copy.deepcopy(item)) for item in _ensure_list(data["releases"], "releases")]
    _ensure_unique_ids(releases, "release")
    return {"schema_version": "delivery-ops-state/v1", "releases": releases}


def validate_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(event, "audit event")
    required_keys = {
        "id",
        "release_id",
        "entity_type",
        "entity_id",
        "actor",
        "action",
        "prior_status",
        "new_status",
        "details",
        "created_at",
    }
    extra = set(data) - required_keys
    missing = required_keys - set(data)
    if missing:
        raise ValidationError(f"audit event missing fields: {sorted(missing)}")
    if extra:
        raise ValidationError(f"unknown audit event fields: {sorted(extra)}")
    data["id"] = _ensure_uuid(data["id"], "id")
    data["release_id"] = _ensure_uuid(data["release_id"], "release_id")
    data["entity_type"] = _ensure_choice(data["entity_type"], "entity_type", {"release", "gate", "risk"})
    data["entity_id"] = _ensure_uuid(data["entity_id"], "entity_id")
    data["actor"] = _ensure_string(data["actor"], "actor", 120)
    data["action"] = _ensure_string(data["action"], "action", 120)
    if data["prior_status"] is not None and not isinstance(data["prior_status"], str):
        raise ValidationError("prior_status must be a string or null")
    if data["new_status"] is not None and not isinstance(data["new_status"], str):
        raise ValidationError("new_status must be a string or null")
    data["details"] = _ensure_dict(data["details"], "details")
    data["created_at"] = _parse_timestamp(data["created_at"], "created_at")
    return data


def _validate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(gate, "gate")
    required_keys = {"id", "name", "required", "status", "waiver_reason"}
    extra = set(data) - required_keys
    missing = required_keys - set(data)
    if missing:
        raise ValidationError(f"gate missing fields: {sorted(missing)}")
    if extra:
        raise ValidationError(f"unknown gate fields: {sorted(extra)}")
    data["id"] = _ensure_uuid(data["id"], "id")
    data["name"] = _ensure_string(data["name"], "name", 120)
    data["required"] = _ensure_bool(data["required"], "required")
    data["status"] = _ensure_choice(data["status"], "status", GATE_STATUSES)
    if data["status"] == "waived":
        data["waiver_reason"] = _ensure_string(data["waiver_reason"], "waiver_reason", 500)
    elif data["waiver_reason"] is not None:
        data["waiver_reason"] = _ensure_string(data["waiver_reason"], "waiver_reason", 500)
    return data


def _validate_risk(risk: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(risk, "risk")
    required_keys = {"id", "description", "severity", "blocking", "status", "acceptance_reason"}
    extra = set(data) - required_keys
    missing = required_keys - set(data)
    if missing:
        raise ValidationError(f"risk missing fields: {sorted(missing)}")
    if extra:
        raise ValidationError(f"unknown risk fields: {sorted(extra)}")
    data["id"] = _ensure_uuid(data["id"], "id")
    data["description"] = _ensure_string(data["description"], "description", 500)
    data["severity"] = _ensure_choice(data["severity"], "severity", RISK_SEVERITIES)
    data["blocking"] = _ensure_bool(data["blocking"], "blocking")
    data["status"] = _ensure_choice(data["status"], "status", RISK_STATUSES)
    if data["status"] == "accepted":
        data["acceptance_reason"] = _ensure_string(data["acceptance_reason"], "acceptance_reason", 500)
    elif data["acceptance_reason"] is not None:
        data["acceptance_reason"] = _ensure_string(data["acceptance_reason"], "acceptance_reason", 500)
    return data


def _find_by_id(items: list[dict[str, Any]], item_id: str, item_name: str) -> dict[str, Any]:
    for item in items:
        if item["id"] == item_id:
            return item
    raise NotFoundError(f"{item_name} not found")


def _ensure_unique_ids(items: list[dict[str, Any]], item_name: str) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = item["id"]
        if item_id in seen:
            raise ValidationError(f"duplicate {item_name} id: {item_id}")
        seen.add(item_id)


def _ensure_ready_requirements(release: dict[str, Any], target: str) -> None:
    if target not in {"ready", "released"}:
        return
    for gate in release["gates"]:
        if gate["required"] and gate["status"] not in {"passed", "waived"}:
            raise ConflictError("required gates must be passed or waived before ready")
    for risk in release["risks"]:
        if risk["blocking"] and risk["status"] in {"open", "mitigated"}:
            raise ConflictError("blocking risks must not be open or mitigated before ready")
