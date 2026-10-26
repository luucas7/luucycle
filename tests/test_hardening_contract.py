"""Static text contracts; these checks do not prove LLM behavior or enforcement."""

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

    def test_retrospective_proposes_only_useful_lessons_with_exact_consent_scope(self):
        implementation = " ".join(
            (SKILL / "IMPLEMENT.md").read_text().partition("## Retrospective\n")[2].split()
        )
        for required in (
            "only when a CLI/agent lesson is well-supported and reusable",
            "<repo-root>/.agents/luucycle/WARNINGS.md",
            "exact proposed text or diff",
            "explicitly ask for approval",
            "With no useful lesson, omit the proposal and approval question",
            "Refusal or absent approval leaves files unchanged",
            "separate decision limited to the approved diff",
            "If the proposed text changes, obtain approval again",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in implementation, required)

    def test_retrospective_keeps_audit_proposals_read_only(self):
        retrospective = " ".join(
            (SKILL / "IMPLEMENT.md").read_text().partition("## Retrospective\n")[2].split()
        )
        for required in (
            "In Audit, present the proposal only",
            "never persist it as part of Audit or its closure",
            "separately authorized transition outside Audit",
            "Native authorization does not authorize that transition",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in retrospective, required)

    def test_lesson_persistence_requires_native_rights_and_verified_exact_write(self):
        retrospective = " ".join(
            (SKILL / "IMPLEMENT.md").read_text().partition("## Retrospective\n")[2].split()
        )
        for required in (
            "Content approval is not technical write permission",
            "Before promising a native authorization prompt, verify that the current runtime actually offers one",
            "If sandbox protection blocks the target",
            "request separate native user authorization for the exact write command, once only",
            "The user grants it; never self-approve or select a persistent/session rule",
            "If the native interface is unavailable or authorization is denied",
            "leave the target unchanged and report `proposal approved but not saved`",
            "After a successful write, reread the target and compare it with the exact approved diff",
            "If the proposed text changes, obtain approval again before writing",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in retrospective, required)

    def test_optional_promotion_does_not_block_the_completed_run(self):
        implementation = (SKILL / "IMPLEMENT.md").read_text()
        completion = implementation.partition("## Completion criterion\n")[2].partition(
            "## Retrospective\n"
        )[0]
        retrospective = " ".join(implementation.partition("## Retrospective\n")[2].split())
        self.assertIn("the Retrospective is delivered", completion)
        for required in (
            "Retrospective delivery completes the run once the completion criterion above is met",
            "The optional promotion decision never blocks the final receipt",
            "including after refusal or without a reply",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in retrospective, required)

    def test_warning_entries_preserve_uncertainty_context_and_bounded_evidence(self):
        warnings = " ".join(
            (SKILL / "ROSTER-FORMAT.md").read_text().partition("## WARNINGS.md\n")[2].split()
        )
        for required in (
            "**Observation**",
            "**Context**",
            "CLI/agent, version, and relevant environment",
            "**Evidence**",
            "reference to existing evidence",
            "omit secrets and raw logs",
            "**Cause**",
            "explicitly labeled hypothesis or `unknown`",
            "**Workaround and limits**",
            "observed workaround or `none`",
            "applicability and unverified limits",
            "A successful outcome does not establish causality",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in warnings, required)
        self.assertNotIn("Each entry records symptom, cause, and the behavior that avoids it", warnings)
        implementation = (SKILL / "IMPLEMENT.md").read_text()
        self.assertIn("(ROSTER-FORMAT.md#warningsmd)", implementation)

    def test_lesson_promotion_preserves_authority_and_security_limits(self):
        retrospective = " ".join(
            (SKILL / "IMPLEMENT.md").read_text().partition("## Retrospective\n")[2].split()
        )
        for required in (
            "Keep warnings advisory under RULES and existing roster/role authority",
            "Neither success nor approval justifies changing user configuration (including persistent permissions), models, or the roster",
            "disabling the sandbox globally, moving the source of truth, or bypassing safeguards",
            "Human approval is consent to the diff, not a safety guarantee or prompt-injection filter",
            "adds no automatic memory engine or security enforcement",
            "Keep the full retrospective in the final receipt rather than copying it into general help",
        ):
            with self.subTest(required=required):
                self.assertTrue(required in retrospective, required)

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
