from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, cast

from . import domain

STATE_SCHEMA = "delivery-ops-state/v1"
TRANSACTION_SCHEMA = "delivery-ops-transaction/v1"

_LOCKS_GUARD = threading.Lock()
_DIRECTORY_LOCKS: dict[Path, Any] = {}


class StoreError(RuntimeError):
    """Raised when persisted state cannot be loaded safely."""


def _directory_lock(data_dir: Path) -> Any:
    with _LOCKS_GUARD:
        lock = _DIRECTORY_LOCKS.get(data_dir)
        if lock is None:
            lock = threading.RLock()
            _DIRECTORY_LOCKS[data_dir] = lock
        return lock


class DeliveryStore:
    def __init__(self, data_dir: str | Path) -> None:
        requested_dir = Path(data_dir)
        requested_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = requested_dir.resolve()
        self.state_path = self.data_dir / "state.json"
        self.tmp_state_path = self.data_dir / "state.json.tmp"
        self.audit_path = self.data_dir / "audit.jsonl"
        self.journal_path = self.data_dir / "transaction.json"
        self.tmp_journal_path = self.data_dir / "transaction.json.tmp"
        self._lock = _directory_lock(self.data_dir)
        self._state: dict[str, Any] = self._empty_state()
        self._audit: list[dict[str, Any]] = []
        with self._lock:
            self._refresh()

    def list_releases(self) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh()
            return copy.deepcopy(self._state["releases"])

    def get_release(self, release_id: str) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            return copy.deepcopy(self._find_release(release_id))

    def create_release(self, payload: dict[str, Any], *, actor: str, now: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            release, event = domain.create_release(payload, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"].append(release)
            self._commit(old_state, candidate, event)
            return copy.deepcopy(release)

    def update_release(
        self,
        release_id: str,
        changes: dict[str, Any],
        *,
        actor: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            index, current = self._find_release_with_index(release_id)
            updated, event = domain.transition_release(current, changes, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"][index] = updated
            self._commit(old_state, candidate, event)
            return copy.deepcopy(updated)

    def add_gate(
        self,
        release_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            index, current = self._find_release_with_index(release_id)
            updated, gate, event = domain.add_gate(current, payload, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"][index] = updated
            self._commit(old_state, candidate, event)
            return copy.deepcopy(gate)

    def update_gate(
        self,
        release_id: str,
        gate_id: str,
        changes: dict[str, Any],
        *,
        actor: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            index, current = self._find_release_with_index(release_id)
            updated, gate, event = domain.update_gate(current, gate_id, changes, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"][index] = updated
            self._commit(old_state, candidate, event)
            return copy.deepcopy(gate)

    def add_risk(
        self,
        release_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            index, current = self._find_release_with_index(release_id)
            updated, risk, event = domain.add_risk(current, payload, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"][index] = updated
            self._commit(old_state, candidate, event)
            return copy.deepcopy(risk)

    def update_risk(
        self,
        release_id: str,
        risk_id: str,
        changes: dict[str, Any],
        *,
        actor: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            old_state = copy.deepcopy(self._state)
            index, current = self._find_release_with_index(release_id)
            updated, risk, event = domain.update_risk(current, risk_id, changes, actor=actor, now=now)
            candidate = copy.deepcopy(old_state)
            candidate["releases"][index] = updated
            self._commit(old_state, candidate, event)
            return copy.deepcopy(risk)

    def get_release_audit(self, release_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh()
            release_key = self._normalize_uuid(release_id, "release_id")
            self._find_release(release_key)
            events = [copy.deepcopy(item) for item in self._audit if item["release_id"] == release_key]
            return list(reversed(events))

    def get_audit(self) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh()
            return list(reversed(copy.deepcopy(self._audit)))

    def _refresh(self) -> None:
        if self.tmp_journal_path.exists():
            self.tmp_journal_path.unlink()
        if self.journal_path.exists():
            self._recover_transaction()
        if self.tmp_state_path.exists():
            self.tmp_state_path.unlink()
        self._state = self._load_state()
        self._audit = self._load_audit()

    def _commit(
        self,
        old_state: dict[str, Any],
        candidate_state: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        old_audit = copy.deepcopy(self._audit)
        audit_prefix = self.audit_path.read_bytes() if self.audit_path.exists() else b""
        journal = {
            "schema_version": TRANSACTION_SCHEMA,
            "old_state": domain.validate_state(copy.deepcopy(old_state)),
            "candidate_state": domain.validate_state(copy.deepcopy(candidate_state)),
            "event": domain.validate_audit_event(copy.deepcopy(event)),
            "audit_prefix_bytes": len(audit_prefix),
            "audit_prefix_sha256": hashlib.sha256(audit_prefix).hexdigest(),
        }
        try:
            self._write_journal(journal)
        except BaseException:
            if self.journal_path.exists():
                try:
                    self._recover_transaction()
                except BaseException:
                    pass
            self._state = old_state
            self._audit = old_audit
            raise

        try:
            self._write_state(candidate_state)
            self._append_audit(event)
        except BaseException:
            try:
                self._recover_transaction()
                self._state = self._load_state()
                self._audit = self._load_audit()
            except BaseException:
                self._state = old_state
                self._audit = old_audit
            raise

        try:
            self._clear_journal()
        except OSError:
            # A durable journal is safe to leave behind; startup recovery is idempotent.
            pass
        self._state = copy.deepcopy(candidate_state)
        self._audit = old_audit + [copy.deepcopy(event)]

    def _write_journal(self, journal: dict[str, Any]) -> None:
        self._write_json_atomic(self.tmp_journal_path, self.journal_path, journal)

    def _write_state(self, state: dict[str, Any]) -> None:
        validated = domain.validate_state(copy.deepcopy(state))
        self._write_json_atomic(self.tmp_state_path, self.state_path, validated)

    def _write_json_atomic(self, staging_path: Path, target_path: Path, payload: dict[str, Any]) -> None:
        try:
            with staging_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staging_path, target_path)
            self._fsync_data_dir()
        except BaseException:
            if staging_path.exists():
                staging_path.unlink()
            raise

    def _append_audit(self, event: dict[str, Any]) -> None:
        serialized = self._serialize_event(event)
        with self.audit_path.open("ab") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

    def _recover_transaction(self) -> None:
        if not self.journal_path.exists():
            return
        if self.tmp_state_path.exists():
            self.tmp_state_path.unlink()
        journal = self._load_journal()
        old_state = domain.validate_state(copy.deepcopy(journal["old_state"]))
        candidate_state = domain.validate_state(copy.deepcopy(journal["candidate_state"]))
        event = domain.validate_audit_event(copy.deepcopy(journal["event"]))
        prefix_bytes = journal["audit_prefix_bytes"]
        prefix_hash = journal["audit_prefix_sha256"]
        if not isinstance(prefix_bytes, int) or isinstance(prefix_bytes, bool) or prefix_bytes < 0:
            raise StoreError("Malformed transaction journal: audit_prefix_bytes must be a non-negative integer")
        if not isinstance(prefix_hash, str) or len(prefix_hash) != 64:
            raise StoreError("Malformed transaction journal: audit_prefix_sha256 must be a SHA-256 digest")

        audit_bytes = self.audit_path.read_bytes() if self.audit_path.exists() else b""
        if len(audit_bytes) < prefix_bytes:
            raise StoreError("Audit file is shorter than the transaction journal prefix")
        prefix = audit_bytes[:prefix_bytes]
        if hashlib.sha256(prefix).hexdigest() != prefix_hash:
            raise StoreError("Audit prefix does not match the transaction journal")

        suffix = audit_bytes[prefix_bytes:]
        event_line = self._serialize_event(event)
        if suffix == event_line:
            self._write_state(candidate_state)
        else:
            self._write_state(old_state)
            if suffix:
                self._truncate_audit(prefix_bytes)
        self._clear_journal()

    def _load_journal(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise StoreError(f"Malformed transaction journal at {self.journal_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise StoreError("Malformed transaction journal: expected an object")
        required = {
            "schema_version",
            "old_state",
            "candidate_state",
            "event",
            "audit_prefix_bytes",
            "audit_prefix_sha256",
        }
        if set(payload) != required or payload.get("schema_version") != TRANSACTION_SCHEMA:
            raise StoreError("Malformed transaction journal: invalid schema")
        return payload

    def _truncate_audit(self, size: int) -> None:
        if not self.audit_path.exists():
            return
        with self.audit_path.open("r+b") as handle:
            handle.truncate(size)
            handle.flush()
            os.fsync(handle.fileno())

    def _clear_journal(self) -> None:
        if self.journal_path.exists():
            self.journal_path.unlink()
            self._fsync_data_dir()

    def _fsync_data_dir(self) -> None:
        descriptor = os.open(self.data_dir, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"Malformed state file at {self.state_path}: {exc.msg}") from exc
        except OSError as exc:
            raise StoreError(f"Could not read state file at {self.state_path}: {exc}") from exc
        try:
            return domain.validate_state(raw)
        except domain.ValidationError as exc:
            raise StoreError(f"Malformed state file at {self.state_path}: {exc}") from exc

    def _load_audit(self) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self.audit_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise StoreError(f"Malformed audit file at {self.audit_path}:{line_number}: {exc.msg}") from exc
                    try:
                        events.append(domain.validate_audit_event(payload))
                    except domain.ValidationError as exc:
                        raise StoreError(f"Malformed audit file at {self.audit_path}:{line_number}: {exc}") from exc
        except OSError as exc:
            raise StoreError(f"Could not read audit file at {self.audit_path}: {exc}") from exc
        return events

    def _find_release(self, release_id: str) -> dict[str, Any]:
        release_key = self._normalize_uuid(release_id, "release_id")
        releases = cast(list[dict[str, Any]], self._state["releases"])
        for release in releases:
            if release["id"] == release_key:
                return release
        raise domain.NotFoundError("release not found")

    def _find_release_with_index(self, release_id: str) -> tuple[int, dict[str, Any]]:
        release_key = self._normalize_uuid(release_id, "release_id")
        for index, release in enumerate(self._state["releases"]):
            if release["id"] == release_key:
                return index, copy.deepcopy(release)
        raise domain.NotFoundError("release not found")

    def _normalize_uuid(self, value: str, field_name: str) -> str:
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError) as exc:
            raise domain.ValidationError(f"{field_name} must be a UUID") from exc

    def _serialize_event(self, event: dict[str, Any]) -> bytes:
        validated = domain.validate_audit_event(copy.deepcopy(event))
        return (json.dumps(validated, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    def _empty_state(self) -> dict[str, Any]:
        return {"schema_version": STATE_SCHEMA, "releases": []}
