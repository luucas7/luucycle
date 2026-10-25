"""Keep operational documentation honest about proof and enforcement boundaries."""

from pathlib import Path
import unittest

SKILL = Path(__file__).resolve().parents[1] / "skills/luucycle"


class HardeningContractTests(unittest.TestCase):
    def test_one_shot_distinguishes_snapshot_validation_from_runtime_fencing(self):
        contract = (SKILL / "COMPACT.md").read_text()
        rules = (SKILL / "RULES.md").read_text()
        self.assertIn("snapshot guard", contract)
        self.assertIn("does not intercept", contract)
        self.assertIn("observed behavior", rules)
        self.assertIn("runtime-enforced", rules)

    def test_dispatch_preserves_dirty_baseline_and_limits_test_writes(self):
        implementation = (SKILL / "IMPLEMENT.md").read_text()
        self.assertIn("git_baseline.py", implementation)
        self.assertIn("preexisting", implementation)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", implementation)
        self.assertIn("test tools may still write", implementation)

    def test_receipt_rules_name_permissions_completeness_and_linter_scope(self):
        contract = (SKILL / "COMPACT.md").read_text()
        self.assertIn("task permissions", contract)
        self.assertIn("acceptance incomplete", contract)
        self.assertIn("linter scope", contract)
        self.assertIn("directory", contract)

    def test_doctor_documents_selected_launch_identity_and_limits(self):
        doctor = (SKILL / "DOCTOR.md").read_text()
        for required in ("--selected-agent", "free launch", "selected_agent",
                         "not a successful launch", "PYTHONDONTWRITEBYTECODE=1"):
            self.assertTrue(required in doctor, required)

    def test_execution_routes_through_supported_evidence_tools(self):
        implementation = (SKILL / "IMPLEMENT.md").read_text()
        compact = (SKILL / "COMPACT.md").read_text()
        for required in ("--selected-agent", "GIT-BASELINE.md", "ORCA-ADAPTER.md"):
            self.assertTrue(required in implementation, required)
        for required in ("orca_adapter.py", "source_verified", "NOT_EVALUATED",
                         "inbox/Delivery", "handwritten"):
            self.assertTrue(required in compact, required)


if __name__ == "__main__":
    unittest.main()
