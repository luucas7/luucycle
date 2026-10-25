"""Regression checks for explicit luucycle command routing and approval gates."""

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

    def test_code_and_unit_test_requests_plan_a_separate_read_only_verifier(self):
        implementation = (SKILL / "IMPLEMENT.md").read_text()

        self.assertIn("plan two sequential tasks", implementation)
        self.assertIn("a `builder` task routed to `tdd`", implementation)
        self.assertIn("a `verifier` task routed to `code-review`", implementation)
        self.assertIn("reviews the complete diff read-only", implementation)


if __name__ == "__main__":
    unittest.main()
