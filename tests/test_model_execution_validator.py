from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_model_execution.py"


class ModelExecutionValidatorTests(unittest.TestCase):
    def load_validator(self) -> types.ModuleType:
        self.assertTrue(VALIDATOR_PATH.exists(), f"missing validator: {VALIDATOR_PATH}")
        spec = importlib.util.spec_from_file_location("validate_model_execution", VALIDATOR_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def write_file(self, repo_root: Path, relative_path: str, content: str) -> str:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def make_record(self, repo_root: Path, role: str) -> tuple[Path, dict[str, object]]:
        assignments = {
            "deepseek-planner": ("deepseek", "deepseek-anthropic-api"),
            "deepseek-reviewer": ("deepseek", "deepseek-anthropic-api"),
            "deepseek-final": ("deepseek", "deepseek-anthropic-api"),
            "codex-worker": ("openai", "Codex Desktop"),
        }
        provider, interface = assignments[role]
        prompt_path = f"evidence/prompts/{role}.txt"
        artifact_path = f"evidence/artifacts/{role}.md"
        transcript_path = f"evidence/transcripts/{role}.log"
        stage = {"deepseek-planner": "s1", "deepseek-reviewer": "s8", "deepseek-final": "s10"}.get(role)
        run_id = f"deepseek-{stage}-20260804-922c71f33672" if stage else "019f6aa2-aa74-73d2-9f99-c7aad51ac2d2"
        model = "deepseek-v4-pro" if stage else "gpt-5.5"
        record: dict[str, object] = {
            "schema_version": "ai-delivery-model-execution/v1",
            "role": role,
            "provider": provider,
            "model": model,
            "interface": interface,
            "run_id": run_id,
            "started_at": "2026-07-16T08:00:00.430Z",
            "completed_at": "2026-07-16T08:01:00.569Z",
            "exit_code": 0,
            "placeholder": False,
            "prompt_path": prompt_path,
            "prompt_sha256": self.write_file(repo_root, prompt_path, f"prompt for {role}\n"),
            "artifact_path": artifact_path,
            "artifact_sha256": self.write_file(repo_root, artifact_path, f"artifact for {role}\n"),
            "transcript_path": transcript_path,
        }
        transcript: dict[str, object] = {
            "schema_version": "ai-delivery-model-transcript/v1",
            "role": role,
            "provider": provider,
            "model": model,
        }
        if stage:
            source_log_path = f"evidence/source-logs/{role}.jsonl"
            source_log_sha256 = self.write_file(
                repo_root,
                source_log_path,
                json.dumps({"provider": "deepseek", "model": model, "run_id": run_id}) + "\n",
            )
            record["source_log_path"] = source_log_path
            record["source_log_sha256"] = source_log_sha256
            transcript.update(
                {
                    "session_id": run_id,
                    "source_log_path": source_log_path,
                    "source_log_sha256": source_log_sha256,
                    "result": "DeepSeek produced a governed structured result.",
                    "endpoint": "https://api.deepseek.com/anthropic/v1/messages",
                    "usage": {"input_tokens": 3, "output_tokens": 5},
                    "cost_usd": 0.001,
                }
            )
        else:
            transcript.update(
                {
                    "interface": interface,
                    "run_id": run_id,
                    "started_at": record["started_at"],
                    "completed_at": record["completed_at"],
                    "exit_code": 0,
                    "source_audit_event_count": 3,
                    "source_audit_sha256": "a" * 64,
                    "source_audit_retained_locally": True,
                    "thread_id": run_id,
                }
            )
        record["transcript_sha256"] = self.write_file(
            repo_root,
            transcript_path,
            json.dumps(transcript, sort_keys=True),
        )
        record_path = repo_root / "evidence" / "models" / f"{role}.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        return record_path, record

    def test_valid_complete_role_set_and_cli_discovery(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            record_paths = [self.make_record(repo_root, role)[0] for role in validator.ROLE_ASSIGNMENTS]

            self.assertEqual(validator.validate_records(repo_root, record_paths, require_all_roles=True), [])
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--discover",
                    "--require-all",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("validated_model_execution_records=4", result.stdout)

    def test_invalid_records_report_each_contract_violation(self) -> None:
        validator = self.load_validator()
        mutations = {
            "provider": lambda record: record.update(provider="openai"),
            "path": lambda record: record.update(prompt_path="../outside.txt"),
            "hash": lambda record: record.update(artifact_sha256="0" * 64),
            "time": lambda record: record.update(completed_at="2026-07-16T07:59:59Z"),
            "missing": lambda record: record.pop("transcript_sha256"),
            "placeholder": lambda record: record.update(placeholder=True),
        }
        expected_fragments = {
            "provider": "provider",
            "path": "escapes repo root",
            "hash": "artifact_sha256 mismatch",
            "time": "completed_at",
            "missing": "missing fields",
            "placeholder": "placeholder must be false",
        }

        for case, mutate in mutations.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp_dir:
                repo_root = Path(tmp_dir)
                record_path, record = self.make_record(repo_root, "deepseek-planner")
                mutate(record)
                record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")

                failures = validator.validate_records(repo_root, [record_path], require_all_roles=False)
                self.assertTrue(any(expected_fragments[case] in failure for failure in failures), failures)

    def test_nonzero_exit_code_is_rejected(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            record_path, record = self.make_record(repo_root, "deepseek-reviewer")
            record["exit_code"] = 17
            record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")

            failures = validator.validate_records(repo_root, [record_path], require_all_roles=False)

            self.assertTrue(any("exit_code must be zero" in failure for failure in failures), failures)

    def test_unstructured_transcript_is_rejected_even_when_hash_matches(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            record_path, record = self.make_record(repo_root, "codex-worker")
            record["transcript_sha256"] = self.write_file(
                repo_root,
                str(record["transcript_path"]),
                "handwritten transcript with no provider execution metadata\n",
            )
            record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")

            failures = validator.validate_records(repo_root, [record_path], require_all_roles=False)

            self.assertTrue(any("transcript must be valid structured JSON" in failure for failure in failures), failures)

    def test_empty_discovery_is_optional_until_evidence_is_finished(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            self.assertEqual(validator.discover_record_paths(repo_root), [])
            self.assertEqual(validator.validate_records(repo_root, [], require_all_roles=False), [])
            failures = validator.validate_records(repo_root, [], require_all_roles=True)
            self.assertTrue(any("missing roles" in failure for failure in failures), failures)

    def test_discovery_ignores_non_record_sidecar_json(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            sidecar = repo_root / "evidence" / "release" / "model-executions" / "deepseek-planner-transcript.json"
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text("{}", encoding="utf-8")
            source_audit = sidecar.with_name("deepseek-planner-source-audit.json")
            source_audit.write_text("{}", encoding="utf-8")

            self.assertNotIn(sidecar.resolve(), validator.discover_record_paths(repo_root))
            self.assertNotIn(source_audit.resolve(), validator.discover_record_paths(repo_root))


if __name__ == "__main__":
    unittest.main()
