from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ToolingContractTests(unittest.TestCase):
    def test_dev_tools_are_pinned_and_real_adapters_invoke_them(self) -> None:
        requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
        lint_script = (ROOT / "scripts" / "lint.sh").read_text(encoding="utf-8")
        typecheck_script = (ROOT / "scripts" / "typecheck.sh").read_text(encoding="utf-8")
        configuration = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertEqual(requirements, ["mypy==1.18.2", "ruff==0.15.12"])
        self.assertIn("python3 -m ruff check", lint_script)
        self.assertIn("python3 -m mypy", typecheck_script)
        for rule_family in ('"E4"', '"E7"', '"E9"', '"F"', '"I"', '"UP"', '"B"'):
            self.assertIn(rule_family, configuration)
        self.assertIn("strict = true", configuration)

    def test_ci_installs_pinned_tools_before_lint_and_typecheck(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ai-delivery-ci.yml").read_text(encoding="utf-8")

        self.assertGreaterEqual(
            workflow.count("python3 -m pip install --requirement requirements-dev.txt"),
            2,
        )

    def test_ci_actions_are_pinned_to_immutable_commits(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ai-delivery-ci.yml").read_text(encoding="utf-8")
        action_refs = re.findall(r"^[ ]*- uses: (actions/[^@\s]+)@([^\s#]+)", workflow, flags=re.MULTILINE)

        self.assertTrue(action_refs)
        for action, revision in action_refs:
            with self.subTest(action=action):
                self.assertRegex(revision, r"^[0-9a-f]{40}$")

    def test_runtime_imports_remain_standard_library_only(self) -> None:
        unexpected: list[str] = []
        for path in sorted((ROOT / "src").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".", 1)[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    roots = [node.module.split(".", 1)[0]]
                else:
                    continue
                for root in roots:
                    if root not in sys.stdlib_module_names and root not in {"delivery_ops", "aid_canary_app"}:
                        unexpected.append(f"{path.relative_to(ROOT)}: {root}")

        self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
