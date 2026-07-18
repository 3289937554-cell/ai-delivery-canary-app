from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delivery_ops import domain  # type: ignore[import-not-found]


class DomainTests(unittest.TestCase):
    def test_audit_events_capture_entity_and_status_facts(self) -> None:
        release, created_event = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, gate, gate_event = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        release, risk, risk_event = domain.add_risk(
            release,
            {
                "description": "Rollback note review",
                "severity": "high",
                "blocking": True,
            },
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )
        _, release_event = domain.transition_release(
            release,
            {"status": "validating"},
            actor="local-operator",
            now="2026-07-16T08:03:00Z",
        )

        self.assertEqual(created_event["entity_type"], "release")
        self.assertEqual(created_event["entity_id"], release["id"])
        self.assertIsNone(created_event["prior_status"])
        self.assertEqual(created_event["new_status"], "planned")

        self.assertEqual(gate_event["entity_type"], "gate")
        self.assertEqual(gate_event["entity_id"], gate["id"])
        self.assertIsNone(gate_event["prior_status"])
        self.assertEqual(gate_event["new_status"], "pending")

        self.assertEqual(risk_event["entity_type"], "risk")
        self.assertEqual(risk_event["entity_id"], risk["id"])
        self.assertIsNone(risk_event["prior_status"])
        self.assertEqual(risk_event["new_status"], "open")

        self.assertEqual(release_event["entity_type"], "release")
        self.assertEqual(release_event["entity_id"], release["id"])
        self.assertEqual(release_event["prior_status"], "planned")
        self.assertEqual(release_event["new_status"], "validating")

    def test_create_release_initializes_expected_shape_and_audit_event(self) -> None:
        release, event = domain.create_release(
            {
                "title": "Operator console rollout",
                "version": "2026.07.16",
            },
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )

        self.assertRegex(release["id"], r"^[0-9a-f-]{36}$")
        self.assertEqual(release["title"], "Operator console rollout")
        self.assertEqual(release["version"], "2026.07.16")
        self.assertEqual(release["status"], "planned")
        self.assertEqual(release["created_at"], "2026-07-16T08:00:00Z")
        self.assertEqual(release["updated_at"], "2026-07-16T08:00:00Z")
        self.assertEqual(release["gates"], [])
        self.assertEqual(release["risks"], [])
        self.assertEqual(event["release_id"], release["id"])
        self.assertEqual(event["action"], "release.created")
        self.assertEqual(event["actor"], "local-operator")
        self.assertEqual(event["created_at"], "2026-07-16T08:00:00Z")

    def test_release_transition_to_ready_requires_clear_gates_and_risks(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release = domain.transition_release(
            release,
            {"status": "validating"},
            actor="local-operator",
            now="2026-07-16T08:05:00Z",
        )[0]
        release = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:06:00Z",
        )[0]
        release = domain.add_risk(
            release,
            {
                "description": "Rollback path not confirmed",
                "severity": "high",
                "blocking": True,
            },
            actor="local-operator",
            now="2026-07-16T08:07:00Z",
        )[0]

        with self.assertRaises(domain.ConflictError):
            domain.transition_release(
                release,
                {"status": "ready"},
                actor="local-operator",
                now="2026-07-16T08:08:00Z",
            )

        gate_id = release["gates"][0]["id"]
        risk_id = release["risks"][0]["id"]
        release = domain.update_gate(
            release,
            gate_id,
            {"status": "waived", "waiver_reason": "Manual verification complete"},
            actor="local-operator",
            now="2026-07-16T08:09:00Z",
        )[0]
        release = domain.update_risk(
            release,
            risk_id,
            {"status": "accepted", "acceptance_reason": "Scheduled mitigation after release"},
            actor="local-operator",
            now="2026-07-16T08:10:00Z",
        )[0]

        updated, event = domain.transition_release(
            release,
            {"status": "ready"},
            actor="local-operator",
            now="2026-07-16T08:11:00Z",
        )

        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["updated_at"], "2026-07-16T08:11:00Z")
        self.assertEqual(event["action"], "release.updated")

    def test_ready_release_rejects_gate_or_risk_changes_that_break_readiness(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release = domain.transition_release(
            release,
            {"status": "validating"},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )[0]
        release, gate, _ = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )
        release = domain.update_gate(
            release,
            gate["id"],
            {"status": "passed"},
            actor="local-operator",
            now="2026-07-16T08:03:00Z",
        )[0]
        release, risk, _ = domain.add_risk(
            release,
            {"description": "Rollback readiness", "severity": "high", "blocking": True},
            actor="local-operator",
            now="2026-07-16T08:04:00Z",
        )
        release = domain.update_risk(
            release,
            risk["id"],
            {"status": "accepted", "acceptance_reason": "Owner accepted for canary"},
            actor="local-operator",
            now="2026-07-16T08:05:00Z",
        )[0]
        release = domain.transition_release(
            release,
            {"status": "ready"},
            actor="local-operator",
            now="2026-07-16T08:06:00Z",
        )[0]

        invalid_operations = (
            lambda: domain.add_gate(
                release,
                {"name": "Security", "required": True},
                actor="local-operator",
                now="2026-07-16T08:07:00Z",
            ),
            lambda: domain.update_gate(
                release,
                gate["id"],
                {"status": "pending"},
                actor="local-operator",
                now="2026-07-16T08:07:00Z",
            ),
            lambda: domain.add_risk(
                release,
                {"description": "Capacity regression", "severity": "critical", "blocking": True},
                actor="local-operator",
                now="2026-07-16T08:07:00Z",
            ),
            lambda: domain.update_risk(
                release,
                risk["id"],
                {"status": "open"},
                actor="local-operator",
                now="2026-07-16T08:07:00Z",
            ),
        )
        for operation in invalid_operations:
            with self.subTest(operation=operation):
                with self.assertRaises(domain.ConflictError):
                    operation()

    def test_ready_release_allows_non_blocking_gate_and_risk_metadata(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release = domain.transition_release(
            release,
            {"status": "validating"},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )[0]
        release = domain.transition_release(
            release,
            {"status": "ready"},
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )[0]

        release, gate, _ = domain.add_gate(
            release,
            {"name": "Post-release observation", "required": False},
            actor="local-operator",
            now="2026-07-16T08:03:00Z",
        )
        release, risk, _ = domain.add_risk(
            release,
            {"description": "Non-blocking follow-up", "severity": "low", "blocking": False},
            actor="local-operator",
            now="2026-07-16T08:04:00Z",
        )

        self.assertEqual(release["status"], "ready")
        self.assertFalse(gate["required"])
        self.assertFalse(risk["blocking"])

    def test_gate_transitions_only_allow_reset_to_pending_after_passed_or_waived(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, pending_gate, _ = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        release, passed_gate, _ = domain.update_gate(
            release,
            pending_gate["id"],
            {"status": "passed"},
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )
        release, pending_gate, _ = domain.add_gate(
            release,
            {"name": "Ops", "required": False},
            actor="local-operator",
            now="2026-07-16T08:03:00Z",
        )
        release, waived_gate, _ = domain.update_gate(
            release,
            pending_gate["id"],
            {"status": "waived", "waiver_reason": "Manual review"},
            actor="local-operator",
            now="2026-07-16T08:04:00Z",
        )

        with self.assertRaises(domain.ConflictError):
            domain.update_gate(
                release,
                passed_gate["id"],
                {"status": "failed"},
                actor="local-operator",
                now="2026-07-16T08:05:00Z",
            )

        with self.assertRaises(domain.ConflictError):
            domain.update_gate(
                release,
                waived_gate["id"],
                {"status": "passed"},
                actor="local-operator",
                now="2026-07-16T08:05:00Z",
            )

        updated, gate, _ = domain.update_gate(
            release,
            waived_gate["id"],
            {"status": "pending"},
            actor="local-operator",
            now="2026-07-16T08:06:00Z",
        )
        self.assertEqual(updated["gates"][1]["status"], "pending")
        self.assertEqual(gate["status"], "pending")

    def test_gate_waiver_requires_reason(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, _, _ = domain.add_gate(
            release,
            {"name": "Security review", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )

        with self.assertRaises(domain.ValidationError):
            domain.update_gate(
                release,
                release["gates"][0]["id"],
                {"status": "waived"},
                actor="local-operator",
                now="2026-07-16T08:02:00Z",
            )

    def test_accepted_risk_requires_reason(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, _, _ = domain.add_risk(
            release,
            {
                "description": "Capacity forecast incomplete",
                "severity": "medium",
                "blocking": False,
            },
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )

        with self.assertRaises(domain.ValidationError):
            domain.update_risk(
                release,
                release["risks"][0]["id"],
                {"status": "accepted"},
                actor="local-operator",
                now="2026-07-16T08:02:00Z",
            )

    def test_validate_release_rejects_mutated_ids_and_invalid_timestamps(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, gate, _ = domain.add_gate(
            release,
            {"name": "QA", "required": False},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        mutated = copy.deepcopy(release)
        mutated["gates"][0]["id"] = "not-a-uuid"

        with self.assertRaises(domain.ValidationError):
            domain.validate_release(mutated)

        release["created_at"] = "2026-07-16 08:00:00"
        with self.assertRaises(domain.ValidationError):
            domain.validate_release(release)

        self.assertRegex(gate["id"], re.compile(r"^[0-9a-f-]{36}$"))

    def test_validate_release_rejects_duplicate_nested_ids_and_backdated_update(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release["gates"] = [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "name": "Build",
                "required": True,
                "status": "pending",
                "waiver_reason": None,
            },
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "name": "Ops",
                "required": False,
                "status": "pending",
                "waiver_reason": None,
            },
        ]
        with self.assertRaises(domain.ValidationError):
            domain.validate_release(copy.deepcopy(release))

        release["gates"][1]["id"] = "22222222-2222-4222-8222-222222222222"
        release["updated_at"] = "2026-07-16T07:59:59Z"
        with self.assertRaises(domain.ValidationError):
            domain.validate_release(copy.deepcopy(release))

    def test_validate_state_rejects_duplicate_release_ids(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        state = {
            "schema_version": "delivery-ops-state/v1",
            "releases": [copy.deepcopy(release), copy.deepcopy(release)],
        }

        with self.assertRaises(domain.ValidationError):
            domain.validate_state(state)

    def test_release_status_transitions_are_limited(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )

        with self.assertRaises(domain.ConflictError):
            domain.transition_release(
                release,
                {"status": "released"},
                actor="local-operator",
                now="2026-07-16T08:01:00Z",
            )

    def test_create_assigns_initial_status_and_ignores_client_ids(self) -> None:
        supplied_id = "11111111-1111-4111-8111-111111111111"
        release, _ = domain.create_release(
            {"id": supplied_id, "title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, gate, _ = domain.add_gate(
            release,
            {"id": supplied_id, "name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        _, risk, _ = domain.add_risk(
            release,
            {
                "id": supplied_id,
                "description": "Rollback readiness",
                "severity": "high",
                "blocking": True,
            },
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )

        self.assertNotEqual(release["id"], supplied_id)
        self.assertNotEqual(gate["id"], supplied_id)
        self.assertNotEqual(risk["id"], supplied_id)
        self.assertEqual(gate["status"], "pending")
        self.assertIsNone(gate["waiver_reason"])
        self.assertEqual(risk["status"], "open")
        self.assertIsNone(risk["acceptance_reason"])

    def test_gate_and_risk_create_reject_lifecycle_fields(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )

        for field, value in (("status", "passed"), ("waiver_reason", "Override")):
            with self.subTest(entity="gate", field=field):
                with self.assertRaisesRegex(domain.ValidationError, "unknown gate fields"):
                    domain.add_gate(
                        release,
                        {"name": "Build", "required": True, field: value},
                        actor="local-operator",
                        now="2026-07-16T08:01:00Z",
                    )

        for field, value in (("status", "accepted"), ("acceptance_reason", "Approved")):
            with self.subTest(entity="risk", field=field):
                with self.assertRaisesRegex(domain.ValidationError, "unknown risk fields"):
                    domain.add_risk(
                        release,
                        {
                            "description": "Rollback readiness",
                            "severity": "high",
                            "blocking": True,
                            field: value,
                        },
                        actor="local-operator",
                        now="2026-07-16T08:01:00Z",
                    )

    def test_release_transition_matrix_is_exhaustive(self) -> None:
        statuses = sorted(domain.RELEASE_STATUSES)
        for source in statuses:
            for target in statuses:
                if source == target:
                    continue
                release, _ = domain.create_release(
                    {"title": "Canary", "version": "1.0.0"},
                    actor="local-operator",
                    now="2026-07-16T08:00:00Z",
                )
                release["status"] = source
                with self.subTest(source=source, target=target):
                    if target in domain.RELEASE_TRANSITIONS[source]:
                        updated, _ = domain.transition_release(
                            release,
                            {"status": target},
                            actor="local-operator",
                            now="2026-07-16T08:01:00Z",
                        )
                        self.assertEqual(updated["status"], target)
                    else:
                        with self.assertRaises(domain.ConflictError):
                            domain.transition_release(
                                release,
                                {"status": target},
                                actor="local-operator",
                                now="2026-07-16T08:01:00Z",
                            )

    def test_gate_transition_matrix_is_exhaustive(self) -> None:
        statuses = sorted(domain.GATE_STATUSES)
        for source in statuses:
            for target in statuses:
                if source == target:
                    continue
                release, _ = domain.create_release(
                    {"title": "Canary", "version": "1.0.0"},
                    actor="local-operator",
                    now="2026-07-16T08:00:00Z",
                )
                release, gate, _ = domain.add_gate(
                    release,
                    {"name": "Build", "required": True},
                    actor="local-operator",
                    now="2026-07-16T08:01:00Z",
                )
                release["gates"][0]["status"] = source
                release["gates"][0]["waiver_reason"] = "Approved" if source == "waived" else None
                changes = {"status": target}
                if target == "waived":
                    changes["waiver_reason"] = "Approved"
                with self.subTest(source=source, target=target):
                    if target in domain.GATE_TRANSITIONS[source]:
                        _, updated, _ = domain.update_gate(
                            release,
                            gate["id"],
                            changes,
                            actor="local-operator",
                            now="2026-07-16T08:02:00Z",
                        )
                        self.assertEqual(updated["status"], target)
                    else:
                        with self.assertRaises(domain.ConflictError):
                            domain.update_gate(
                                release,
                                gate["id"],
                                changes,
                                actor="local-operator",
                                now="2026-07-16T08:02:00Z",
                            )

    def test_risk_transition_matrix_is_exhaustive(self) -> None:
        statuses = sorted(domain.RISK_STATUSES)
        for source in statuses:
            for target in statuses:
                if source == target:
                    continue
                release, _ = domain.create_release(
                    {"title": "Canary", "version": "1.0.0"},
                    actor="local-operator",
                    now="2026-07-16T08:00:00Z",
                )
                release, risk, _ = domain.add_risk(
                    release,
                    {"description": "Rollback readiness", "severity": "high", "blocking": True},
                    actor="local-operator",
                    now="2026-07-16T08:01:00Z",
                )
                release["risks"][0]["status"] = source
                release["risks"][0]["acceptance_reason"] = "Approved" if source == "accepted" else None
                changes = {"status": target}
                if target == "accepted":
                    changes["acceptance_reason"] = "Approved"
                with self.subTest(source=source, target=target):
                    if target in domain.RISK_TRANSITIONS[source]:
                        _, updated, _ = domain.update_risk(
                            release,
                            risk["id"],
                            changes,
                            actor="local-operator",
                            now="2026-07-16T08:02:00Z",
                        )
                        self.assertEqual(updated["status"], target)
                    else:
                        with self.assertRaises(domain.ConflictError):
                            domain.update_risk(
                                release,
                                risk["id"],
                                changes,
                                actor="local-operator",
                                now="2026-07-16T08:02:00Z",
                            )

    def test_field_boundaries_unknown_fields_unique_ids_and_time_ordering(self) -> None:
        invalid_release_payloads = (
            ({"title": "", "version": "1.0.0"}, "title"),
            ({"title": "x" * 201, "version": "1.0.0"}, "title"),
            ({"title": "Canary", "version": ""}, "version"),
            ({"title": "Canary", "version": "x" * 81}, "version"),
            ({"title": "Canary", "version": "1.0.0", "unknown": True}, "unknown release fields"),
        )
        for payload, message in invalid_release_payloads:
            with self.subTest(entity="release", message=message):
                with self.assertRaisesRegex(domain.ValidationError, message):
                    domain.create_release(payload, actor="local-operator", now="2026-07-16T08:00:00Z")

        releases = [
            domain.create_release(
                {"title": f"Canary {index}", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T08:00:00Z",
            )[0]
            for index in range(2)
        ]
        self.assertEqual(len({release["id"] for release in releases}), 2)

        release = releases[0]
        invalid_gate_payloads = (
            ({"name": "", "required": True}, "name"),
            ({"name": "x" * 121, "required": True}, "name"),
            ({"name": "Build", "required": "yes"}, "required"),
            ({"name": "Build", "required": True, "unknown": True}, "unknown gate fields"),
        )
        for payload, message in invalid_gate_payloads:
            with self.subTest(entity="gate", message=message):
                with self.assertRaisesRegex(domain.ValidationError, message):
                    domain.add_gate(release, payload, actor="local-operator", now="2026-07-16T08:01:00Z")

        release, first_gate, _ = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        release, second_gate, _ = domain.add_gate(
            release,
            {"name": "Smoke", "required": True},
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )
        self.assertNotEqual(first_gate["id"], second_gate["id"])

        invalid_risk_payloads = (
            ({"description": "", "severity": "high", "blocking": True}, "description"),
            ({"description": "x" * 501, "severity": "high", "blocking": True}, "description"),
            ({"description": "Risk", "severity": "urgent", "blocking": True}, "severity"),
            ({"description": "Risk", "severity": "high", "blocking": "yes"}, "blocking"),
            ({"description": "Risk", "severity": "high", "blocking": True, "unknown": True}, "unknown risk fields"),
        )
        for payload, message in invalid_risk_payloads:
            with self.subTest(entity="risk", message=message):
                with self.assertRaisesRegex(domain.ValidationError, message):
                    domain.add_risk(release, payload, actor="local-operator", now="2026-07-16T08:01:00Z")

        release, first_risk, _ = domain.add_risk(
            release,
            {"description": "Rollback readiness", "severity": "high", "blocking": True},
            actor="local-operator",
            now="2026-07-16T08:03:00Z",
        )
        release, second_risk, _ = domain.add_risk(
            release,
            {"description": "Capacity review", "severity": "medium", "blocking": False},
            actor="local-operator",
            now="2026-07-16T08:04:00Z",
        )
        self.assertNotEqual(first_risk["id"], second_risk["id"])

        update_cases = (
            (lambda: domain.transition_release(release, {}, actor="local-operator"), "changes"),
            (lambda: domain.transition_release(release, {"title": "x" * 201}, actor="local-operator"), "title"),
            (lambda: domain.transition_release(release, {"unknown": True}, actor="local-operator"), "unknown release fields"),
            (lambda: domain.update_gate(release, first_gate["id"], {}, actor="local-operator"), "changes"),
            (lambda: domain.update_gate(release, first_gate["id"], {"name": "x" * 121}, actor="local-operator"), "name"),
            (lambda: domain.update_gate(release, first_gate["id"], {"unknown": True}, actor="local-operator"), "unknown gate fields"),
            (lambda: domain.update_risk(release, first_risk["id"], {}, actor="local-operator"), "changes"),
            (lambda: domain.update_risk(release, first_risk["id"], {"description": "x" * 501}, actor="local-operator"), "description"),
            (lambda: domain.update_risk(release, first_risk["id"], {"unknown": True}, actor="local-operator"), "unknown risk fields"),
        )
        for operation, message in update_cases:
            with self.subTest(update=message):
                with self.assertRaisesRegex(domain.ValidationError, message):
                    operation()

        with self.assertRaisesRegex(domain.ValidationError, "updated_at"):
            domain.transition_release(
                release,
                {"status": "validating"},
                actor="local-operator",
                now="2026-07-16T07:59:59Z",
            )
        with self.assertRaisesRegex(domain.ValidationError, "RFC3339 UTC"):
            domain.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T08:00:00+00:00",
            )
        with self.assertRaisesRegex(domain.ValidationError, "updated_at"):
            domain.add_gate(
                releases[1],
                {"name": "Build", "required": True},
                actor="local-operator",
                now="2026-07-16T07:59:59Z",
            )
        with self.assertRaisesRegex(domain.ValidationError, "updated_at"):
            domain.add_risk(
                releases[1],
                {"description": "Risk", "severity": "low", "blocking": False},
                actor="local-operator",
                now="2026-07-16T07:59:59Z",
            )

    def test_mutations_reject_timestamps_earlier_than_current_updated_at(self) -> None:
        release, _ = domain.create_release(
            {"title": "Canary", "version": "1.0.0"},
            actor="local-operator",
            now="2026-07-16T08:00:00Z",
        )
        release, gate, _ = domain.add_gate(
            release,
            {"name": "Build", "required": True},
            actor="local-operator",
            now="2026-07-16T08:01:00Z",
        )
        release, risk, _ = domain.add_risk(
            release,
            {"description": "Rollback readiness", "severity": "high", "blocking": True},
            actor="local-operator",
            now="2026-07-16T08:02:00Z",
        )

        operations = (
            lambda: domain.transition_release(
                release,
                {"title": "Backdated"},
                actor="local-operator",
                now="2026-07-16T08:01:59Z",
            ),
            lambda: domain.add_gate(
                release,
                {"name": "Smoke", "required": True},
                actor="local-operator",
                now="2026-07-16T08:01:59Z",
            ),
            lambda: domain.update_gate(
                release,
                gate["id"],
                {"status": "passed"},
                actor="local-operator",
                now="2026-07-16T08:01:59Z",
            ),
            lambda: domain.add_risk(
                release,
                {"description": "Capacity", "severity": "medium", "blocking": False},
                actor="local-operator",
                now="2026-07-16T08:01:59Z",
            ),
            lambda: domain.update_risk(
                release,
                risk["id"],
                {"status": "mitigated"},
                actor="local-operator",
                now="2026-07-16T08:01:59Z",
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(domain.ValidationError, "updated_at"):
                    operation()


if __name__ == "__main__":
    unittest.main()
