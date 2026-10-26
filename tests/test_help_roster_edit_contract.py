"""Documentation contracts, not proof of agent behavior or consent enforcement."""

from pathlib import Path

import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/luucycle"


class ReadmeContractTests(unittest.TestCase):
    def test_readme_is_a_short_english_entrypoint_with_bounded_free_plan_claims(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Several AI providers offer free plans. Why let them go unused?", readme)
        self.assertLess(len(readme.splitlines()), 65)
        self.assertLess(len(readme.encode()), 4000)
        for removed in ("## Development", "## Structure", "scripts/doctor.py", "## Local return-contract checks"):
            self.assertNotIn(removed, readme)
        for required in ("Orca", "approval", "quotas", "cost", "npx skills add luucas7/luucycle", "/luucycle help", "/luucycle roster edit", "/luucycle init"):
            self.assertIn(required, readme)
        self.assertIn("[HELP.md](skills/luucycle/HELP.md)", readme)
        self.assertNotIn("alias: `/luucycle help`", readme)


class RosterEditContractTests(unittest.TestCase):
    def test_edit_is_routed_and_recommended_for_existing_entries(self):
        router = (SKILL / "SKILL.md").read_text()
        self.assertIn("`/luucycle roster edit [agent\\|cli]`", router)
        self.assertIn("[ROSTER-EDIT.md](ROSTER-EDIT.md)", router)
        for name in ("HELP.md", "DOCTOR-REPORT.md", "ROSTER-LIST.md", "ROSTER-ADD.md", "ROSTER-FORMAT.md"):
            self.assertIn("/luucycle roster edit", (SKILL / name).read_text(), name)

    def test_edit_limits_scope_and_requires_dated_comparative_evidence(self):
        branch = (SKILL / "ROSTER-EDIT.md").read_text()
        for required in (
            "existing Agent IDs only", "including disabled entries", "exact Agent ID",
            "CLI product", "Command", "ambiguous", "no matches", "without creating",
            "first-party documentation", "--help", "version", "catalog", "YYYY-MM-DD",
            "quota", "reset", "subscription", "UNKNOWN", "credentials", "auth stores",
            "every canonical role", "before/after", "comparative", "judgment", "permissions",
            "New models", "/luucycle roster add", "fresh consent immediately before each",
        ):
            with self.subTest(required=required):
                self.assertIn(required, branch)

    def test_edit_uses_existing_guarded_mechanics_after_exact_approval(self):
        branch = (SKILL / "ROSTER-EDIT.md").read_text()
        for required in (
            "scripts/roster.py\" list --json", "scripts/roster.py\" plan --json",
            "scripts/roster.py\" apply --json", "scripts/roster.py\" check --json",
            "base_hashes", "expected_hashes", "previews", "complete replacement role lists",
            "out-of-scope", "explicit approval of this exact plan", "before any roster write",
            "Refusal or absent approval leaves", "rebuild", "approval again", "hash guard",
            "WARNINGS.md", "reread", "DOCTOR.md", "no changes",
        ):
            with self.subTest(required=required):
                self.assertIn(required, branch)
        self.assertLess(branch.index("explicit approval of this exact plan"), branch.index('scripts/roster.py" apply'))
        rules = (SKILL / "RULES.md").read_text()
        self.assertIn("`roster add` and `roster edit`", rules)


class HelpContractTests(unittest.TestCase):
    def test_help_is_canonical_and_ask_lucas_is_a_thin_compatibility_pointer(self):
        router = (SKILL / "SKILL.md").read_text()
        help_rows = [line for line in router.splitlines() if "Answer questions about luucycle" in line]
        self.assertEqual(len(help_rows), 1)
        self.assertIn("`/luucycle help`", help_rows[0])
        self.assertLess(help_rows[0].index("/luucycle help"), help_rows[0].index("/luucycle ask-lucas"))
        self.assertIn("[HELP.md](HELP.md)", help_rows[0])
        self.assertNotIn("(ASK-LUCAS.md)", router)
        compatibility = (SKILL / "ASK-LUCAS.md").read_text()
        self.assertIn("[HELP.md](HELP.md)", compatibility)
        self.assertLessEqual(len(compatibility.splitlines()), 8)
        canonical = (SKILL / "HELP.md").read_text()
        for required in ("/luucycle help", "/luucycle ask-lucas", "application or product", "/luucycle cook", "DOCTOR.md", "remains advisory"):
            self.assertIn(required, canonical)
        self.assertNotIn("Ask Lucas", (SKILL / "DOCTOR.md").read_text())
        for name in ("RULES.md", "INIT.md", "ROSTER-ADD.md"):
            self.assertNotIn("ASK-LUCAS.md", (SKILL / name).read_text())


if __name__ == "__main__":
    unittest.main()
