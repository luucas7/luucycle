"""Version-scoped native specimens; offline tests never prove live acceptance."""
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/luucycle/scripts"))
FIXTURES = ROOT / "tests/fixtures/orca/1.4.229"


def module():
    try:
        return importlib.import_module("orca_adapter")
    except ModuleNotFoundError:
        return None


def specimens():
    return {p.stem: p.read_bytes() for p in FIXTURES.glob("*.json")
            if p.name != "provenance.json"}


def change(records, name, edit):
    result = dict(records)
    value = json.loads(result[name])
    edit(value)
    result[name] = json.dumps(value).encode()
    return result


class NativeAdapterTests(unittest.TestCase):
    def adapter(self):
        result = module()
        self.assertIsNotNone(result, "versioned native adapter is not implemented")
        return result

    def test_genuine_native_inventory_normalizes_without_claiming_live_verification(self):
        records = specimens()
        native = json.loads(records["explicit-workers"])["result"]
        result = self.adapter().inspect_fixture("1.4.229", native["scope"]["run"], records)
        self.assertEqual(result["status"], "REVIEW")
        self.assertFalse(result["source_verified"])
        self.assertEqual(result["verification"], "offline_fixture")
        envelope = result["envelope"]
        self.assertEqual(envelope["schema"], "luucycle.return.v1")
        self.assertEqual(envelope["expected_count"], native["page"]["total"])
        self.assertEqual(len(envelope["items"]), len(native["workers"]))
        self.assertTrue(envelope["complete"])
        for before, after in zip(native["workers"], envelope["items"]):
            self.assertEqual(after["id"], before["dispatchId"])
            self.assertEqual(after["controls"]["native_worker"], before)
            self.assertEqual(after["status"], "DONE")
            self.assertTrue(after["controls"]["sealed"])
            self.assertEqual(after["ids"]["task"], before["taskId"])
        from compact import encode, project
        self.assertEqual(project(encode(envelope), "fixture:normalized")["actual_count"], 4)

    def test_every_task_requires_exactly_one_supported_worker(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        def orphan(doc):
            task = copy.deepcopy(doc["result"]["tasks"][0])
            task.update(id="task_ffffffffffff", status="failed", safety_gate="blocked")
            doc["result"]["tasks"].append(task)
            doc["result"]["count"] += 1
        extra = change(base, "task-list", orphan)
        empty = {k: v for k, v in base.items() if not k.startswith(("worker-show-", "dispatch-show-"))}
        empty = change(empty, "explicit-workers", lambda d: d["result"].update(
            workers=[], counts={}, page={"limit": 100, "total": 0, "hasMore": False, "nextCursor": None}))
        no_tasks = change(empty, "task-list", lambda d: d["result"].update(tasks=[], count=0))
        for source in (extra, empty, no_tasks):
            with self.subTest(records=list(source)):
                result = self.adapter().inspect_fixture("1.4.229", run, source)
                self.assertEqual(result["status"], "STOP")
                self.assertFalse(result["source_verified"])
                self.assertNotIn("envelope", result)

    def test_unsupported_version_shape_and_json_fail_closed_without_echo(self):
        records = specimens()
        run = json.loads(records["explicit-workers"])["result"]["scope"]["run"]
        variants = [("1.4.230", records), ("1.4.229", {**records, "task-list": b'{"private":"DO_NOT_ECHO"'}),
                    ("1.4.229", {**records, "task-list": b'{"ok":true,"ok":true}'}),
                    ("1.4.229", {**records, "task-list": b'{"x":NaN}'}),
                    ("1.4.229", change(records, "task-list", lambda d: d.update(ok=False))),
                    ("1.4.229", change(records, "status", lambda d: d["result"]["runtime"].update(appVersion="future"))),
                    ("1.4.229", {**records, "inbox": b'{}'})]
        for version, source in variants:
            with self.subTest(version=version, keys=list(source)):
                result = self.adapter().inspect_fixture(version, run, source)
                self.assertEqual(result["status"], "STOP")
                self.assertFalse(result["source_verified"])
                self.assertNotIn("envelope", result)
                self.assertNotIn("DO_NOT_ECHO", json.dumps(result))

    def test_all_native_pages_are_required_and_counts_are_independently_reconciled(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        paged = {**base, **{p.stem: p.read_bytes() for p in (FIXTURES / "pages").glob("*.json")}}
        good = self.adapter().inspect_fixture("1.4.229", run, paged)
        self.assertEqual(good["status"], "REVIEW")
        self.assertEqual(len(good["envelope"]["items"]), 4)
        bads = [{k: v for k, v in paged.items() if k != "workers-page-2"},
                change(base, "explicit-workers", lambda d: d["result"]["page"].update(total=5)),
                change(base, "explicit-workers", lambda d: d["result"]["page"].update(total=True)),
                change(base, "explicit-workers", lambda d: d["result"]["counts"].update(released=3)),
                change(base, "task-list", lambda d: d["result"].update(count=5)),
                change(base, "task-list", lambda d: d["result"]["tasks"][0].update(spec_truncated=True)),
                change(base, "explicit-workers", lambda d: d["result"].update(partialHostErrors=[{"error": "x"}])),
                change(base, "explicit-workers", lambda d: d["result"]["page"].update(nextCursor="unfollowed")),
                change(paged, "workers-page-1", lambda d: d["result"]["page"].update(nextCursor=json.loads(paged["explicit-workers"])["result"]["page"]["nextCursor"])),
                change(base, "explicit-workers", lambda d: d["result"]["workers"].append(d["result"]["workers"][0]))]
        for bad in bads:
            with self.subTest(keys=list(bad)):
                result = self.adapter().inspect_fixture("1.4.229", run, bad)
                self.assertEqual(result["status"], "STOP")
                self.assertNotIn("envelope", result)

    def test_all_resource_projections_validate_known_crossrefs_and_release_controls(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        for field, value in (("id", "wtr_ffffffffffff"), ("ownerDispatchId", "ctx_ffffffffffff"),
                             ("originDispatchId", "ctx_ffffffffffff"), ("worktreeId", "foreign"),
                             ("terminalHandle", "term_foreign"), ("releaseState", "failed"),
                             ("ownershipState", "retained"), ("releaseError", "PRIVATE_FAILURE"),
                             ("retainedReason", "PRIVATE_FAILURE"), ("terminalState", "retained")):
            for name in ("explicit-workers", "worker-show-0"):
                with self.subTest(receipt=name, field=field):
                    def edit(d):
                        projection = d["result"]["workers"][0]["projection"] if name == "explicit-workers" else d["result"]["projection"]
                        projection["resource"][field] = value
                    result = self.adapter().inspect_fixture("1.4.229", run, change(base, name, edit))
                    self.assertEqual(result["status"], "STOP")
                    self.assertNotIn("PRIVATE_FAILURE", json.dumps(result))
        # Agreement between full records cannot legitimize retained resources.
        source = change(base, "explicit-workers", lambda d: d["result"]["workers"][0]["resource"].update(retainedReason="retained"))
        source = change(source, "worker-show-0", lambda d: d["result"]["terminalResource"].update(retainedReason="retained"))
        self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, source)["status"], "STOP")

    def test_independent_authoritative_records_reject_foreign_and_conflicting_ids(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        cases = [
            ("run-show", lambda d: d["result"]["run"].update(id="run_ffffffffffff")),
            ("task-list", lambda d: d["result"].update(runId="run_ffffffffffff")),
            ("task-list", lambda d: d["result"]["tasks"][0].update(run_id="run_ffffffffffff")),
            ("task-list", lambda d: d["result"]["tasks"][0].update(parent_id="task_ffffffffffff")),
            ("task-list", lambda d: d["result"]["tasks"][0].update(deps='["task_ffffffffffff"]')),
            ("task-list", lambda d: d["result"]["tasks"][0].update(status="dispatched", dispatch_id="ctx_ffffffffffff")),
            ("explicit-workers", lambda d: d["result"]["workers"][0].update(runId="run_ffffffffffff")),
            ("explicit-workers", lambda d: d["result"]["workers"][0]["projection"].update(taskId="task_ffffffffffff")),
            ("explicit-workers", lambda d: d["result"]["workers"][0]["resource"].update(ownerDispatchId="ctx_ffffffffffff")),
            ("explicit-workers", lambda d: d["result"]["workers"][0]["resource"]["archive"].update(truncated=True)),
            ("worker-show-0", lambda d: d["result"]["dispatch"].update(task_id="task_ffffffffffff")),
            ("worker-show-0", lambda d: d["result"]["worker"].update(agentTerminalHandle="term_foreign")),
            ("worker-show-0", lambda d: d["result"]["terminalResource"].update(worktreeId="foreign")),
            ("worker-show-0", lambda d: d["_meta"].update(runtimeId="foreign-runtime")),
            ("explicit-workers", lambda d: d["result"]["workers"][0].update(workerState="future")),
        ]
        for name, edit in cases:
            with self.subTest(receipt=name):
                result = self.adapter().inspect_fixture("1.4.229", run, change(base, name, edit))
                self.assertEqual(result["status"], "STOP")
                self.assertNotIn("envelope", result)
        result = self.adapter().inspect_fixture("1.4.229", run[:-1], base)
        self.assertEqual(result["status"], "STOP")

    def test_safety_and_completeness_controls_stop_with_retained_evidence(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        cases = [
            ("task-list", lambda d: d["result"].update(complete=False, hasMore=True, nextCursor="missing")),
            ("run-show", lambda d: d["result"].update(partialHostErrors=[{"error": "PRIVATE_FAILURE"}])),
            ("run-show", lambda d: d["result"]["run"].update(safety_gate="PRIVATE_FAILURE")),
            ("task-list", lambda d: d["result"]["tasks"][0].update(safety_gate="PRIVATE_FAILURE")),
        ]
        for field, value in (("outcome", "failed"), ("attention", {"requiresAction": True, "categories": ["repair"]}),
                             ("nextAction", {"kind": "repair", "argv": ["PRIVATE_FAILURE"]})):
            source = change(base, "explicit-workers", lambda d: d["result"]["workers"][0]["projection"].update({field: value}))
            source = change(source, "worker-show-0", lambda d: d["result"]["projection"].update({field: value}))
            cases.append((None, source))
        for name, edit in cases:
            source = change(base, name, edit) if name else edit
            with self.subTest(receipt=name):
                result = self.adapter().inspect_fixture("1.4.229", run, source)
                self.assertEqual(result["status"], "STOP")
                self.assertNotIn("envelope", result)
                self.assertNotIn("PRIVATE_FAILURE", json.dumps(result))
                self.assertEqual(set(result["sources"]), set(source))
                for key, raw in source.items():
                    self.assertEqual(result["sources"][key]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_unknown_controls_wrappers_and_pagination_survive_without_numeric_loss(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        future = {"nested": ["control" * 900, {"permission": False}]}
        modified = change(base, "explicit-workers", lambda d: (d.update(future_wrapper=future), d["result"].update(future_collection=future), d["result"]["workers"][0].update(future_row=future)))
        modified = change(modified, "worker-show-0", lambda d: d.update(future_show_wrapper=future))
        result = self.adapter().inspect_fixture("1.4.229", run, modified)
        self.assertEqual(result["status"], "STOP")
        self.assertNotIn("envelope", result)
        # Unknown controls remain decision-bearing: immutable source references,
        # not an invented success interpretation or leaked native narrative.
        for name, raw in modified.items():
            self.assertEqual(result["sources"][name]["sha256"], hashlib.sha256(raw).hexdigest())
        for literal in (b'0.12345678901234567890123456789', b'1e999', b'1e-999', b'"\\ud800"'):
            raw = base["explicit-workers"].replace(b'"released": 4', b'"released": 4, "future_number": ' + literal)
            out = self.adapter().inspect_fixture("1.4.229", run, {**base, "explicit-workers": raw})
            self.assertEqual(out["status"], "STOP")

    def replay_collect(self, directory, overrides=None, **kwargs):
        """Synthetic subprocess seam replay; never a live/authenticity assertion."""
        adapter = self.adapter()
        records = specimens()
        overrides = overrides or {}
        def capture(argv, target, name):
            self.assertEqual(argv[0], sys.executable)
            key = name.removeprefix("final-")
            if key == "tasks":
                key = "task-list"
            if name == "version":
                raw = b"1.4.229\n"
            elif name == "guide":
                raw = b'{"name":"orchestration"}'
            else:
                raw = overrides.get(name, records[key])
            ref = adapter._store(target / (name + ".stdout"), raw)
            adapter._store(target / (name + ".stderr"), b"")
            return raw, ref
        with mock_patch.object(adapter, "_capture", side_effect=capture):
            return adapter.collect("run_7c58413f7566", directory, capture_authorized=True,
                                   executable=sys.executable, **kwargs)

    def test_closing_authority_is_fully_validated_and_reconciled(self):
        base = specimens()
        cases = [
            ("status", lambda d: d.update(error={"code": "runtime_unavailable", "message": "PRIVATE_FAILURE"})),
            ("status", lambda d: d["result"]["runtime"].update(state="stopped", reachable=False)),
            ("status", lambda d: d["result"].update(target={"kind": "remote"})),
            ("status", lambda d: d.update(id="foreign")),
            ("status", lambda d: d["_meta"].update(runtimeId="foreign")),
            ("explicit-workers", lambda d: d["result"]["workers"][0]["projection"].update(outcome="failed")),
            ("dispatch-show-0", lambda d: d["result"]["dispatch"].update(id="ctx_ffffffffffff")),
            ("run-show", lambda d: d["result"]["run"].update(consumer_generation=2)),
        ]
        for key, edit in cases:
            with self.subTest(closing=key), tempfile.TemporaryDirectory() as directory:
                raw = change(base, key, edit)[key]
                result = self.replay_collect(directory, {"final-" + key: raw})
                self.assertEqual(result["status"], "STOP")
                self.assertFalse(result["source_verified"])
                self.assertNotIn("projection", result)
                self.assertNotIn("PRIVATE_FAILURE", json.dumps(result))
                self.assertEqual(Path(result["sources"]["final-" + key]["ref"]).read_bytes(), raw)
        with tempfile.TemporaryDirectory() as directory:
            result = self.replay_collect(directory)
            self.assertEqual(result["status"], "REVIEW", result["issues"])
            self.assertTrue(result["source_verified"])
            for key in ("status", "run-show", "task-list", "explicit-workers", "dispatch-show-0"):
                self.assertIn("final-" + key, result["sources"])

    def test_failed_collection_never_claims_verified_source(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.replay_collect(directory, expectations={"task_2360d69fd0c3": {}})
            self.assertEqual(result["status"], "STOP")
            self.assertEqual(result["acceptance"], "INCOMPLETE")
            self.assertFalse(result["source_verified"])

    def test_live_runtime_selection_is_explicit_before_storage_or_subprocess(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as directory, mock_patch.object(adapter, "_capture", return_value=(b"1.4.229\n", {})) as capture:
            result = adapter.collect("run_7c58413f7566", directory, capture_authorized=True)
            self.assertEqual(result["status"], "STOP")
            self.assertFalse(result["source_verified"])
            self.assertEqual(list(Path(directory).iterdir()), [])
            capture.assert_not_called()

    def test_selected_absolute_executable_is_reused_without_fallback(self):
        adapter = self.adapter()
        self.assertIn("executable", __import__("inspect").signature(adapter.collect).parameters)
        with tempfile.TemporaryDirectory() as directory:
            for selected in ("orca-ide", directory, "/usr/bin/orca", str(Path(directory) / "missing")):
                with self.subTest(executable=selected), mock_patch.object(adapter, "_capture") as capture:
                    result = adapter.collect("run_7c58413f7566", directory, capture_authorized=True, executable=selected)
                    self.assertEqual(result["status"], "STOP")
                    self.assertEqual(list(Path(directory).iterdir()), [])
                    capture.assert_not_called()
            with mock_patch.object(adapter, "_capture", side_effect=OSError("PRIVATE_FAILURE")) as capture:
                result = adapter.collect("run_7c58413f7566", directory, capture_authorized=True, executable=sys.executable)
                self.assertEqual(result["status"], "STOP")
                self.assertFalse(result["source_verified"])
                self.assertNotIn("PRIVATE_FAILURE", json.dumps(result))
                self.assertEqual(capture.call_count, 1)
                self.assertEqual(capture.call_args.args[0], [sys.executable, "--version"])
        script = ROOT / "skills/luucycle/scripts/orca_adapter.py"
        denied = subprocess.run([sys.executable, "-B", str(script), "collect", "--run", "run_7c58413f7566",
                                 "--capture-root", str(FIXTURES), "--capture-authorized", "--orca-executable", "relative"],
                                capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stdout)["status"], "STOP")

    def test_live_capture_requires_explicit_storage_permission_and_exact_selector(self):
        adapter = self.adapter()
        self.assertTrue(hasattr(adapter, "collect"), "owned live retrieval is missing")
        with tempfile.TemporaryDirectory() as directory:
            before = list(Path(directory).iterdir())
            result = adapter.collect("run_7c58413f7566", directory, executable=sys.executable)
            self.assertEqual(result["status"], "STOP")
            self.assertEqual(list(Path(directory).iterdir()), before)
            result = adapter.collect("run_7c58413f756", directory, capture_authorized=True, executable=sys.executable)
            self.assertEqual(result["status"], "STOP")
            self.assertEqual(list(Path(directory).iterdir()), before)

    @unittest.skipUnless(os.environ.get("ORCA_ADAPTER_LIVE_TEST") == "1" and os.environ.get("ORCA_ADAPTER_EXECUTABLE"), "explicit live read-only executable selection")
    def test_genuine_local_retrieval_is_byte_bound_and_projected_only_after_capture(self):
        adapter = self.adapter()
        self.assertTrue(hasattr(adapter, "collect"), "owned live retrieval is missing")
        with tempfile.TemporaryDirectory() as directory:
            result = adapter.collect("run_7c58413f7566", directory, capture_authorized=True,
                                     executable=os.environ["ORCA_ADAPTER_EXECUTABLE"])
            self.assertEqual(result["status"], "REVIEW", result.get("issues"))
            self.assertTrue(result["source_verified"])
            self.assertEqual(result["verification"], "live_read_only_source")
            self.assertNotIn("envelope", result)
            self.assertEqual(result["projection"]["actual_count"], 4)
            self.assertEqual(result["acceptance"], "NOT_EVALUATED")
            for ref in result["sources"].values():
                raw = Path(ref["ref"]).read_bytes()
                self.assertEqual(ref["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(ref["bytes"], len(raw))
            self.assertTrue(all("detail" not in row for row in result["projection"]["items"]))

    def test_task_evidence_requires_routed_skill_content_and_explicit_permissions(self):
        adapter = self.adapter()
        self.assertTrue(hasattr(adapter, "validate_task_evidence"), "task evidence seam is missing")
        with tempfile.TemporaryDirectory() as directory:
            skill_path = Path(directory) / "SKILL.md"
            skill_path.write_text("# Routed skill\n")
            skill = {"identity": "test-routed-skill", "path": str(skill_path),
                     "sha256": hashlib.sha256(skill_path.read_bytes()).hexdigest()}
            expected = {"routed_skill": skill, "permissions": {"artifact_write": False, "report_write": False},
                        "storage": "existing_record"}
            report = {"schema": "luucycle.task-evidence.v1", "task_id": "task_2360d69fd0c3",
                      "dispatch_id": "ctx_0e0e9b0e6b63", "routed_skill": skill, "loaded_skill": skill,
                      "writes": {"artifact": False, "report": False},
                      "storage": {"kind": "existing_record", "ref": "orca:task:task_2360d69fd0c3:result"}}
            check = lambda policy, observation, complete=True: adapter.validate_task_evidence(
                policy, observation, task_id=report["task_id"], dispatch_id=report["dispatch_id"], source_complete=complete)
            good = check(expected, report)
            self.assertEqual(good["status"], "EVIDENCE_REVIEW")
            self.assertFalse(good["source_verified"])
            self.assertEqual(good["acceptance"], "NOT_GRANTED")
            self.assertIn("not proof of worker loading", good["limits"])
            bad_reports = []
            for edit in [lambda d: d.update(task_id="task_ffffffffffff"),
                         lambda d: d.update(dispatch_id="ctx_ffffffffffff"),
                         lambda d: d.update(schema="future"),
                         lambda d: d.update(loaded_skill={**skill, "identity": "wrong"}),
                         lambda d: d.update(loaded_skill={**skill, "sha256": "0" * 64}),
                         lambda d: d["writes"].update(artifact=True),
                         lambda d: d.update(storage={"kind": "artifact", "path": str(skill_path), "sha256": skill["sha256"]}),
                         lambda d: d["storage"].update(ref="orca:task:foreign:result")]:
                bad = copy.deepcopy(report)
                edit(bad)
                bad_reports.append(bad)
            for bad in bad_reports:
                self.assertEqual(check(expected, bad)["status"], "STOP")
            self.assertEqual(check(expected, report, False)["status"], "STOP")
            skill_path.write_text("changed skill")
            self.assertEqual(check(expected, report)["status"], "STOP")

    def test_artifact_report_requires_exact_authorized_path_and_matching_content(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            skill_path = Path(directory) / "SKILL.md"
            skill_path.write_text("skill")
            report_path = Path(directory) / "report.txt"
            report_path.write_text("existing execution report")
            skill = {"identity": "skill", "path": str(skill_path), "sha256": hashlib.sha256(skill_path.read_bytes()).hexdigest()}
            policy = {"routed_skill": skill, "permissions": {"artifact_write": True, "report_write": True},
                      "storage": "artifact", "report_path": str(report_path)}
            report = {"schema": "luucycle.task-evidence.v1", "task_id": "task_2360d69fd0c3", "dispatch_id": "ctx_0e0e9b0e6b63",
                      "routed_skill": skill, "loaded_skill": skill, "writes": {"artifact": True, "report": True},
                      "storage": {"kind": "artifact", "path": str(report_path), "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()}}
            check = lambda p=policy, r=report: adapter.validate_task_evidence(p, r, task_id=report["task_id"], dispatch_id=report["dispatch_id"], source_complete=True)
            # A digest of unrelated bytes is not a task report binding.
            self.assertEqual(check()["status"], "STOP")
            bound = {"schema": "luucycle.task-report.v1",
                     "receipt": {k: v for k, v in report.items() if k != "storage"},
                     "detail": "Executed the task-scoped review; assertions remain untrusted."}
            for edit in (lambda d: d.update(schema="future"),
                         lambda d: d["receipt"].update(task_id="task_ffffffffffff"),
                         lambda d: d["receipt"]["loaded_skill"].update(identity="foreign"),
                         lambda d: d.update(detail=" "), lambda d: d.pop("receipt")):
                bad = copy.deepcopy(bound)
                edit(bad)
                report_path.write_text(json.dumps(bad))
                report["storage"]["sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
                self.assertEqual(check()["status"], "STOP")
            report_path.write_text(json.dumps(bound))
            report["storage"]["sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
            self.assertEqual(check()["status"], "EVIDENCE_REVIEW")
            self.assertEqual(check({**policy, "permissions": {"artifact_write": True, "report_write": False}})["status"], "STOP")
            self.assertEqual(check({**policy, "report_path": str(skill_path)})["status"], "STOP")
            report_path.write_text("changed")
            self.assertEqual(check()["status"], "STOP")

    def test_optional_task_expectations_block_acceptance_not_unrelated_diagnostics(self):
        adapter = self.adapter()
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        self.assertEqual(adapter.inspect_fixture("1.4.229", run, base)["status"], "REVIEW")
        self.assertIn("expectations", __import__("inspect").signature(adapter.inspect_fixture).parameters,
                      "task policy must be enforced at adapter seam")
        result = adapter.inspect_fixture("1.4.229", run, base, expectations={"task_2360d69fd0c3": {}})
        self.assertEqual(result["status"], "STOP")
        self.assertEqual(result["acceptance"], "INCOMPLETE")
        row = next(x for x in result["envelope"]["items"] if x["ids"]["task"] == "task_2360d69fd0c3")
        self.assertTrue(row["controls"]["sealed"])
        self.assertEqual(row["decision"]["action"], "inspect_existing_records")
        self.assertFalse(row["decision"]["worker_input_allowed"])
        self.assertTrue(row["blockers"])
        self.assertFalse(result["source_verified"])

    def test_latest_dispatch_and_local_authority_are_required_even_for_settled_workers(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, base)["status"], "REVIEW")
        cases = [
            ("dispatch-show-0", lambda d: d["result"]["dispatch"].update(id="ctx_ffffffffffff")),
            ("dispatch-show-0", lambda d: d["result"]["dispatch"].update(task_id="task_ffffffffffff")),
            ("dispatch-show-0", lambda d: d["result"]["dispatch"].update(status="dispatched")),
            ("worker-show-0", lambda d: d["result"]["dispatch"].update(contractVersion=2)),
            ("worker-show-0", lambda d: d["result"]["dispatch"].update(hostScope={"kind": "remote", "hostId": "foreign"})),
        ]
        for name, edit in cases:
            self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, change(base, name, edit))["status"], "STOP")
        missing = {k: v for k, v in base.items() if k != "dispatch-show-0"}
        self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, missing)["status"], "STOP")

    @unittest.skipUnless(os.environ.get("ORCA_ADAPTER_LIVE_TEST") == "1" and os.environ.get("ORCA_ADAPTER_EXECUTABLE"), "explicit live read-only executable selection")
    def test_live_expectations_fail_incomplete_without_contacting_sealed_worker(self):
        adapter = self.adapter()
        self.assertIn("expectations", __import__("inspect").signature(adapter.collect).parameters)
        with tempfile.TemporaryDirectory() as directory:
            result = adapter.collect("run_7c58413f7566", directory, capture_authorized=True,
                                     executable=os.environ["ORCA_ADAPTER_EXECUTABLE"],
                                     expectations={"task_2360d69fd0c3": {}})
            self.assertEqual(result["status"], "STOP")
            self.assertFalse(result["source_verified"])
            self.assertEqual(result["acceptance"], "INCOMPLETE")
            row = next(x for x in result["projection"]["items"] if x["ids"]["task"] == "task_2360d69fd0c3")
            self.assertFalse(row["decision"]["worker_input_allowed"])
            self.assertTrue(row["controls"]["sealed"])

    def test_subprocess_failures_timeout_and_overflow_leave_exact_private_receipts(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [("failure", "import sys; print('retained'); sys.stderr.write('PRIVATE_ERROR'); sys.exit(7)", 2, 1024),
                     ("overflow", "import sys; sys.stdout.write('x'*2048)", 2, 1024),
                     ("timeout", "import time; time.sleep(2)", 0.05, 1024)]
            for name, code, timeout, size in cases:
                with self.subTest(case=name):
                    with self.assertRaises(adapter.AdapterError):
                        adapter._capture([sys.executable, "-B", "-c", code], root, name, timeout=timeout, max_bytes=size)
                    receipt_path = root / (name + ".process.json")
                    self.assertTrue(receipt_path.exists(), "exit/error accounting must be retained")
                    receipt = json.loads(receipt_path.read_bytes())
                    self.assertEqual(receipt["argv"], [sys.executable, "-B", "-c", code])
                    self.assertFalse(receipt["successful"])
                    self.assertLessEqual((root / (name + ".stdout")).stat().st_size, size)
                    self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
                    if name == "failure":
                        self.assertEqual(receipt["exit_code"], 7)
                        self.assertEqual(Path(receipt["stderr"]["ref"]).read_bytes(), b"PRIVATE_ERROR")
                    else:
                        self.assertFalse(receipt["complete"])
            raw, ref = adapter._capture([sys.executable, "-B", "-c", "print('success')"], root, "success")
            self.assertEqual(raw, b"success\n")
            self.assertEqual(ref["sha256"], hashlib.sha256(raw).hexdigest())

    def test_inconsistent_error_and_unknown_expectation_cannot_escape_stop(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        variants = [change(base, "task-list", lambda d: d.update(error={"code": "native_error"})),
                    change(base, "task-list", lambda d: d["result"].update(errors=["unresolved"])),
                    change(base, "run-show", lambda d: d.pop("id")),
                    change(base, "worker-show-0", lambda d: d["result"]["worker"].update(failedStage="launch"))]
        for source in variants:
            self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, source)["status"], "STOP")
        result = self.adapter().inspect_fixture("1.4.229", run, base, expectations={"task_ffffffffffff": {}})
        self.assertEqual(result["status"], "STOP")

    def test_fixture_provenance_covers_every_native_specimen_and_exact_hash(self):
        manifest = json.loads((FIXTURES / "provenance.json").read_bytes())
        paths = {str(p.relative_to(FIXTURES)): p for p in FIXTURES.rglob("*.json") if p.name != "provenance.json"}
        self.assertEqual(set(manifest["files"]), set(paths))
        for name, path in paths.items():
            self.assertEqual(manifest["files"][name]["fixture_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            if not manifest["files"][name]["redactions"]:
                self.assertEqual(manifest["files"][name]["fixture_sha256"], manifest["files"][name]["original_sha256"])

    def test_cli_projects_fixture_only_and_reports_offline_scope(self):
        script = ROOT / "skills/luucycle/scripts/orca_adapter.py"
        result = subprocess.run([sys.executable, "-B", str(script), "fixture", "--version", "1.4.229",
                                 "--run", "run_7c58413f7566", "--directory", str(FIXTURES)],
                                capture_output=True, check=False)
        self.assertTrue(result.stdout, "native adapter command line is missing")
        value = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(value["source_verified"])
        self.assertNotIn("envelope", value)
        self.assertEqual(value["projection"]["actual_count"], 4)
        self.assertTrue(all("detail" not in row for row in value["projection"]["items"]))
        denied = subprocess.run([sys.executable, "-B", str(script), "collect", "--run", "run_7c58413f7566",
                                 "--capture-root", str(FIXTURES)], capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stdout)["status"], "STOP")

    def test_unsupported_lineage_liveness_and_malformed_narrative_are_not_projected(self):
        base = specimens()
        run = json.loads(base["explicit-workers"])["result"]["scope"]["run"]
        variants = [change(base, "task-list", lambda d: d["result"]["tasks"][0].update(spec={"unknown": "shape"})),
                    change(base, "task-list", lambda d: d["result"]["tasks"][0].update(result={"unknown": "shape"})),
                    change(base, "worker-show-0", lambda d: d["result"]["dispatch"].update(retryOfDispatchId="ctx_ffffffffffff")),
                    change(base, "worker-show-0", lambda d: d["result"]["dispatch"].update(creatorDispatchId="ctx_ffffffffffff")),
                    change(base, "dispatch-show-0", lambda d: d["result"]["dispatch"].update(contract_version=True)),
                    change(base, "worker-show-0", lambda d: d["result"]["projection"]["resource"].update(ownerDispatchId="ctx_ffffffffffff"))]
        # Mutate both independently obtained projections: agreement alone is not proof of valid state.
        altered = change(base, "worker-show-0", lambda d: d["result"]["projection"]["liveness"].update(verdict="future"))
        altered = change(altered, "explicit-workers", lambda d: d["result"]["workers"][0]["projection"]["liveness"].update(verdict="future"))
        variants.append(altered)
        for source in variants:
            self.assertEqual(self.adapter().inspect_fixture("1.4.229", run, source)["status"], "STOP")


if __name__ == "__main__":
    unittest.main()
