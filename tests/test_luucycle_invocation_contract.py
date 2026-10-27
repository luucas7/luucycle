"""Static routing/approval contracts, not simulations of agent behavior."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "luucycle"


class LuucycleInvocationContractTests(unittest.TestCase):
    def test_codex_can_route_literal_slash_commands_to_the_skill(self):
        metadata = (SKILL / "agents" / "openai.yaml").read_text()
        instructions = (SKILL / "SKILL.md").read_text()

        self.assertIn("allow_implicit_invocation: true", metadata)
        self.assertIn("/luucycle", metadata)
        self.assertIn("/luucycle", instructions)
        self.assertIn("$luucycle", instructions)
        self.assertIn("before considering the rest of the prompt as a direct coding request", instructions)

    def test_implementation_brief_cannot_bypass_phase_approval(self):
        implementation = (SKILL / "IMPLEMENT.md").read_text()
        rules = (SKILL / "RULES.md").read_text()

        gate = implementation.index("Approval is the boundary between planning and execution.")
        selection = implementation.index("Break its work into tasks")
        dispatch = implementation.index("Dispatch Execution with a skill contract")
        self.assertLess(gate, selection)
        self.assertLess(gate, dispatch)
        self.assertIn("Do not edit project files, dispatch workers, or run implementation work.", implementation)
        self.assertIn("authorizes coordination and planning, not unapproved execution", rules)

    def test_shared_guardrail_requires_independent_review_for_every_execution_change(self):
        rules = " ".join((SKILL / "RULES.md").read_text().split())
        review = rules.split("17. ", 1)[-1]
        for required in (
            "Every Execution change, including small code or documentation changes",
            "a `builder` followed by an independent `verifier`",
            "distinct task roles in fresh conversations and terminals",
            "same approved Execution table",
            "Reuse the best-fit Agent ID, model or CLI under rule 15",
            "An absent or unresolved blocked reviewer leaves acceptance incomplete",
            "Builder self-review, green tests or coordinator prose do not replace independent review",
            "Read-only Audit, Doctor and consultation do not trigger recursive review",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in review, required)
        self.assertNotIn("Focused", review)
        self.assertNotIn("Extended", review)

    def test_focused_review_covers_bounded_code_or_documentation_with_one_builder(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        for required in (
            "Choose **Focused** only for a bounded task whose",
            "scope is clear, local and reversible",
            "sufficient objective evidence",
            "one `builder` owns the requested files, including source and tests",
            "For code plus unit tests, route that builder to `tdd`",
            "For both levels, plan two sequential tasks under RULES rule 17",
            "a `verifier` task routed to `code-review` depends on the builder",
            "reviews the complete diff read-only and examines the relevant test evidence",
            "runs the pertinent tests within its approved test rights",
            "A Focused review may use a brief report",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)
        self.assertNotIn("When a request asks for both code and a unit-test suite, plan two", implementation)

    def test_risk_or_insufficient_evidence_requires_extended_not_a_small_diff_shortcut(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        for required in (
            "Choose **Extended** for ambiguity",
            "multi-component changes or public contracts",
            "security or permissions",
            "persistent data or migrations",
            "concurrency",
            "insufficient verification",
            "When in doubt, choose Extended",
            "A small diff or green tests alone do not justify Focused",
            "small local, reversible correction with focused tests may be Focused",
            "small permissions change is Extended",
            "Extended adds risk-adapted analysis of counterexamples and regressions",
            "does not automatically add subagents",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)

    def test_mandatory_review_and_ui_require_extended_with_fresh_best_fit_verifier(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        for required in (
            "User, project or routed-skill requirements for deeper review select Extended",
            "Mandatory independent review alone does not force Extended",
            "UI work is Extended and still requires the impeccable UI Gate",
            "Keep both rows in the approval table",
            "fresh terminal and conversation, with its own review brief",
            "including the builder's Agent ID or CLI when it is the best fit",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)

    def test_review_level_and_evidence_are_disclosed_under_the_same_approval_table(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        disclosure = "Under the same Execution table, state Focused or Extended"
        self.assertTrue(disclosure in implementation, disclosure)
        table = implementation.index("| Task | Routed skill | Primary agent | Fallback agent |")
        approval = implementation.index("Wait for explicit approval of this exact phase plan")
        self.assertLess(implementation.index("Choose the Execution review level before phase approval"), table)
        self.assertLess(table, implementation.index(disclosure))
        self.assertLess(implementation.index(disclosure), approval)
        for required in (
            "risk rationale, planned objective evidence and the independent verifier assignment",
            "Both levels include independent review",
            "Use the existing phase approval, without another table or gate",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)

    def test_risk_growth_pauses_for_reapproval_before_another_dispatch(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        for required in (
            "If scope or risk increases during building, pause the affected work",
            "report the new risk and exact partial changes",
            "return to step 2 for a revised plan and explicit user approval before any further dispatch",
            "Never add a hidden reviewer or self-upgrade the approved plan",
            "A worker's DONE status does not bypass acceptance checks",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)

    def test_completion_discloses_actual_review_without_inventing_independence(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        completion = implementation.split("## Completion criterion", 1)[1].split("## Retrospective", 1)[0]
        for required in (
            "approved review level, evidence actually obtained and actual independent review",
            "reviewer identity, exact diff covered, test evidence examined, verdict and limits",
            "An absent or unresolved blocked reviewer leaves acceptance incomplete under RULES rule 17",
            "Report the blocker and any missing evidence without inventing a review or acceptance",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in completion, required)
        for forbidden in (
            "reviewer and scope, or none",
            "Light",
            "Reviewed",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, completion)

    def test_unresolved_verifier_uses_existing_fallback_and_cannot_be_self_approved(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        blocked = implementation.split("6. **Handle a blocked or unavailable worker.", 1)[1]
        for required in (
            "For an unavailable verifier, use only this approved fallback path",
            "if review remains blocked, pause with acceptance incomplete under RULES rule 17",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in blocked, required)

    def test_small_focused_retrospective_can_be_one_sentence_without_invented_lessons(self):
        implementation = " ".join((SKILL / "IMPLEMENT.md").read_text().split())
        retrospective = implementation.split("## Retrospective", 1)[1]
        for required in (
            "For a small Focused task, one sentence on observed friction or no reusable lesson is sufficient",
            "Report only actual checks and review; invent neither a review nor a WARNINGS entry",
            "With no useful lesson, omit the proposal and approval question",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in retrospective, required)

    def test_review_docs_have_no_review_free_level_and_state_static_proof_limits(self):
        for path in (SKILL / "IMPLEMENT.md", SKILL / "RULES.md", ROOT / "tests" / "README.md"):
            text = " ".join(path.read_text().split())
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(any(token in text for token in (
                    "Light", "Reviewed", "without an automatic `verifier`",
                    "no independent review", "reviewer and scope, or none",
                )), "obsolete review exception or level")
        readme = " ".join((ROOT / "tests" / "README.md").read_text().split())
        for required in (
            "Focused et Extended, tous deux avec builder puis verifier indépendant",
            "agent behavior: NOT_EVALUATED",
            "aucun gain de performance",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in readme, required)


if __name__ == "__main__":
    unittest.main()
