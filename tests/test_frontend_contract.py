from __future__ import annotations

import re
import json
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.password_inputs = 0
        self.forms: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(str(attributes["id"]))
        if tag == "input" and attributes.get("type", "").lower() == "password":
            self.password_inputs += 1
        if tag == "form":
            self.forms.append(attributes.get("id") or "")


class FrontendContractTests(unittest.TestCase):
    def test_only_approved_pages_are_present(self) -> None:
        html_pages = {path.name for path in WEB_ROOT.glob("*.html")}
        self.assertEqual(html_pages, {"index.html", "methodology.html"})

    def test_main_page_contains_required_unified_workflow_controls(self) -> None:
        parser = IdCollector()
        parser.feed((WEB_ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "Duplicate HTML IDs")
        self.assertEqual(parser.password_inputs, 0)
        required_ids = {
            "map",
            "search-form",
            "coordinate-form",
            "latitude",
            "longitude",
            "hazard-layer-controls",
            "map-legend",
            "run-assessment",
            "results-content",
            "preview-report",
            "download-report",
            "history-list",
        }
        self.assertTrue(required_ids.issubset(parser.ids))

    def test_frontend_calls_only_approved_api_groups(self) -> None:
        scripts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (WEB_ROOT / "app.js", WEB_ROOT / "methodology.js")
        )
        required_paths = {
            "/boundary",
            "/barangays",
            "/ulap/status",
            "/ulap/services",
            "/hazards/at-location",
            "/location/search",
            "/location/identify",
            "/assessments",
            "/incidents/nearby",
            "/clup-references/by-location",
            "/methodology",
            "/data-sources",
        }
        self.assertTrue(all(path in scripts for path in required_paths))
        for forbidden in (
            "/users",
            "/roles",
            "/permissions",
            "/admin",
            "/staff",
            "/audit",
            "/activity",
            "/sessions",
            "/approvals",
            "/datasets/upload",
            "/datasets/publish",
            "/fuzzy-models/editor",
            "/auth/register",
            "/auth/login",
        ):
            self.assertNotIn(forbidden, scripts)

    def test_disclaimer_and_missing_data_rule_are_visible(self) -> None:
        page_text = " ".join(
            path.read_text(encoding="utf-8")
            for path in (
                WEB_ROOT / "index.html",
                WEB_ROOT / "methodology.html",
                WEB_ROOT / "app.js",
            )
        )
        self.assertRegex(
            page_text,
            re.compile(r"not an official hazard certification", re.IGNORECASE),
        )
        self.assertRegex(
            page_text,
            re.compile(
                r"missing (?:information|data).{0,80}(?:not|never).{0,30}low",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            page_text,
            re.compile(r"(?:demonstration|unvalidated).{0,30}model", re.IGNORECASE),
        )

    def test_fallback_and_methodology_use_canonical_disclaimer(self) -> None:
        disclaimer = json.loads(
            (PROJECT_ROOT / "config" / "fuzzy_model.json").read_text(
                encoding="utf-8"
            )
        )["disclaimer"]
        data_disclaimer = json.loads(
            (PROJECT_ROOT / "config" / "data_sources.json").read_text(
                encoding="utf-8"
            )
        )["required_disclaimer"]
        self.assertEqual(data_disclaimer, disclaimer)
        self.assertIn(
            f'const DISCLAIMER = "{disclaimer}";',
            (WEB_ROOT / "app.js").read_text(encoding="utf-8"),
        )
        self.assertIn(
            disclaimer,
            (WEB_ROOT / "methodology.html").read_text(encoding="utf-8"),
        )

    def test_javascript_has_valid_syntax_when_node_is_available(self) -> None:
        try:
            for filename in ("app.js", "methodology.js"):
                completed = subprocess.run(
                    ["node", "--check", str(WEB_ROOT / filename)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=completed.stdout + completed.stderr,
                )
        except FileNotFoundError:
            self.skipTest("Node.js is not installed; browser syntax check skipped.")


if __name__ == "__main__":
    unittest.main()
