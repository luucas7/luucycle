"""Free Orca launch preflight; fixture executables never launch agents."""

import os
import sys
import json
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
import doctor
import roster


WORKER_HELP = """orca orchestration worker-start
Usage: orca orchestration worker-start --agent <agent> [--model <id>]
  --agent takes an Orca agent id enabled on the worker server, such as claude, codex, cursor, antigravity, muse, zcode, opencode, or opencode2.
  --model supports Claude, Codex, Cursor, Antigravity, and Muse opaque provider model ids; --effort requires --model. OMP accepts --model only; --effort is unsupported. Neither can combine with --terminal. OpenCode model selection requires an existing worktree, a verified execution-host CLI, and an available model; effort is unsupported. Other agents, including zcode, launch with the model from their own config.
"""


@contextmanager
def launch_fixture(alias=None, help_text=WORKER_HELP):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repo = root / "repo"
        repo.mkdir()
        doctor.write_skill(repo / "skills/orchestration", "orchestration")
        worker = root / "worker"
        doctor.write_executable(worker, "#!" + sys.executable + "\nimport sys\nassert sys.argv[-1:] == ['--help']\nprint('Usage: worker exec --model MODEL --bypass')\n")
        doctor.write_roster(repo, str(worker))
        roster_path = repo / ".agents/luucycle/ROSTER.md"
        if alias is not None:
            roster_path.write_text(roster_path.read_text().replace("- Command:", f"- Orca Agent: `{alias}`\n- Command:"))
        log = root / "calls.log"
        orca = root / "orca-ide"
        doctor.write_executable(orca, "#!" + sys.executable + "\n" +
            "import json, sys\nfrom pathlib import Path\n" +
            f"with Path({str(log)!r}).open('a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')\n" +
            "args = sys.argv[1:]\n" +
            "if args == ['status', '--json']: print(json.dumps({'runtime': {'state': 'ready'}}))\n" +
            "elif args == ['skills', 'get', 'orchestration']: print('# Orca orchestration guide')\n" +
            "elif args == ['skills', 'get', 'orca-cli', '--json']: print(json.dumps({'markdown': '# Orca CLI\\nStarting agents with orchestration worker-start'}))\n" +
            f"elif args == ['orchestration', 'worker-start', '--help']: print({help_text!r})\n" +
            "else: raise SystemExit('fixture refuses command: '+repr(args))\n")
        env = dict(os.environ, ORCA_CLI_COMMAND=str(orca), HOME=str(root / "home"))
        yield repo, env, log


class OrcaLaunchTests(unittest.TestCase):
    def test_one_or_three_codex_workers_are_ready_without_roster_expansion(self):
        for count in (1, 3):
            with self.subTest(workers=count), launch_fixture("codex") as (repo, env, log):
                path = repo / ".agents/luucycle/ROSTER.md"
                template = roster.parse_roster_document(path.read_text()).entries[0]
                entries = [
                    roster.AgentEntry(f"codex:worker-{index}", dict(template.fields, CLI="Codex"))
                    for index in range(count)
                ]
                path.write_text(roster.render_roster(entries))
                roles = path.with_name("ROLES.md")
                eligible = "<br>".join(f"`{entry.agent_id}@1.0`" for entry in entries)
                roles.write_text(roles.read_text().replace("`fake:gpt-test@1.0`", eligible))
                for scope in ("core", "task"):
                    with self.subTest(scope=scope):
                        result = doctor.run_diagnostic(
                            repo, scope, [], env,
                            selected_agent=[entry.agent_id for entry in entries] if scope == "task" else [],
                        )
                        self.assertEqual(result["status"], "READY", result)
                        self.assertEqual(result["warning"], [])
                        self.assertEqual(result["error"], [])
                        checks = {check["check"]: check for check in result["check"]}
                        inventory = checks["roster.cli_diversity"]
                        self.assertEqual(inventory["status"], "PASS")
                        self.assertEqual(inventory["evidence"], ["clis=Codex", "distinct_clis=1"])
                        self.assertNotIn("roster add", json.dumps(result))
                self.assertNotIn('"--agent"', log.read_text())
                self.assertNotIn('"--model"', log.read_text())

    def test_single_cli_inventory_does_not_hide_an_unavailable_selected_cli(self):
        with launch_fixture("codex") as (repo, env, _log):
            path = repo / ".agents/luucycle/ROSTER.md"
            entry = roster.parse_roster_document(path.read_text()).entries[0]
            Path(entry.fields["Command"]).unlink()
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=[entry.agent_id])
            checks = {check["check"]: check for check in result["check"]}
            self.assertEqual(checks["roster.cli_diversity"]["status"], "PASS")
            self.assertEqual(checks[f"cli.{entry.agent_id}"]["status"], "FAIL")
            self.assertEqual(checks["launch.selected"]["status"], "FAIL")
            self.assertEqual(result["status"], "BLOCKED")

    def test_absent_roster_still_blocks_without_an_inventory_check(self):
        with launch_fixture("codex") as (repo, env, _log):
            (repo / ".agents/luucycle/ROSTER.md").unlink()
            result = doctor.run_diagnostic(repo, "core", [], env)
            checks = {check["check"]: check for check in result["check"]}
            self.assertNotIn("roster.cli_diversity", checks)
            self.assertEqual(checks["roster.validation"]["status"], "FAIL")
            self.assertEqual(result["status"], "BLOCKED")

    def test_legacy_contract_never_infers_alias_from_id_cli_or_command(self):
        document = roster.parse_roster_document(roster.sample_roster("codex:gpt-test", "gpt-test"))
        self.assertEqual(document.errors, [])
        self.assertIsNone(document.entries[0].contract()["orca_agent"])
        self.assertNotIn("Orca Agent", roster.render_roster(document.entries))

    def test_unknown_or_malformed_alias_is_never_normalized_or_inferred(self):
        for alias in ("agy", "Codex", "antigravity --model wrong", "agy:gemini-3.1-pro", "unknown"):
            with self.subTest(alias=alias):
                entry = {"agent_id": "agy:gemini-3.1-pro", "Orca Agent": alias, "Model": "gemini-3.1-pro"}
                check = doctor.check_launch_entry(entry, WORKER_HELP, [], [])
                self.assertEqual(check["status"], "FAIL")
                self.assertIn(f"orca_agent={alias}", check["evidence"])

    def test_generic_model_option_does_not_prove_agent_specific_forwarding(self):
        entry = {"agent_id": "codex:exact", "Orca Agent": "codex", "Model": "exact"}
        help_text = WORKER_HELP.split("  --model supports")[0] + "\n--model <id> Generic option\n"
        self.assertEqual(doctor.check_launch_entry(entry, help_text, [], [])["status"], "UNKNOWN")

    def test_unavailable_discovery_is_unknown_without_switching_executables(self):
        help_text, evidence, errors = doctor.launch_help(None, {})
        self.assertEqual(help_text, "")
        self.assertEqual(evidence, [])
        self.assertIn("selected Orca executable is unavailable", errors)
        entry = {"agent_id": "codex:exact", "Orca Agent": "codex", "Model": "exact"}
        self.assertEqual(doctor.check_launch_entry(entry, help_text, evidence, errors)["status"], "UNKNOWN")

    def test_failed_guide_preserves_diagnostics_without_trying_help_or_starting_services(self):
        with launch_fixture("codex") as (repo, env, log):
            orca = Path(env["ORCA_CLI_COMMAND"])
            doctor.write_executable(orca, "#!" + sys.executable + "\n" +
                "import json, sys\nfrom pathlib import Path\n" +
                f"with Path({str(log)!r}).open('a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')\n" +
                "print('guide unavailable: critical-tail')\nprint('exact stderr', file=sys.stderr)\nraise SystemExit(1)\n")
            help_text, evidence, errors = doctor.launch_help([str(orca)], env)
            self.assertEqual(help_text, "")
            self.assertIn("guide unavailable: critical-tail\n", errors)
            self.assertIn("exact stderr\n", errors)
            self.assertEqual(len(evidence), 1)
            self.assertEqual(json.loads(log.read_text()), ["skills", "get", "orca-cli", "--json"])

    def test_selected_id_must_be_enabled_and_not_an_orca_alias(self):
        with launch_fixture("codex") as (repo, env, _log):
            for agent_id in ("codex", "missing:model"):
                with self.subTest(agent_id=agent_id):
                    self.assertEqual(doctor.run_diagnostic(repo, "task", [], env, selected_agent=[agent_id])["status"], "BLOCKED")
            path = repo / ".agents/luucycle/ROSTER.md"
            path.write_text(path.read_text().replace("- Enabled: `true`", "- Enabled: `false`"))
            self.assertEqual(doctor.run_diagnostic(repo, "task", [], env, selected_agent=["fake:gpt-test"])["status"], "BLOCKED")

    def test_unknown_reserved_selected_ids_cannot_borrow_aggregate_checks(self):
        with launch_fixture("codex") as (repo, env, _log):
            for agent_id in ("enabled_available", "selected", "validation", "cli_diversity"):
                with self.subTest(agent_id=agent_id):
                    result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=[agent_id])
                    selected = next(check for check in result["check"] if check["check"] == "launch.selected")
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(selected["status"], "FAIL")
                    self.assertTrue(any("not an enabled role-mapped agent" in error for error in selected["error"]))

    def test_real_reserved_roster_ids_are_rejected_without_duplicate_checks(self):
        for agent_id in ("enabled_available", "selected"):
            with self.subTest(agent_id=agent_id), launch_fixture("codex") as (repo, env, _log):
                path = repo / ".agents/luucycle/ROSTER.md"
                healthy = roster.parse_roster_document(path.read_text()).entries[0]
                path.write_text(roster.render_roster([healthy, roster.AgentEntry(agent_id, dict(healthy.fields))]))
                roles = path.with_name("ROLES.md")
                roles.write_text(roles.read_text().replace("`fake:gpt-test@1.0`", f"`fake:gpt-test@1.0`<br>`{agent_id}@0.9`"))
                result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=[agent_id])
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(any(agent_id in error and "reserved" in error for error in result["error"]))
                names = [check["check"] for check in result["check"]]
                self.assertEqual(len(names), len(set(names)))

    def test_launch_aggregate_does_not_combine_two_agents_partial_readiness(self):
        with launch_fixture() as (repo, env, _log):
            path = repo / ".agents/luucycle/ROSTER.md"
            legacy = roster.parse_roster_document(path.read_text()).entries[0]
            fields = dict(legacy.fields, **{"Orca Agent": "codex", "Command": str(repo / "nonexistent-worker")})
            path.write_text(roster.render_roster([legacy, roster.AgentEntry("codex:broken-cli", fields)]))
            roles = path.with_name("ROLES.md")
            roles.write_text(roles.read_text().replace("`fake:gpt-test@1.0`", "`fake:gpt-test@1.0`<br>`codex:broken-cli@0.9`"))
            result = doctor.run_diagnostic(repo, "core", [], env)
            checks = {check["check"]: check for check in result["check"]}
            self.assertEqual(checks["cli.fake:gpt-test"]["status"], "PASS")
            self.assertEqual(checks["launch.codex:broken-cli"]["status"], "PASS")
            self.assertEqual(checks["launch.enabled_available"]["status"], "WARN")
            self.assertFalse(checks["launch.enabled_available"]["required"])
            self.assertEqual(result["status"], "DEGRADED")

    def test_model_flag_prefix_is_not_evidence_for_the_declared_option(self):
        with launch_fixture("codex") as (repo, env, _log):
            entry = roster.parse_roster_document((repo / ".agents/luucycle/ROSTER.md").read_text()).entries[0]
            doctor.write_executable(Path(entry.fields["Command"]), "#!" + sys.executable + "\nprint('Usage: worker --model-cache PATH --bypass')\n")
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=[entry.agent_id])
            cli = next(check for check in result["check"] if check["check"] == "cli.fake:gpt-test")
            self.assertEqual(cli["status"], "FAIL")
            self.assertEqual(result["status"], "BLOCKED")

    def test_nonzero_worker_help_cannot_make_selected_agent_ready(self):
        with launch_fixture("codex") as (repo, env, _log):
            entry = roster.parse_roster_document((repo / ".agents/luucycle/ROSTER.md").read_text()).entries[0]
            doctor.write_executable(Path(entry.fields["Command"]), "#!" + sys.executable + "\nprint('error: usage --model MODEL --bypass')\nraise SystemExit(2)\n")
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=[entry.agent_id])
            cli = next(check for check in result["check"] if check["check"] == "cli.fake:gpt-test")
            self.assertEqual(cli["status"], "FAIL")
            self.assertEqual(result["status"], "BLOCKED")

    def test_opencode_model_forwarding_stays_unproven_without_host_catalog_evidence(self):
        with launch_fixture("opencode2") as (repo, env, log):
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=["fake:gpt-test"])
            launch = next(check for check in result["check"] if check["check"] == "launch.fake:gpt-test")
            self.assertEqual(launch["status"], "UNKNOWN")
            self.assertTrue(any("existing worktree" in error and "available model" in error for error in launch["error"]))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertNotIn('"--model"', log.read_text())

    def test_omp_model_only_support_is_proven_from_selected_help(self):
        with launch_fixture("omp") as (repo, env, _log):
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=["fake:gpt-test"])
            launch = next(check for check in result["check"] if check["check"] == "launch.fake:gpt-test")
            self.assertEqual(launch["status"], "PASS")
            self.assertIn("launch_model=gpt-test", launch["evidence"])

    def test_explicit_auto_default_does_not_forward_literal_auto_default(self):
        with launch_fixture("zcode") as (repo, env, _log):
            path = repo / ".agents/luucycle/ROSTER.md"
            path.write_text(path.read_text().replace("- Model: `gpt-test`", "- Model: `auto-default`"))
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=["fake:gpt-test"])
            launch = next(check for check in result["check"] if check["check"] == "launch.fake:gpt-test")
            self.assertEqual(launch["status"], "PASS")
            self.assertIn("launch_model=<config-default>", launch["evidence"])
            self.assertNotEqual(result["status"], "BLOCKED")

    def test_config_only_launcher_refuses_exact_model_instead_of_silent_default(self):
        with launch_fixture("zcode") as (repo, env, _log):
            result = doctor.run_diagnostic(repo, "task", [], env, selected_agent=["fake:gpt-test"])
            launch = next(check for check in result["check"] if check["check"] == "launch.fake:gpt-test")
            self.assertEqual(launch["status"], "FAIL")
            self.assertTrue(any("own config" in error for error in launch["error"]))
            self.assertEqual(result["status"], "BLOCKED")

    def test_selected_unproven_agent_blocks_only_its_task_while_healthy_agent_remains_usable(self):
        with launch_fixture() as (repo, env, log):
            path = repo / ".agents/luucycle/ROSTER.md"
            legacy = roster.parse_roster_document(path.read_text()).entries[0]
            fields = dict(legacy.fields, **{"Orca Agent": "codex", "CLI": "Codex"})
            healthy = roster.AgentEntry("codex:healthy", fields)
            path.write_text(roster.render_roster([legacy, healthy]))
            roles = path.with_name("ROLES.md")
            roles.write_text(roles.read_text().replace("`fake:gpt-test@1.0`", "`fake:gpt-test@1.0`<br>`codex:healthy@0.9`"))
            core = doctor.run_diagnostic(repo, "core", [], env)
            self.assertEqual(core["status"], "DEGRADED")
            command = [sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts/doctor.py"), str(repo), "--scope", "task", "--json", "--selected-agent", "fake:gpt-test"]
            selected = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(selected.returncode, 2, selected.stderr)
            self.assertEqual(selected.returncode, 1, selected.stdout)
            result = json.loads(selected.stdout)
            self.assertEqual(result["status"], "BLOCKED")
            checks = {check["check"]: check for check in result["check"]}
            self.assertEqual(checks["launch.selected"]["status"], "FAIL")
            healthy_run = subprocess.run([*command[:-1], "codex:healthy"], env=env, capture_output=True, text=True)
            self.assertEqual(healthy_run.returncode, 0, healthy_run.stdout + healthy_run.stderr)
            self.assertEqual(json.loads(healthy_run.stdout)["status"], "DEGRADED")

    def test_documented_explicit_alias_and_model_are_preflight_ready_without_launch(self):
        with launch_fixture("antigravity") as (repo, env, log):
            path = repo / ".agents/luucycle/ROSTER.md"
            path.write_text(path.read_text().replace("fake:gpt-test", "agy:gemini-3.1-pro").replace("gpt-test", "gemini-3.1-pro"))
            roles_path = path.with_name("ROLES.md")
            roles_path.write_text(roles_path.read_text().replace("fake:gpt-test", "agy:gemini-3.1-pro"))
            result = doctor.run_diagnostic(repo, "core", [], env)
            checks = {check["check"]: check for check in result["check"]}
            self.assertEqual(checks["launch.agy:gemini-3.1-pro"]["status"], "PASS")
            self.assertIn("launch_model=gemini-3.1-pro", checks["launch.agy:gemini-3.1-pro"]["evidence"])
            self.assertTrue(any("host enablement" in item and "unverified" in item
                                for item in checks["launch.agy:gemini-3.1-pro"]["evidence"]))
            self.assertEqual(checks["launch.enabled_available"]["status"], "PASS")
            calls = log.read_text()
            self.assertIn('["skills", "get", "orca-cli", "--json"]', calls)
            self.assertIn('["orchestration", "worker-start", "--help"]', calls)
            self.assertNotIn('"--agent"', calls)
            self.assertNotIn('"--model"', calls)

    def test_legacy_missing_alias_is_readable_but_not_launch_ready(self):
        with launch_fixture() as (repo, env, log):
            result = doctor.run_diagnostic(repo, "core", [], env)
            checks = {check["check"]: check for check in result["check"]}
            self.assertIn("launch.fake:gpt-test", checks)
            launch = checks["launch.fake:gpt-test"]
            self.assertEqual(launch["status"], "FAIL")
            self.assertTrue(any("missing Orca Agent" in error for error in launch["error"]))
            self.assertEqual(checks["roster.validation"]["status"], "PASS")
            self.assertEqual(checks["launch.enabled_available"]["status"], "WARN")
            self.assertEqual(result["status"], "DEGRADED")
            self.assertNotIn("fake:gpt-test", log.read_text())

    def test_explicit_alias_round_trips_without_changing_stable_agent_id(self):
        text = roster.sample_roster("agy:gemini-3.1-pro", "gemini-3.1-pro", cli="Antigravity")
        text = text.replace("- Command:", "- Orca Agent: `antigravity`\n- Command:")
        document = roster.parse_roster_document(text)
        self.assertEqual(document.errors, [])
        entry = document.entries[0]
        self.assertEqual(entry.contract()["agent_id"], "agy:gemini-3.1-pro")
        self.assertEqual(entry.contract()["orca_agent"], "antigravity")
        rendered = roster.render_roster([entry])
        self.assertIn("- Orca Agent: `antigravity`", rendered)
        self.assertEqual(roster.parse_roster_document(rendered).errors, [])
        proposal = roster.agent_to_proposal(entry)
        self.assertEqual(proposal["orca_agent"], "antigravity")
        errors = []
        normalized = roster.normalize_agent_proposal(proposal, 0, errors)
        self.assertEqual(errors, [])
        self.assertEqual(normalized.fields["Orca Agent"], "antigravity")

    def test_role_only_plan_apply_preserves_explicit_alias_and_legacy_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roster_dir = roster.write_sample_repo(root)
            path = roster_dir / "ROSTER.md"
            text = path.read_text().replace("- CLI: `Codex`\n- Command:", "- CLI: `Codex`\n- Orca Agent: `codex`\n- Command:", 1)
            path.write_text(text)
            proposal_path = root / "proposal.json"
            proposal_path.write_text(json.dumps({"roles": {"builder": ["codex:gpt-primary@0.9", "claude:gpt-fallback@0.7"]}}))
            plan = roster.plan_roster(root, str(proposal_path))
            self.assertEqual(plan["status"], "PASS")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            self.assertEqual(roster.apply_plan(root, str(plan_path))["status"], "PASS")
            entries = roster.parse_roster_document(path.read_text()).entries
            by_id = {entry.agent_id: entry for entry in entries}
            self.assertEqual(by_id["codex:gpt-primary"].contract()["orca_agent"], "codex")
            self.assertIsNone(by_id["claude:gpt-fallback"].contract()["orca_agent"])
            selection = roster.select_agents(root, "builder", "medium")
            self.assertEqual(selection["contracts"]["primary"]["orca_agent"], "codex")
            self.assertIsNone(selection["contracts"]["fallback"]["orca_agent"])


if __name__ == "__main__":
    unittest.main()
