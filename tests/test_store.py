from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delivery_ops import store  # type: ignore[import-not-found]


class StoreTests(unittest.TestCase):
    def test_list_releases_uses_read_lock_for_snapshot_reads(self) -> None:
        class BlockingLock:
            def __init__(self) -> None:
                self.entered = threading.Event()
                self.release = threading.Event()

            def __enter__(self) -> BlockingLock:
                self.entered.set()
                self.release.wait(timeout=2)
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp_dir:
            persisted = store.DeliveryStore(Path(tmp_dir))
            persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            blocking_lock = BlockingLock()
            persisted._lock = blocking_lock  # type: ignore[assignment]

            result: list[dict[str, object]] = []
            thread = threading.Thread(target=lambda: result.extend(persisted.list_releases()))
            thread.start()

            self.assertTrue(blocking_lock.entered.wait(timeout=1))
            self.assertTrue(thread.is_alive(), "reader should remain blocked until the read lock is released")
            blocking_lock.release.set()
            thread.join(timeout=2)

            self.assertEqual(len(result), 1)

    def test_missing_state_loads_empty_and_removes_leftover_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            tmp_state = data_dir / "state.json.tmp"
            tmp_state.write_text("stale", encoding="utf-8")

            persisted = store.DeliveryStore(data_dir)

            self.assertEqual(persisted.list_releases(), [])
            self.assertFalse(tmp_state.exists())

    def test_malformed_state_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            (data_dir / "state.json").write_text("{not-json", encoding="utf-8")

            with self.assertRaises(store.StoreError) as context:
                store.DeliveryStore(data_dir)

            self.assertIn("state.json", str(context.exception))

    def test_mutations_persist_state_and_audit_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            first = store.DeliveryStore(data_dir)

            release = first.create_release(
                {"title": "Operator console rollout", "version": "2026.07.16"},
                actor="local-operator",
                now="2026-07-16T09:00:00Z",
            )
            gate = first.add_gate(
                release["id"],
                {"name": "Build", "required": True},
                actor="local-operator",
                now="2026-07-16T09:01:00Z",
            )
            risk = first.add_risk(
                release["id"],
                {
                    "description": "Rollback checklist pending sign-off",
                    "severity": "high",
                    "blocking": True,
                },
                actor="local-operator",
                now="2026-07-16T09:02:00Z",
            )

            second = store.DeliveryStore(data_dir)
            loaded = second.get_release(release["id"])
            state_payload = json.loads((data_dir / "state.json").read_text(encoding="utf-8"))

            self.assertEqual(loaded["title"], "Operator console rollout")
            self.assertEqual(loaded["gates"][0]["id"], gate["id"])
            self.assertEqual(loaded["risks"][0]["id"], risk["id"])
            self.assertEqual(len(second.get_release_audit(release["id"])), 3)
            self.assertEqual(len(second.get_audit()), 3)
            self.assertEqual(state_payload["schema_version"], "delivery-ops-state/v1")
            self.assertTrue((data_dir / "state.json").exists())
            self.assertTrue((data_dir / "audit.jsonl").exists())

    def test_each_accepted_mutation_appends_exactly_one_audit_event_and_reads_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            persisted = store.DeliveryStore(Path(tmp_dir))

            release = persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            persisted.update_release(
                release["id"],
                {"status": "validating"},
                actor="local-operator",
                now="2026-07-16T10:01:00Z",
            )

            audit = persisted.get_release_audit(release["id"])
            self.assertEqual(len(audit), 2)
            self.assertNotEqual(audit[0]["id"], audit[1]["id"])
            self.assertEqual(audit[0]["action"], "release.updated")
            self.assertEqual(audit[1]["action"], "release.created")
            self.assertEqual(persisted.get_audit()[0]["action"], "release.updated")

    def test_store_accepts_exact_state_schema_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            release = {
                "id": "11111111-1111-4111-8111-111111111111",
                "title": "Canary",
                "version": "1.0.0",
                "status": "planned",
                "created_at": "2026-07-16T10:00:00Z",
                "updated_at": "2026-07-16T10:00:00Z",
                "gates": [],
                "risks": [],
            }
            (data_dir / "state.json").write_text(
                json.dumps({"schema_version": "delivery-ops-state/v1", "releases": [release]}),
                encoding="utf-8",
            )

            persisted = store.DeliveryStore(data_dir)
            self.assertEqual(persisted.get_release(release["id"])["title"], "Canary")

    def test_state_and_audit_writes_flush_and_replace_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)

            with mock.patch("delivery_ops.store.os.replace", wraps=store.os.replace) as replace_mock:
                with mock.patch("delivery_ops.store.os.fsync", wraps=store.os.fsync) as fsync_mock:
                    persisted.create_release(
                        {"title": "Canary", "version": "1.0.0"},
                        actor="local-operator",
                        now="2026-07-16T10:00:00Z",
                    )

            self.assertGreaterEqual(replace_mock.call_count, 2)
            self.assertGreaterEqual(fsync_mock.call_count, 3)
            state = json.loads((data_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["releases"]), 1)
            self.assertFalse((data_dir / "state.json.tmp").exists())
            self.assertFalse((data_dir / "transaction.json").exists())

    def test_journal_staging_failure_leaves_state_and_audit_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)
            original_open = Path.open

            def fail_journal_open(path: Path, *args, **kwargs):
                if path.name == "transaction.json.tmp":
                    raise OSError("injected journal staging failure")
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", autospec=True, side_effect=fail_journal_open):
                with self.assertRaisesRegex(OSError, "journal staging"):
                    persisted.create_release(
                        {"title": "Canary", "version": "1.0.0"},
                        actor="local-operator",
                        now="2026-07-16T10:00:00Z",
                    )

            self.assertEqual(persisted.list_releases(), [])
            self.assertEqual(persisted.get_audit(), [])
            self.assertFalse((data_dir / "state.json").exists())
            self.assertFalse((data_dir / "transaction.json").exists())

    def test_state_replace_failure_rolls_back_memory_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)
            release = persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            audit_prefix = (data_dir / "audit.jsonl").read_bytes()
            real_replace = os.replace
            failed = False

            def fail_state_replace(source: str | bytes | os.PathLike[str] | os.PathLike[bytes], target: str | bytes | os.PathLike[str] | os.PathLike[bytes]) -> None:
                nonlocal failed
                if Path(source).name == "state.json.tmp" and not failed:
                    failed = True
                    raise OSError("injected state replace failure")
                real_replace(source, target)

            with mock.patch("delivery_ops.store.os.replace", side_effect=fail_state_replace):
                with self.assertRaisesRegex(OSError, "state replace"):
                    persisted.update_release(
                        release["id"],
                        {"status": "validating"},
                        actor="local-operator",
                        now="2026-07-16T10:01:00Z",
                    )

            self.assertEqual(persisted.get_release(release["id"])["status"], "planned")
            self.assertEqual((data_dir / "audit.jsonl").read_bytes(), audit_prefix)
            restarted = store.DeliveryStore(data_dir)
            self.assertEqual(restarted.get_release(release["id"])["status"], "planned")
            self.assertEqual(len(restarted.get_audit()), 1)

    def test_partial_audit_append_rolls_back_and_preserves_prior_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)
            release = persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            audit_prefix = (data_dir / "audit.jsonl").read_bytes()

            def append_partial(_event: dict[str, object]) -> None:
                with (data_dir / "audit.jsonl").open("ab") as handle:
                    handle.write(b'{"id":"interrupted')
                    handle.flush()
                    os.fsync(handle.fileno())
                raise OSError("injected audit append failure")

            with mock.patch.object(persisted, "_append_audit", side_effect=append_partial):
                with self.assertRaisesRegex(OSError, "audit append"):
                    persisted.update_release(
                        release["id"],
                        {"status": "validating"},
                        actor="local-operator",
                        now="2026-07-16T10:01:00Z",
                    )

            self.assertEqual((data_dir / "audit.jsonl").read_bytes(), audit_prefix)
            self.assertEqual(persisted.get_release(release["id"])["status"], "planned")
            restarted = store.DeliveryStore(data_dir)
            self.assertEqual(restarted.get_release(release["id"])["status"], "planned")
            self.assertEqual(len(restarted.get_audit()), 1)

    def test_durable_audit_append_error_rolls_forward_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)
            release = persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            append_audit = persisted._append_audit

            def append_then_fail(event: dict[str, object]) -> None:
                append_audit(event)
                raise OSError("injected post-append failure")

            with mock.patch.object(persisted, "_append_audit", side_effect=append_then_fail):
                with self.assertRaisesRegex(OSError, "post-append"):
                    persisted.update_release(
                        release["id"],
                        {"status": "validating"},
                        actor="local-operator",
                        now="2026-07-16T10:01:00Z",
                    )

            self.assertEqual(persisted.get_release(release["id"])["status"], "validating")
            self.assertEqual(len(persisted.get_audit()), 2)
            restarted = store.DeliveryStore(data_dir)
            self.assertEqual(restarted.get_release(release["id"])["status"], "validating")
            self.assertEqual(len(restarted.get_audit()), 2)
            self.assertEqual(len({event["id"] for event in restarted.get_audit()}), 2)

    def test_restart_recovers_journal_after_interrupted_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)
            release = persisted.create_release(
                {"title": "Canary", "version": "1.0.0"},
                actor="local-operator",
                now="2026-07-16T10:00:00Z",
            )
            audit_prefix = (data_dir / "audit.jsonl").read_bytes()

            with mock.patch.object(persisted, "_append_audit", side_effect=OSError("injected append failure")):
                with mock.patch.object(
                    store.DeliveryStore,
                    "_recover_transaction",
                    side_effect=store.StoreError("simulated process stop"),
                    create=True,
                ):
                    with self.assertRaises(OSError):
                        persisted.update_release(
                            release["id"],
                            {"status": "validating"},
                            actor="local-operator",
                            now="2026-07-16T10:01:00Z",
                        )

            self.assertTrue((data_dir / "transaction.json").exists())
            restarted = store.DeliveryStore(data_dir)
            self.assertEqual(restarted.get_release(release["id"])["status"], "planned")
            self.assertEqual((data_dir / "audit.jsonl").read_bytes(), audit_prefix)
            self.assertFalse((data_dir / "transaction.json").exists())

    def test_restart_rolls_forward_durable_event_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            persisted = store.DeliveryStore(data_dir)

            with mock.patch.object(
                store.DeliveryStore,
                "_clear_journal",
                side_effect=OSError("simulated stop before journal cleanup"),
                create=True,
            ):
                release = persisted.create_release(
                    {"title": "Canary", "version": "1.0.0"},
                    actor="local-operator",
                    now="2026-07-16T10:00:00Z",
                )

            self.assertTrue((data_dir / "transaction.json").exists())
            restarted = store.DeliveryStore(data_dir)
            self.assertEqual(restarted.get_release(release["id"])["title"], "Canary")
            self.assertEqual(len(restarted.get_audit()), 1)
            self.assertFalse((data_dir / "transaction.json").exists())

    def test_two_store_instances_serialize_and_reload_each_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir)
            first = store.DeliveryStore(data_dir)
            second = store.DeliveryStore(data_dir)
            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def create_release(persisted: store.DeliveryStore, title: str) -> None:
                try:
                    barrier.wait(timeout=2)
                    persisted.create_release(
                        {"title": title, "version": "1.0.0"},
                        actor="local-operator",
                        now="2026-07-16T10:00:00Z",
                    )
                except BaseException as exc:
                    errors.append(exc)

            threads = [
                threading.Thread(target=create_release, args=(first, "Canary A")),
                threading.Thread(target=create_release, args=(second, "Canary B")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(errors, [])
            self.assertEqual({item["title"] for item in first.list_releases()}, {"Canary A", "Canary B"})
            self.assertEqual({item["title"] for item in second.list_releases()}, {"Canary A", "Canary B"})
            self.assertEqual(len(store.DeliveryStore(data_dir).get_audit()), 2)


if __name__ == "__main__":
    unittest.main()
