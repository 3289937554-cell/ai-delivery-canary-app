from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ElementIndex(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.by_id: dict[str, tuple[str, dict[str, str | None]]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.by_id[element_id] = (tag, attributes)


class WebContractTests(unittest.TestCase):
    def test_app_uses_session_storage_and_retains_pending_mutations(self) -> None:
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("sessionStorage", script)
        self.assertNotIn("localStorage", script)
        self.assertIn("pendingMutation", script)
        self.assertIn("retryPendingMutation", script)

    def test_cross_release_audit_mode_is_wired_to_api_audit(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="audit-scope"', html)
        self.assertIn("All releases", html)
        self.assertIn('"/api/audit"', script)
        self.assertIn("auditMode", script)

    def test_status_controls_are_restricted_to_allowed_transitions(self) -> None:
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("allowedReleaseStatuses", script)
        self.assertIn("allowedGateStatuses", script)
        self.assertIn("allowedRiskStatuses", script)
        self.assertIn("releaseCanBecomeReady", script)

    def test_release_surface_is_semantic_and_responsive_at_640_pixels(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        parser = ElementIndex()
        parser.feed(html)

        self.assertEqual(parser.by_id["release-table"][0], "table")
        self.assertEqual(parser.by_id["release-table-body"][0], "tbody")
        for heading in ("Title", "Version", "Status", "Gates", "Open risks"):
            self.assertIn(f">{heading}<", html)
        self.assertIn("@media (min-width: 640px)", styles)
        self.assertIn("grid-template-columns: minmax(0, 2fr) minmax(0, 3fr)", styles)
        self.assertIn("overflow-x: hidden", styles)
        self.assertIn("release.gates", script)
        self.assertIn("release.risks", script)
        self.assertIn('risk.status === "open"', script)

    def test_create_forms_do_not_offer_lifecycle_state_or_reason_fields(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        parser = ElementIndex()
        parser.feed(html)

        for removed_id in ("gate-status", "gate-waiver-reason", "risk-status", "risk-acceptance-reason"):
            self.assertNotIn(removed_id, parser.by_id)
        self.assertNotIn("form.elements.waiver_reason", script[script.index("async function handleCreateGate") : script.index("async function handleCreateRisk")])
        self.assertNotIn("form.elements.acceptance_reason", script[script.index("async function handleCreateRisk") : script.index("async function handleGateAction")])

    def test_audit_and_form_errors_render_required_operator_context(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("prior_status", script)
        self.assertIn("new_status", script)
        self.assertIn("\\u2192", script)
        self.assertIn("setFieldError", script)
        self.assertIn("focusFirstInvalidField", script)
        self.assertIn('class="field-error"', html)
        self.assertIn(".field-error", styles)

    def test_runbook_documents_sanitized_structured_logging(self) -> None:
        runbook = (ROOT / "docs" / "operations-runbook.md").read_text(encoding="utf-8").lower()

        self.assertIn("structured stderr", runbook)
        self.assertIn("query strings", runbook)
        self.assertIn("request bodies", runbook)

    def test_build_script_emits_compile_output_and_asset_manifest(self) -> None:
        script = (ROOT / "scripts" / "build.sh").read_text(encoding="utf-8")

        self.assertIn("compileall", script)
        self.assertIn(".ai-delivery/build", script)
        self.assertIn("sha256", script)
        self.assertIn("asset-manifest", script)

    def test_runbook_covers_required_operations_topics(self) -> None:
        runbook = (ROOT / "docs" / "operations-runbook.md").read_text(encoding="utf-8").lower()

        for phrase in (
            "token rotation",
            "backup",
            "restore",
            "rollback",
            "1 mib",
            "additive-only migration",
            "health",
            "incident recovery",
        ):
            self.assertIn(phrase, runbook)


if __name__ == "__main__":
    unittest.main()
