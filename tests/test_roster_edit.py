"""Exercise roster edit's shared plan/apply CLI on synthetic, temporary rosters.

Approval and existing-only scope are branch instructions, not script enforcement.
No CLI/model discovery, network, credentials, or real roster is accessed.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"
sys.path.insert(0, str(SCRIPTS))
import roster


class RosterEditMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = roster.write_sample_repo(self.root)
        self.before = self.snapshot()
        self.entries = roster.parse_roster_document(self.before["ROSTER.md"].decode()).entries
        self.roles = roster.parse_roles_document(self.before["ROLES.md"].decode())
        selected = roster.agent_to_proposal(self.entries[0])
        selected.update(cost="low", verified="2026-10-26; synthetic help and pricing; quota UNKNOWN")
        self.proposal = {
            "version": 1,
            "roster": [selected],
            "roles": {"builder": [
                "codex:gpt-primary@0.95", "claude:gpt-fallback@0.7",
                "codex:gpt-disabled@0.8", "gemini:gpt-high@0.6",
            ]},
        }

    def snapshot(self):
        return {name: (self.directory / name).read_bytes() for name in ("ROSTER.md", "ROLES.md", "WARNINGS.md")}

    def run_cli(self, command, payload=None):
        args = [sys.executable, "-B", str(SCRIPTS / "roster.py"), command, "--json"]
        if payload is not None:
            payload_path = self.root / f"{command}-input.json"
            payload_path.write_text(json.dumps(payload))
            args.append(str(payload_path))
        args.append(str(self.root))
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def planned(self):
        code, plan = self.run_cli("plan", self.proposal)
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["status"], "PASS", plan)
        return plan

    def test_list_and_existing_entry_plan_leave_roster_bytes_unchanged(self):
        code, listing = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertEqual(len(listing["agents"]), len(self.entries))
        plan = self.planned()
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(plan["changes"]["roster_upserts"], ["codex:gpt-primary"])
        self.assertEqual(plan["changes"]["roles_replaced"], ["builder"])
        for name in ("ROSTER.md", "ROLES.md"):
            self.assertEqual(plan["base_hashes"][name], roster.sha256_text(self.before[name].decode()))

    def test_apply_updates_same_id_preserving_peers_disabled_state_and_other_roles(self):
        plan = self.planned()
        code, result = self.run_cli("apply", plan)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "PASS", result)
        after = self.snapshot()
        for name, preview in plan["previews"].items():
            self.assertEqual(after[name], preview.encode())
            self.assertEqual(roster.sha256_text(after[name].decode()), plan["expected_hashes"][name])
        self.assertEqual(after["WARNINGS.md"], self.before["WARNINGS.md"])
        parsed = roster.parse_roster_document(after["ROSTER.md"].decode())
        self.assertEqual(parsed.errors, [])
        self.assertEqual([entry.agent_id for entry in parsed.entries], [entry.agent_id for entry in self.entries])
        self.assertEqual(parsed.entries[1:], self.entries[1:])
        self.assertEqual(parsed.entries[0].fields["Cost"], "low")
        self.assertEqual(parsed.entries[0].fields["Enabled"], "true")
        self.assertEqual(parsed.entries[1].fields["Enabled"], "false")
        updated_roles = roster.parse_roles_document(after["ROLES.md"].decode())
        for role in roster.REQUIRED_ROLES:
            if role == "builder":
                self.assertEqual(str(updated_roles.role_scores[role]["codex:gpt-primary"]), "0.95")
                for peer in ("claude:gpt-fallback", "codex:gpt-disabled", "gemini:gpt-high"):
                    self.assertEqual(updated_roles.role_scores[role][peer], self.roles.role_scores[role][peer])
            else:
                self.assertEqual(updated_roles.row_by_role[role], self.roles.row_by_role[role])
        code, checked = self.run_cli("check")
        self.assertEqual((code, checked["status"]), (0, "PASS"))
        code, repeat = self.run_cli("apply", plan)
        self.assertEqual(code, 1)
        self.assertEqual(repeat["status"], "FAIL")
        self.assertEqual(self.snapshot(), after)

    def test_stale_base_for_either_file_rejects_before_any_write(self):
        for name in ("ROSTER.md", "ROLES.md"):
            with self.subTest(name=name):
                for original, data in self.before.items():
                    (self.directory / original).write_bytes(data)
                plan = self.planned()
                path = self.directory / name
                path.write_bytes(path.read_bytes() + b"\nConcurrent edit\n")
                changed = self.snapshot()
                code, result = self.run_cli("apply", plan)
                self.assertEqual(code, 1)
                self.assertTrue(any("does not match approved base" in error for error in result["errors"]))
                self.assertEqual(self.snapshot(), changed)

    def test_modified_preview_is_rejected_without_writing(self):
        plan = self.planned()
        plan["previews"]["ROSTER.md"] += "\nUnapproved change\n"
        code, result = self.run_cli("apply", plan)
        self.assertEqual(code, 1)
        self.assertTrue(any("does not match preview content" in error for error in result["errors"]))
        self.assertEqual(self.snapshot(), self.before)


if __name__ == "__main__":
    unittest.main()
