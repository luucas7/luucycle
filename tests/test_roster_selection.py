"""Offline selection and documentary contracts; no model or real roster access."""

from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills/luucycle"
sys.path.insert(0, str(SKILL / "scripts"))
import roster


class RosterSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = roster.write_sample_repo(self.root)
        path = self.directory / "ROSTER.md"
        path.write_text(path.read_text() + "\n" + roster.sample_roster("codex:second", "second", "low"))
        path = self.directory / "ROLES.md"
        path.write_text(path.read_text().replace("`claude:gpt-fallback@0.7`", "`claude:gpt-fallback@0.7`<br>`codex:second@0.8`"))

    def run_select(self, *options, role="builder"):
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        process = subprocess.run(
            [sys.executable, "-B", str(SKILL / "scripts/roster.py"), "select", role,
             str(self.root), "--json", *options],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.stderr, "")
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)
        return process.returncode, json.loads(process.stdout)

    def test_three_identical_tasks_and_builder_verifier_keep_best_fit(self):
        selections = []
        for role in ("builder", "builder", "builder", "verifier"):
            code, result = self.run_select(role=role)
            self.assertEqual((code, result["status"]), (0, "PASS"))
            selections.append((result["primary"], result["fallback"]))
            self.assertEqual(result["warnings"], [])
        self.assertEqual(selections, [("codex:gpt-primary", "codex:second")] * 4)

    def test_agent_exclusions_apply_to_both_assignments_once(self):
        for excluded, expected in (
            ("codex:gpt-primary", ("codex:second", "claude:gpt-fallback")),
            ("codex:second", ("codex:gpt-primary", "claude:gpt-fallback")),
        ):
            with self.subTest(excluded=excluded):
                code, result = self.run_select("--avoid", excluded)
                self.assertEqual((code, result["status"]), (0, "PASS"))
                self.assertEqual((result["primary"], result["fallback"]), expected)
                self.assertEqual(result["skipped"].count({"agent_id": excluded, "reason": "avoided"}), 1)

    def test_cost_ceiling_and_disabled_agents_filter_both_assignments(self):
        code, result = self.run_select("--max-cost", "medium")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["contracts"]["primary"]["cost"], "medium")
        self.assertEqual(result["contracts"]["fallback"]["cost"], "low")
        self.assertIn({"agent_id": "codex:gpt-disabled", "reason": "disabled"}, result["skipped"])
        self.assertIn({"agent_id": "gemini:gpt-high", "reason": "cost>medium"}, result["skipped"])
        code, result = self.run_select("--max-cost", "low", "--avoid", "codex:second")
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertNotIn("primary", result)

    def test_combined_cli_id_and_cost_constraints_leave_only_allowed_primary(self):
        code, result = self.run_select("--max-cost", "medium", "--avoid-cli", "Codex", "--avoid", "claude:gpt-fallback")
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        code, result = self.run_select("--avoid-cli", "Codex", "--avoid", "claude:gpt-fallback")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["primary"], "gemini:gpt-high")
        self.assertIsNone(result["fallback"])

    def test_ties_preserve_role_table_order_instead_of_cost_or_cli(self):
        path = self.directory / "ROLES.md"
        document = roster.parse_roles_document(path.read_text())
        rows = [roster.RoleRow(row.role, row.when, row.context, row.output, row.agents,
                               {agent_id: Decimal("0.8") for agent_id in row.agents})
                for row in document.rows]
        path.write_text(roster.render_roles(rows))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual((result["primary"], result["fallback"]), ("claude:gpt-fallback", "codex:second"))
        self.assertEqual(result["contracts"]["primary"]["role_fit"], "0.8")

    def test_legacy_unscored_roles_keep_default_fit_and_table_order(self):
        path = self.directory / "ROLES.md"
        document = roster.parse_roles_document(path.read_text())
        rows = [roster.RoleRow(row.role, row.when, row.context, row.output, row.agents, {})
                for row in document.rows]
        path.write_text(roster.render_roles(rows))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual((result["primary"], result["fallback"]), ("claude:gpt-fallback", "codex:second"))
        self.assertEqual(result["contracts"]["fallback"]["role_fit"], "1.0")

    def test_exclusions_use_exact_labels_without_normalizing_unknown_values(self):
        code, result = self.run_select("--avoid-cli", "codex", "--avoid", "Codex:gpt-primary")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual((result["primary"], result["fallback"]), ("codex:gpt-primary", "codex:second"))

    def test_unknown_role_and_missing_roster_fail_without_assignment(self):
        code, result = self.run_select(role="unknown-role")
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertEqual(result["errors"], ["unknown role: unknown-role"])
        (self.directory / "ROSTER.md").unlink()
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertNotIn("contracts", result)
        self.assertTrue(any("missing file:" in error for error in result["errors"]))

    def test_invalid_fit_fails_validation_before_selecting(self):
        path = self.directory / "ROLES.md"
        path.write_text(path.read_text().replace("@0.9", "@1.1"))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertNotIn("primary", result)
        self.assertTrue(any("role fit must be" in error for error in result["errors"]))

    def test_empty_role_fails_while_unrelated_role_warning_is_preserved(self):
        path = self.directory / "ROLES.md"
        document = roster.parse_roles_document(path.read_text())
        rows = [roster.RoleRow(row.role, row.when, row.context, row.output,
                               [] if row.role == "builder" else row.agents, row.scores)
                for row in document.rows]
        path.write_text(roster.render_roles(rows))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertIn("role builder: no enabled eligible agent", result["warnings"])
        code, result = self.run_select(role="verifier")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertIn("role builder: no enabled eligible agent", result["warnings"])

    def test_zero_enabled_agents_remains_blocking(self):
        path = self.directory / "ROSTER.md"
        path.write_text(path.read_text().replace("- Enabled: `true`", "- Enabled: `false`"))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertIn("zero enabled agents", result["errors"])
        self.assertNotIn("primary", result)

    def test_self_tests_cover_current_selection_contract(self):
        for script in ("roster.py", "check_roster.py"):
            with self.subTest(script=script):
                process = subprocess.run([sys.executable, "-B", str(SKILL / "scripts" / script), "--self-test"],
                                         capture_output=True, text=True, check=False)
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                self.assertEqual(process.stderr, "")
                self.assertIn("self-test: PASS", process.stdout)

    def test_mono_cli_pair_has_fallback_without_diversity_warning(self):
        path = self.directory / "ROSTER.md"
        path.write_text(path.read_text().replace("- CLI: `Claude`", "- CLI: `Codex`").replace("- CLI: `Gemini`", "- CLI: `Codex`"))
        code, result = self.run_select()
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["fallback"], "codex:second")
        self.assertEqual(result["warnings"], [])

    def test_single_candidate_reports_missing_fallback_without_roster_add(self):
        code, result = self.run_select("--max-cost", "low")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["primary"], "codex:second")
        self.assertIsNone(result["fallback"])
        self.assertIsNone(result["contracts"]["fallback"])
        self.assertEqual(result["warnings"], ["role builder: no distinct eligible fallback within the selection constraints"])

    def test_explicit_cli_exclusion_applies_to_primary_and_fallback(self):
        code, result = self.run_select("--avoid-cli", "Codex")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["primary"], "claude:gpt-fallback")
        self.assertEqual(result["fallback"], "gemini:gpt-high")
        self.assertEqual(result["contracts"]["fallback"]["cli"], "Gemini")
        self.assertIn({"agent_id": "codex:second", "reason": "cli_avoided"}, result["skipped"])

    def test_exhausted_explicit_exclusions_fail_instead_of_forced_reuse(self):
        for options in (
            ("--avoid-cli", "Codex", "--avoid-cli", "Claude", "--avoid-cli", "Gemini"),
            tuple(item for agent_id in ("codex:gpt-primary", "codex:second", "claude:gpt-fallback", "gemini:gpt-high")
                  for item in ("--avoid", agent_id)),
        ):
            with self.subTest(options=options):
                code, result = self.run_select(*options)
                self.assertEqual((code, result["status"]), (1, "FAIL"))
                self.assertNotIn("primary", result)
                self.assertNotIn("contracts", result)
                self.assertTrue(any("exclusions" in error for error in result["errors"]))
                self.assertFalse(any("reusing" in warning for warning in result["warnings"]))

    def test_fallback_uses_better_fit_on_same_cli_before_other_product(self):
        code, result = self.run_select("--max-cost", "medium")
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(result["primary"], "codex:gpt-primary")
        self.assertEqual(result["fallback"], "codex:second")
        for position, fit in (("primary", "0.9"), ("fallback", "0.8")):
            self.assertEqual(result["contracts"][position]["agent_id"], result[position])
            self.assertEqual(result["contracts"][position]["role_fit"], fit)
            self.assertEqual(result["contracts"][position]["cli"], "Codex")


class SelectionDocumentContractTests(unittest.TestCase):
    def test_shared_selection_rule_allows_best_fit_reuse(self):
        rules = (SKILL / "RULES.md").read_text()
        rule = rules.split("\n15. ", 1)[1].split("\n16. ", 1)[0]
        self.assertIn("explicit user constraints", rule)
        self.assertIn("Reuse the best-fit Agent ID and CLI", rule)
        self.assertIn("three identical Codex tasks", rule)
        self.assertIn("CLI diversity is optional", rule)
        self.assertNotIn("distinct primary", rule)
        fallback = rules.split("\n3. ", 1)[1].split("\n4. ", 1)[0]
        self.assertIn("distinct Agent ID", fallback)
        self.assertIn("may share the primary's CLI", fallback)
        self.assertIn("product-wide availability failures", fallback)
        self.assertIn("Dispatch that fallback once in a fresh terminal", fallback)

    def test_implementation_keeps_fresh_review_without_automatic_avoidance(self):
        implement = (SKILL / "IMPLEMENT.md").read_text()
        self.assertIn("fresh terminal and conversation", implement)
        self.assertIn("including the builder's Agent ID or CLI", implement)
        self.assertIn("only for explicit user exclusions", implement)
        for obsolete in ("For every task after the first", "select distinct primary agents and CLIs",
                         "Each returned fallback runs on a different CLI", "forced reuse"):
            self.assertNotIn(obsolete, implement)
        for guard in ("Wait for explicit approval of this exact phase plan", "one-shot dispatch",
                      "immediately release or terminate", "Any rework or follow-up is a distinct task"):
            self.assertIn(guard, implement)

    def test_selector_contract_covers_hard_exclusions_and_neutral_warnings(self):
        document = (SKILL / "ROSTER-FORMAT.md").read_text()
        contract = document.split("`select` returns", 1)[1].split("`plan` accepts", 1)[0]
        for required in ("both primary and fallback", "same CLI", "never relaxes explicit exclusions",
                         "table order for ties", "no distinct eligible fallback"):
            self.assertIn(required, contract)
        for obsolete in ("same_cli_as_primary", "already_assigned", "forced primary reuse",
                         "/luucycle roster add"):
            self.assertNotIn(obsolete, contract)


if __name__ == "__main__":
    unittest.main()
