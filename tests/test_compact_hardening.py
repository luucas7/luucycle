"""Snapshot guards do not establish native authority or lock runtime input."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
from compact import check_input
from synthetic_returns import envelope, record

SCRIPT = Path(__file__).resolve().parents[1] / "skills/luucycle/scripts/compact.py"


class CompactHardeningTests(unittest.TestCase):
    def test_input_rejects_snapshot_with_unaccounted_records(self):
        worker = record(1, status="RUNNING")
        packet = envelope("workers", [worker])
        packet["expected_count"] = 2
        result = check_input(packet, worker_id=worker["id"])
        self.assertEqual(result["status"], "STOP")
        self.assertIn("count", " ".join(result["issues"]))

    def test_directory_sources_stop_with_explicit_file_requirement(self):
        for source in ("", ".", str(SCRIPT.parent)):
            with self.subTest(source=source):
                result = subprocess.run(
                    [sys.executable, "-B", str(SCRIPT), "project", source],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                receipt = json.loads(result.stdout)
                self.assertEqual(receipt["status"], "STOP")
                self.assertIn("regular file", " ".join(receipt["issues"]))


if __name__ == "__main__":
    unittest.main()
