"""Bootstrap documentation and offline CLI checks, not human approval enforcement."""

import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills/luucycle"
sys.path.insert(0, str(SKILL / "scripts"))
roster = importlib.import_module("roster")


class RosterBootstrapTests(unittest.TestCase):
    def test_rule_11_scopes_bootstrap_exception_to_initial_creation(self):
        rules = (SKILL / "RULES.md").read_text()
        match = re.search(r"^11\. (.*?)(?=\n\n12\.)", rules, re.M | re.S)
        self.assertIsNotNone(match)
        assert match is not None
        rule = match.group(1)
        self.assertIn("For an existing roster, `roster add` and `roster edit`", rule)
        self.assertIn("`roster.py`'s hash guard", rule)
        self.assertIn("Initial creation of missing `.agents/luucycle/`", rule)
        self.assertIn("three exact approved previews", rule)
        self.assertEqual(rule.count("[ROSTER-ADD.md](ROSTER-ADD.md)"), 1)
        self.assertNotIn("check --json", rule)  # Procedure belongs to the branch.

    def test_init_delegates_bootstrap_and_existing_updates_keep_guarded_branch(self):
        init = (SKILL / "INIT.md").read_text()
        self.assertIn("([ROSTER-ADD.md](ROSTER-ADD.md))", init)
        branch = (SKILL / "ROSTER-ADD.md").read_text()
        for required in (
            "When `.agents/luucycle/` is missing", "`ROSTER.md`, `ROLES.md`, and `WARNINGS.md`",
            "No roster file is written in this step", "Wait for explicit approval of this exact write",
            "Existing roster updates go through `plan` and `apply`; do not hand-edit existing roster files",
            "For a missing roster, create the three approved previews exactly as shown",
            'scripts/roster.py\" check --json',
        ):
            self.assertIn(required, branch)

    def test_missing_roster_rejects_plan_and_checks_exact_initial_previews(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = roster.write_sample_repo(base / "fixture")
            names = ("ROSTER.md", "ROLES.md", "WARNINGS.md")
            previews = {name: (fixture / name).read_bytes() for name in names}
            project = base / "project"
            project.mkdir()
            agent = roster.parse_roster_document(previews["ROSTER.md"].decode()).entries[0]
            proposal = base / "proposal.json"
            proposal.write_text(json.dumps({"version": 1, "roster": [roster.agent_to_proposal(agent)]}))
            command = [sys.executable, "-B", str(SKILL / "scripts/roster.py")]
            result = subprocess.run(command + ["plan", "--json", str(proposal), str(project)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")
            failed = json.loads(result.stdout)
            self.assertEqual(failed["status"], "FAIL")
            self.assertEqual({Path(error.removeprefix("missing file: ")).name for error in failed["errors"]},
                             set(names))
            self.assertEqual(list(project.iterdir()), [])

            # Simulate the branch's approved bootstrap; no bootstrap writer exists.
            directory = project / ".agents/luucycle"
            directory.mkdir(parents=True)
            for name, preview in previews.items():
                (directory / name).write_bytes(preview)
            result = subprocess.run(command + ["check", "--json", str(project)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.stderr, "")
            self.assertEqual((result.returncode, json.loads(result.stdout)["status"]), (0, "PASS"))
            self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, previews)


if __name__ == "__main__":
    unittest.main()
