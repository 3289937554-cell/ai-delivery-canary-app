from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_evidence_manifest.py"


class EvidenceManifestValidatorTests(unittest.TestCase):
    def load_validator(self) -> types.ModuleType:
        spec = importlib.util.spec_from_file_location("validate_evidence_manifest", VALIDATOR_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_boolean_test_counts_are_rejected(self) -> None:
        validator = self.load_validator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_path = Path(tmp_dir) / "test-summary.json"
            summary_path.write_text(
                json.dumps({"status": "passed", "failed": False, "passed": True, "total": True}),
                encoding="utf-8",
            )
            result = validator.ValidationResult()

            validator.validate_test_summary(summary_path, result)

            self.assertTrue(any("must be an integer, not a boolean" in failure for failure in result.failures), result.failures)


if __name__ == "__main__":
    unittest.main()
