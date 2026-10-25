"""Offline Delivery projector tests; inbox messages in this file are synthetic."""
import copy
import importlib
import json
import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/luucycle/scripts"))
FIXTURES = ROOT / "tests/fixtures/orca/1.4.229"


def base_records():
    return {p.stem: p.read_bytes() for p in FIXTURES.glob("*.json") if p.name != "provenance.json"}


def replace(records, name, value):
    updated = dict(records)
    updated[name] = json.dumps(value, ensure_ascii=False).encode()
    return updated


class OrcaInboxTests(unittest.TestCase):
    def setUp(self):
        self.inbox = importlib.import_module("orca_inbox")
        self.records = base_records()
        workers = json.loads(self.records["explicit-workers"])["result"]["workers"]
        row = workers[0]
        self.run_id, self.task_id, self.dispatch_id = row["runId"], row["taskId"], row["dispatchId"]
        template = json.loads((FIXTURES / "inbox-synthetic/nominal-messages.json").read_bytes())
        messages = []
        for index, source in enumerate(template["messages"]):
            def substitute(value):
                if isinstance(value, str):
                    return value.replace("$TASK_ID", self.task_id).replace("$DISPATCH_ID", self.dispatch_id)
                if isinstance(value, dict):
                    return {k: substitute(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [substitute(v) for v in value]
                return value
            message = {
                "id": f"msg_synthetic_{index + 1}", "run_id": self.run_id,
                "from_handle": row["agentTerminalHandle"], "to_handle": "term_synthetic_coordinator",
                **substitute(source), "priority": "normal", "thread_id": "thread_synthetic",
                "created_at": "2026-10-25T10:00:00Z", "delivery_contract": "contract_v1"
            }
            message["payload"] = json.dumps(message["payload"], separators=(",", ":"))
            messages.append(message)
        self.check = {"id": "synthetic-check-receipt", "ok": True,
                      "result": {"runId": self.run_id, "deliveryId": "delivery_synthetic_001",
                                 "messages": messages, "count": len(messages), "acknowledged": None,
                                 "replayed": False, "timedOut": False, "cancelled": False,
                                 "connectionLost": False},
                      "_meta": copy.deepcopy(json.loads(self.records["status"])["_meta"])}
        self.records["check"] = json.dumps(self.check).encode()
        task_doc = json.loads(self.records["task-list"])
        done = messages[1]
        for task in task_doc["result"]["tasks"]:
            if task["id"] == self.task_id:
                task["result"] = json.dumps({
                    "provenance": "worker_report", "outcome": "succeeded", "messageId": done["id"],
                    "reportedBy": done["from_handle"], "completedBy": done["from_handle"],
                    "subject": done["subject"], "body": done["body"], "filesModified": [],
                    "reportPath": None, "completedAt": "2026-10-25T10:00:00Z"})
        self.records["task-list"] = json.dumps(task_doc).encode()
        for index in range(len(messages)):
            self.records[f"worker-show-{index}"] = self.records["worker-show-0"]
            self.records[f"dispatch-show-{index}"] = self.records["dispatch-show-0"]
            self.records[f"final-worker-show-{index}"] = self.records[f"worker-show-{index}"]
            self.records[f"final-dispatch-show-{index}"] = self.records[f"dispatch-show-{index}"]
        for name in ("status", "run-show", "task-list", "explicit-workers"):
            self.records[f"final-{name}"] = self.records[name]

    def inspect(self, records=None):
        return self.inbox.inspect_delivery("1.4.229", self.run_id, records or self.records)

    def test_nominal_delivery_keeps_complete_native_messages_and_exact_authority_ids(self):
        result = self.inspect()
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertFalse(result["source_verified"])
        projection = result["projection"]
        self.assertEqual(projection["delivery"]["result"]["deliveryId"], "delivery_synthetic_001")
        self.assertEqual([m["native_message"]["id"] for m in projection["messages"]],
                         ["msg_synthetic_1", "msg_synthetic_2"])
        first, second = projection["messages"]
        self.assertIn("The full second line must survive collection.", first["native_message"]["body"])
        self.assertEqual(first["ids"], {"run": self.run_id, "task": self.task_id, "dispatch": self.dispatch_id})
        self.assertEqual(second["parsed_payload"]["outcome"], "succeeded")
        self.assertEqual(second["native_message"]["body"],
                         f"Implemented and verified the requested work. Task: {self.task_id}. Dispatch: {self.dispatch_id}. Outcome: succeeded.")

    def test_foreign_and_mismatched_message_ids_stop_without_projection(self):
        cases = []
        foreign_run = copy.deepcopy(self.check)
        foreign_run["result"]["messages"][0]["run_id"] = "run_ffffffffffff"
        cases.append(replace(self.records, "check", foreign_run))
        foreign_dispatch = copy.deepcopy(self.check)
        payload = json.loads(foreign_dispatch["result"]["messages"][1]["payload"])
        payload["dispatchId"] = "ctx_ffffffffffff"
        foreign_dispatch["result"]["messages"][1]["payload"] = json.dumps(payload)
        cases.append(replace(self.records, "check", foreign_dispatch))
        for records in cases:
            result = self.inspect(records)
            self.assertEqual(result["status"], "STOP")
            self.assertNotIn("projection", result)

    def test_bad_delivery_receipts_and_native_errors_stop(self):
        bads = []
        empty = copy.deepcopy(self.check)
        empty["result"].update(deliveryId=None, messages=[], count=0)
        bads.append(replace(self.records, "check", empty))
        unknown = copy.deepcopy(self.check)
        unknown["result"]["futureControl"] = True
        bads.append(replace(self.records, "check", unknown))
        failed = copy.deepcopy(self.check)
        failed["ok"] = False
        bads.append(replace(self.records, "check", failed))
        partial = copy.deepcopy(json.loads(self.records["explicit-workers"]))
        partial["result"]["page"]["hasMore"] = True
        bads.append(replace(self.records, "explicit-workers", partial))
        for records in bads:
            result = self.inspect(records)
            self.assertEqual(result["status"], "STOP")
            self.assertFalse(result["source_verified"])
            self.assertNotIn("projection", result)

    def test_missing_authority_and_stale_closing_snapshot_stop(self):
        missing = {k: v for k, v in self.records.items() if k != "dispatch-show-0"}
        result = self.inspect(missing)
        self.assertEqual(result["status"], "STOP")
        self.assertNotIn("projection", result)
        stale = copy.deepcopy(json.loads(self.records["final-dispatch-show-0"]))
        stale["result"]["dispatch"]["status"] = "failed"
        result = self.inspect(replace(self.records, "final-dispatch-show-0", stale))
        self.assertEqual(result["status"], "STOP")
        self.assertNotIn("projection", result)

    def test_unreadable_or_clipped_native_text_stops_and_keeps_digest(self):
        # Truncated JSON is retained by source identity but is never projected.
        records = dict(self.records)
        records["check"] = self.records["check"][:-14]
        result = self.inspect(records)
        self.assertEqual(result["status"], "STOP")
        self.assertIn("check", result["sources"])
        self.assertEqual(len(result["sources"]["check"]["sha256"]), 64)

    def test_live_collect_requires_explicit_delivery_and_storage_authority(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result = self.inbox.collect_delivery(self.run_id, directory,
                                                  executable="/opt/Orca/resources/bin/orca-ide")
            self.assertEqual(result["status"], "STOP")
            self.assertFalse(result["source_verified"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_read_dispatch_authority_returns_exact_current_ids_and_sealed_state(self):
        adapter = importlib.import_module("orca_adapter")
        sources = self.records
        def capture(argv, directory, name):
            mapping = {"status": "status", "run-show": "run-show", "task-list": "task-list",
                       "explicit-workers": "explicit-workers", "worker-show": "worker-show-0",
                       "dispatch-show": "dispatch-show-0", "final-status": "status",
                       "final-run": "run-show", "final-tasks": "task-list",
                       "final-workers": "explicit-workers", "final-worker": "worker-show-0",
                       "final-dispatch": "dispatch-show-0"}
            raw = b"1.4.229\n" if name == "version" else (
                b'{"name":"orchestration"}' if name == "guide" else sources[mapping[name]])
            return raw, {"ref": str(Path(directory) / name), "sha256": __import__("hashlib").sha256(raw).hexdigest(),
                         "bytes": len(raw)}
        with __import__("tempfile").TemporaryDirectory() as directory, patch.object(adapter, "_capture", side_effect=capture):
            row = json.loads(sources["explicit-workers"])["result"]["workers"][0]
            result = self.inbox.read_dispatch_authority(self.run_id, row["taskId"], row["dispatchId"], directory,
                                                        executable=sys.executable, capture_authorized=True)
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertTrue(result["source_verified"])
        self.assertTrue(result["complete"])
        self.assertTrue(result["sealed"])
        self.assertEqual(result["ids"], {"run": self.run_id, "task": row["taskId"],
                                          "dispatch": row["dispatchId"], "assignee": row["agentTerminalHandle"]})

    def test_collect_delivery_uses_one_default_check_and_never_acknowledges(self):
        adapter = importlib.import_module("orca_adapter")
        captured = []
        def capture(argv, directory, name):
            captured.append((list(argv), name))
            mapping = {"check": "check", "status": "status", "run-show": "run-show",
                       "task-list": "task-list", "explicit-workers": "explicit-workers",
                       "worker-show-0": "worker-show-0", "worker-show-1": "worker-show-0",
                       "dispatch-show-0": "dispatch-show-0", "dispatch-show-1": "dispatch-show-0",
                       "final-status": "status", "final-run-show": "run-show",
                       "final-task-list": "task-list", "final-explicit-workers": "explicit-workers",
                       "final-worker-show-0": "worker-show-0", "final-worker-show-1": "worker-show-0",
                       "final-dispatch-show-0": "dispatch-show-0", "final-dispatch-show-1": "dispatch-show-0"}
            raw = b"1.4.229\n" if name == "version" else (
                b'{"name":"orchestration"}' if name == "guide" else self.records[mapping[name]])
            return raw, {"ref": str(Path(directory) / name), "sha256": __import__("hashlib").sha256(raw).hexdigest(),
                         "bytes": len(raw)}
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, "_capture", side_effect=capture):
            result = self.inbox.collect_delivery(self.run_id, directory, executable=sys.executable,
                                                  capture_authorized=True, consume_authorized=True)
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertTrue(result["source_verified"])
        checks = [argv for argv, name in captured if name == "check"]
        self.assertEqual(len(checks), 1)
        self.assertIn("--run", checks[0])
        self.assertNotIn("--peek", checks[0])
        self.assertNotIn("--all", checks[0])
        self.assertNotIn("--ack", checks[0])
        self.assertTrue(all("--ack" not in argv and "reply" not in argv and "send" not in argv
                            for argv, _ in captured))

    def test_native_delivery_metadata_and_dispatch_addressed_question_survive(self):
        check = copy.deepcopy(self.check)
        check["result"]["mutation"] = {"requestId": "actual-request-id", "replayed": False}
        check["result"]["messages"][0].update(from_handle=f"dispatch:{self.dispatch_id}", delivered_at=None)
        result = self.inspect(replace(self.records, "check", check))
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertEqual(result["projection"]["delivery"]["result"]["mutation"], check["result"]["mutation"])

    def test_missing_attestation_does_not_erase_native_settlement(self):
        check = copy.deepcopy(self.check)
        payload = json.loads(check["result"]["messages"][1]["payload"])
        payload.pop("task_evidence")
        check["result"]["messages"][1]["payload"] = json.dumps(payload)
        result = self.inspect(replace(self.records, "check", check))
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertNotIn("task_evidence", result["projection"]["messages"][1]["parsed_payload"])

    def test_unrelated_task_report_cannot_authorize_worker_done(self):
        doc = json.loads(self.records["task-list"])
        target = next(task for task in doc["result"]["tasks"] if task["id"] == self.task_id)
        report = json.loads(target["result"])
        report["messageId"] = "msg_other"
        target["result"] = json.dumps(report)
        records = replace(self.records, "task-list", doc)
        records = replace(records, "final-task-list", doc)
        result = self.inspect(records)
        self.assertEqual(result["status"], "STOP")
        self.assertIn("not linked", result["issues"][0])

    def test_nullable_terminal_schema_rejects_non_object_scalar(self):
        native = json.loads(self.records["worker-show-0"])
        native["result"]["terminal"] = 42
        result = self.inspect(replace(self.records, "worker-show-0", native))
        self.assertEqual(result["status"], "STOP")
        self.assertNotIn("projection", result)

    def test_mechanical_compact_projection_retains_message_and_controls(self):
        result = self.inspect()
        view, raw = self.inbox.compact_delivery(result, "fixture:normalized-delivery")
        self.assertEqual(view["status"], "REVIEW", view["issues"])
        native = result["projection"]["messages"]
        for record, projected in zip(native, view["items"]):
            self.assertEqual(projected["ids"]["message"], record["native_message"]["id"])
            self.assertEqual(projected["controls"]["message"]["payload"], record["native_message"]["payload"])
            self.assertEqual(projected["controls"]["current_dispatch"], record["native_current_dispatch"])
            self.assertNotIn("spec", projected["controls"]["task"])
        self.assertEqual(view["source"]["sha256"], __import__("hashlib").sha256(raw).hexdigest())

    def test_byte_exact_live_delivery_fixture_and_provenance(self):
        directory = FIXTURES.parent / "delivery-1.4.229"
        manifest = json.loads((directory / "provenance.json").read_text())
        records = {}
        for name, provenance in manifest["files"].items():
            raw = (directory / name).read_bytes()
            self.assertEqual(__import__("hashlib").sha256(raw).hexdigest(), provenance["sha256"])
            self.assertEqual(len(raw), provenance["bytes"])
            self.assertEqual(provenance["classification"], "byte_exact_native_receipt")
            records[Path(name).stem] = raw
        result = self.inbox.inspect_delivery("1.4.229", manifest["run_id"], records)
        self.assertEqual(result["status"], "REVIEW", result["issues"])
        self.assertFalse(result["source_verified"])
        view, raw = self.inbox.compact_delivery(result, "fixture:live-normalized")
        self.assertEqual(view["items"][0]["ids"]["delivery"], "delivery_ff93cecca90e")
        self.assertTrue(view["items"][0]["controls"]["sealed"])
        self.assertLess(view["source"]["bytes"], sum(len(v) for v in records.values()))

    def test_fixture_cli_projects_before_stdout_without_writing_sources(self):
        directory = FIXTURES.parent / "delivery-1.4.229"
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "skills/luucycle/scripts/orca_inbox.py"),
                                    "fixture-delivery", "--version", "1.4.229", "--run", "run_1ca5b4d322df",
                                    "--directory", str(directory)], capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["projection"]["schema"], "luucycle.return.v1")
        self.assertFalse(result["source_verified"])
        self.assertNotIn(b'"task_spec"', completed.stdout)
        self.assertNotIn(b'"collection_narratives"', completed.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})


if __name__ == "__main__":
    unittest.main()
