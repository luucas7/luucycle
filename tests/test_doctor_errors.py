"""Diagnostic failures remain complete even when the success path is compact."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
import doctor


class DoctorErrorTests(unittest.TestCase):
    def test_single_cli_inventory_is_informational_for_one_or_three_workers(self):
        for count in (1, 3):
            with self.subTest(workers=count):
                payload = {"agents": [
                    {"agent_id": f"codex:worker-{index}", "cli": "Codex",
                     "enabled": "true", "roles": ["builder"]}
                    for index in range(count)
                ]}
                check = doctor.check_cli_diversity(payload)
                self.assertEqual(check["status"], "PASS")
                self.assertFalse(check["required"])
                self.assertEqual(check["evidence"], ["clis=Codex", "distinct_clis=1"])
                self.assertEqual(check["warning"], [])
                self.assertEqual(check["error"], [])
                self.assertEqual(doctor.overall_status([check]), "READY")

    def test_cli_inventory_counts_only_enabled_role_mapped_products(self):
        payload = {"agents": [
            {"cli": "Codex", "enabled": "true", "roles": ["builder"]},
            {"cli": "Claude", "enabled": "true", "roles": ["verifier"]},
            {"cli": "Codex", "enabled": "true", "roles": ["researcher"]},
            {"cli": "Disabled", "enabled": "false", "roles": ["builder"]},
            {"cli": "Unmapped", "enabled": "true", "roles": []},
        ]}
        check = doctor.check_cli_diversity(payload)
        self.assertEqual(check["status"], "PASS")
        self.assertFalse(check["required"])
        self.assertEqual(check["evidence"], ["clis=Claude,Codex", "distinct_clis=2"])
        self.assertEqual(check["warning"], [])
        self.assertEqual(check["error"], [])

    def test_cli_inventory_does_not_create_a_pass_for_absent_eligible_workers(self):
        for payload in (None, {}, {"agents": []}, {"agents": [
            {"cli": "Codex", "enabled": "false", "roles": ["builder"]},
            {"cli": "Codex", "enabled": "true", "roles": []},
        ]}):
            with self.subTest(payload=payload):
                self.assertIsNone(doctor.check_cli_diversity(payload))

    def test_cli_inventory_reports_missing_product_as_unknown_without_claiming_availability(self):
        check = doctor.check_cli_diversity({"agents": [
            {"enabled": "true", "roles": ["builder"]},
        ]})
        self.assertEqual(check["evidence"], ["clis=unknown", "distinct_clis=1"])
        self.assertFalse(check["required"])

    def test_orca_errors_preserve_both_streams_and_evidence_after_1200_characters(self):
        stderr = "synthetic-échec-" * 200 + "critical-tail:unverifiable"
        stdout = "synthetic receipt: residualResources=terminal:SYNTH-01"
        result = {"returncode": 1, "stdout": stdout, "stderr": stderr, "error": "", "timed_out": False}
        with patch.object(doctor, "resolve_command", return_value=(["synthetic-orca"], "/synthetic/orca", None)), \
             patch.object(doctor, "run_bounded", return_value=result):
            checks, _ = doctor.check_orca({})
        by_name = {check["check"]: check for check in checks}
        self.assertEqual(by_name["orca.status"]["status"], "FAIL")
        self.assertEqual(set(by_name["orca.status"]["error"]), {stderr, stdout})
        self.assertEqual(by_name["orca.guide"]["error"], [stdout + "\n" + stderr])

    def test_roster_parse_failure_preserves_both_streams_without_cutting(self):
        stdout = "not-json:" + "synthetic-data-" * 200 + "critical-tail:partial"
        stderr = "synthetic parse failure: retain original receipt"
        result = {"returncode": 1, "stdout": stdout, "stderr": stderr, "error": "", "timed_out": False}
        skill_root = Path(__file__).resolve().parents[1] / "skills/luucycle"
        with patch.object(doctor, "run_bounded", return_value=result):
            payload, check = doctor.check_roster(Path("/synthetic/repo"), skill_root, {})
        self.assertIsNone(payload)
        self.assertEqual(check["status"], "UNKNOWN")
        self.assertIn(stdout, check["error"])
        self.assertIn(stderr, check["error"])


if __name__ == "__main__":
    unittest.main()
