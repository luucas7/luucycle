"""Diagnostic failures remain complete even when the success path is compact."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
import doctor


class DoctorErrorTests(unittest.TestCase):
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
