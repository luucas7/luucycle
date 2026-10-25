import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/luucycle/scripts/worker_contract.py"
spec = importlib.util.spec_from_file_location("worker_contract", SCRIPT)
worker_contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = worker_contract
spec.loader.exec_module(worker_contract)


class WorkerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skill_path = Path(self.tmp.name) / "SKILL.md"
        self.skill_path.write_text("# Routed review skill\n", encoding="utf-8")
        self.skill = {"identity": "code-review", "path": str(self.skill_path),
                      "sha256": hashlib.sha256(self.skill_path.read_bytes()).hexdigest()}
        self.plan = {
            "approval": True,
            "target": {"run_id": "run_123456789abc", "task_id": "task_123456789abc",
                       "dispatch_id": "ctx_123456789abc", "terminal_id": "term_exact_handle"},
            "task": "Review the target diff and return evidence.", "skill": self.skill,
            "permissions": {"artifact_write": False, "report_write": False},
            "targets": ["skills/luucycle/scripts/worker_contract.py"],
            "model": {"agent_id": "codex", "cli": "Codex", "alias": "codex", "model": "gpt-6.1-sol"},
            "evidence": {"required": ["exact skill attestation", "review findings"],
                         "completion_criterion": "Report all findings with evidence.",
                         "storage": "existing_record", "report_path": None},
        }
        self.expectation = {"routed_skill": copy.deepcopy(self.skill),
                            "permissions": {"artifact_write": False, "report_write": False},
                            "storage": "existing_record"}

    def authority(self, **updates):
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        authority = {"complete": True, "source_verified": True,
                     "observed_at": now.isoformat().replace("+00:00", "Z"),
                     **self.plan["target"], "task_status": "dispatched",
                     "dispatch_status": "dispatched", "terminal_state": "active", "sealed": False}
        authority.update(updates)
        return authority, now

    def evidence(self, **updates):
        report = {"schema": "luucycle.task-evidence.v1", "task_id": self.plan["target"]["task_id"],
                  "dispatch_id": self.plan["target"]["dispatch_id"],
                  "routed_skill": copy.deepcopy(self.skill), "loaded_skill": copy.deepcopy(self.skill),
                  "writes": {"artifact": False, "report": False},
                  "storage": {"kind": "existing_record",
                              "ref": f"orca:task:{self.plan['target']['task_id']}:result"}}
        report.update(updates)
        return report

    def receipt(self, **updates):
        receipt = {"schema": "luucycle.worker-receipt.v1",
                   "task_id": self.plan["target"]["task_id"],
                   "dispatch_id": self.plan["target"]["dispatch_id"],
                   "worker_status": "DONE", "worker_done": True,
                   "task_evidence": self.evidence()}
        receipt.update(updates)
        return receipt

    def test_prompt_is_deterministic_and_contains_all_bound_fields(self):
        first = worker_contract.build_dispatch_prompt(self.plan)
        self.assertEqual(first, worker_contract.build_dispatch_prompt(self.plan))
        for value in ("run_123456789abc", "task_123456789abc", "ctx_123456789abc",
                      "term_exact_handle", self.skill["sha256"], "code-review",
                      "artifact_write", "gpt-6.1-sol", "Report all findings with evidence.",
                      "luucycle.task-evidence.v1", "task_evidence", "orca:task:task_123456789abc:result",
                      "worker_done", "subprocess.run([ORCA"):
            self.assertIn(value, first)
        with self.assertRaises(worker_contract.ContractError):
            worker_contract.build_dispatch_prompt({**self.plan, "approval": False})

    def test_native_launch_ids_can_be_bound_after_worker_start(self):
        unassigned = copy.deepcopy(self.plan)
        unassigned["target"].update(task_id=None, dispatch_id=None, terminal_id=None)
        prompt = worker_contract.build_dispatch_prompt(unassigned)
        self.assertIn("assigned by Orca", prompt)
        launch = {"complete": True, "source_verified": True, **self.plan["target"]}
        bound = worker_contract.bind_launch_ids(unassigned, launch)
        self.assertEqual(bound["target"], self.plan["target"])
        with self.assertRaisesRegex(worker_contract.ContractError, "different Run"):
            worker_contract.bind_launch_ids(unassigned, {**launch, "run_id": "run_ffffffffffff"})
        with self.assertRaisesRegex(worker_contract.ContractError, "native launch identity"):
            worker_contract.bind_launch_ids(unassigned, {**launch, "source_verified": False})

    def test_builder_fails_closed_on_skill_digest_change_and_insufficient_rights(self):
        self.skill_path.write_text("# Skill changed\n", encoding="utf-8")
        with self.assertRaisesRegex(worker_contract.ContractError, "digest changed"):
            worker_contract.build_dispatch_prompt(self.plan)
        self.skill_path.write_text("# Routed review skill\n", encoding="utf-8")
        bad = copy.deepcopy(self.plan)
        bad["evidence"].update(storage="artifact", report_path=str(Path(self.tmp.name) / "report.json"))
        with self.assertRaisesRegex(worker_contract.ContractError, "requires artifact and report write rights"):
            worker_contract.build_dispatch_prompt(bad)

    def test_current_task_evidence_schema_is_accepted_without_granting_acceptance(self):
        result = worker_contract.validate_return(self.expectation, self.receipt(),
                                                 task_id=self.plan["target"]["task_id"],
                                                 dispatch_id=self.plan["target"]["dispatch_id"],
                                                 source_complete=True)
        self.assertTrue(result["worker_done"])
        self.assertEqual(result["status"], "RECEIVED_TERMINAL")
        self.assertEqual(result["acceptance"], "EVIDENCE_REVIEW_NOT_ACCEPTED")
        self.assertEqual(result["task_evidence"]["status"], "EVIDENCE_REVIEW")

    def test_native_worker_done_payload_is_parsed_and_bound_without_manual_receipt(self):
        payload = {"taskId": self.plan["target"]["task_id"],
                   "dispatchId": self.plan["target"]["dispatch_id"],
                   "outcome": "succeeded", "task_evidence": self.evidence()}
        message = {"native_message": {"id": "msg_123", "type": "worker_done",
                                      "payload": json.dumps(payload)},
                   "parsed_payload": payload,
                   "ids": {"task": payload["taskId"], "dispatch": payload["dispatchId"]}}
        result = worker_contract.validate_native_worker_done(
            self.expectation, message, expected_task_id=payload["taskId"],
            expected_dispatch_id=payload["dispatchId"], source_complete=True)
        self.assertTrue(result["worker_done"])
        self.assertEqual(result["acceptance"], "EVIDENCE_REVIEW_NOT_ACCEPTED")
        foreign = copy.deepcopy(payload)
        foreign["dispatchId"] = "ctx_ffffffffffff"
        message["parsed_payload"] = foreign
        message["native_message"]["payload"] = json.dumps(foreign)
        result = worker_contract.validate_native_worker_done(
            self.expectation, message, expected_task_id=payload["taskId"],
            expected_dispatch_id=payload["dispatchId"], source_complete=True)
        self.assertEqual(result["status"], "STOP")
        self.assertEqual(result["acceptance"], "INCOMPLETE")

    def test_receipt_malformed_foreign_or_incomplete_evidence_does_not_accept(self):
        result = worker_contract.validate_return(self.expectation, self.receipt(worker_status="RUNNING"),
                                                 task_id=self.plan["target"]["task_id"],
                                                 dispatch_id=self.plan["target"]["dispatch_id"],
                                                 source_complete=True)
        self.assertFalse(result["worker_done"])
        self.assertEqual(result["acceptance"], "INCOMPLETE")
        foreign = self.receipt(task_evidence=self.evidence(task_id="task_ffffffffffff"))
        result = worker_contract.validate_return(self.expectation, foreign,
                                                 task_id=self.plan["target"]["task_id"],
                                                 dispatch_id=self.plan["target"]["dispatch_id"],
                                                 source_complete=True)
        self.assertTrue(result["worker_done"])
        self.assertEqual(result["status"], "RECEIVED_TERMINAL_EVIDENCE_INCOMPLETE")
        self.assertEqual(result["acceptance"], "INCOMPLETE")
        result = worker_contract.validate_return(self.expectation, self.receipt(),
                                                 task_id=self.plan["target"]["task_id"],
                                                 dispatch_id=self.plan["target"]["dispatch_id"],
                                                 source_complete=False)
        self.assertTrue(result["worker_done"])
        self.assertEqual(result["acceptance"], "INCOMPLETE")

    def test_fresh_exact_authority_routes_only_to_dispatch_address(self):
        authority, now = self.authority(task_status="dispatched", dispatch_status="dispatched", terminal_state="active")
        preflight = worker_contract.preflight_dispatch_message(self.plan, authority, "Status update",
                                                               now=now, max_age_seconds=5)
        self.assertEqual(preflight["recipient"], "dispatch:ctx_123456789abc")
        self.assertEqual(preflight["identity"], self.plan["target"])
        self.assertFalse(preflight["atomic"])

    def test_controlled_send_reads_fresh_authority_and_passes_exact_dispatch_target(self):
        authority, now = self.authority()
        calls = []
        result = worker_contract.controlled_dispatch_send(
            self.plan, "Follow-up", read_fresh_authority=lambda: calls.append("read") or authority,
            send=lambda envelope: calls.append(envelope["recipient"]) or {"accepted": True}, now=now)
        self.assertEqual(calls, ["read", "dispatch:ctx_123456789abc"])
        self.assertEqual(result["status"], "SEND_ATTEMPTED")
        self.assertEqual(result["acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["atomic"])

    def test_stale_or_mismatched_identity_and_settled_authority_refuse_send(self):
        authority, now = self.authority()
        stale = dict(authority, observed_at="2026-10-25T11:59:00Z")
        mismatches = [stale, dict(authority, dispatch_id="ctx_ffffffffffff"),
                      dict(authority, task_id="task_ffffffffffff"), dict(authority, run_id="run_ffffffffffff"),
                      dict(authority, terminal_id="term_other")]
        for changed in mismatches:
            with self.subTest(changed=changed):
                with self.assertRaises(worker_contract.ContractError):
                    worker_contract.preflight_dispatch_message(self.plan, changed, "hello", now=now)
        for changed in (dict(authority, sealed=True), dict(authority, task_status="completed"),
                        dict(authority, task_status="running"), dict(authority, task_status="queued"),
                        dict(authority, dispatch_status="failed"), dict(authority, dispatch_status="running"),
                        dict(authority, terminal_state="released"), dict(authority, terminal_state="live"),
                        dict(authority, source_verified=False), dict(authority, complete=False)):
            with self.subTest(changed=changed):
                with self.assertRaises(worker_contract.ContractError):
                    worker_contract.preflight_dispatch_message(self.plan, changed, "hello", now=now)

    def test_send_callback_is_never_called_after_failed_fresh_check(self):
        authority, now = self.authority(sealed=True)
        sent = []
        with self.assertRaises(worker_contract.ContractError):
            worker_contract.controlled_dispatch_send(self.plan, "late follow-up",
                read_fresh_authority=lambda: authority, send=lambda envelope: sent.append(envelope), now=now)
        self.assertEqual(sent, [])

    def test_owned_live_send_refuses_settlement_before_mutation(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import orca_inbox
        authority, _ = self.authority(sealed=True, task_status="completed", dispatch_status="completed",
                                      terminal_state="released")
        native = {"status": "REVIEW", "source_verified": True, "complete": True, "sealed": True,
                  "observed_at": datetime.now(timezone.utc).isoformat(),
                  "ids": {"run": authority["run_id"], "task": authority["task_id"],
                          "dispatch": authority["dispatch_id"], "assignee": authority["terminal_id"]},
                  **{k: authority[k] for k in ("task_status", "dispatch_status", "terminal_state")}}
        with patch.object(orca_inbox, "read_dispatch_authority", return_value=native), \
             patch.object(orca_inbox.adapter, "_capture") as send:
            result = worker_contract.send_orca_message(self.plan, "late message", executable=sys.executable,
                capture_root=self.tmp.name, capture_authorized=True, send_authorized=True)
        self.assertEqual(result["status"], "STOP")
        self.assertIs(result["sent"], False)
        send.assert_not_called()

    def test_owned_live_send_requires_authorization_before_any_read(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import orca_inbox
        with patch.object(orca_inbox, "read_dispatch_authority") as read:
            result = worker_contract.send_orca_message(self.plan, "message", executable=sys.executable,
                                                       capture_root=self.tmp.name)
        self.assertEqual(result["status"], "STOP")
        read.assert_not_called()

    def test_owned_live_send_matches_native_receipt_and_keeps_ambiguity(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import orca_inbox
        t = self.plan["target"]
        observation = {"status": "REVIEW", "source_verified": True, "complete": True, "sealed": False,
                       "runtime_id": "trusted-runtime", "observed_at": datetime.now(timezone.utc).isoformat(),
                       "ids": {"run": t["run_id"], "task": t["task_id"], "dispatch": t["dispatch_id"],
                               "assignee": t["terminal_id"]},
                       "task_status": "dispatched", "dispatch_status": "dispatched", "terminal_state": "active"}
        native = {"ok": True, "_meta": {"runtimeId": "trusted-runtime"},
                  "result": {"message": {"id": "msg_0123456789ab", "run_id": t["run_id"],
                    "to_handle": "dispatch:" + t["dispatch_id"], "type": "status", "body": "guidance",
                    "payload": __import__("json").dumps({"taskId": t["task_id"], "dispatchId": t["dispatch_id"]})}}}
        with patch.object(orca_inbox, "read_dispatch_authority", return_value=observation), \
             patch.object(orca_inbox.adapter, "_capture", return_value=(__import__("json").dumps(native).encode(), {})) as send:
            result = worker_contract.send_orca_message(self.plan, "guidance", executable=sys.executable,
                capture_root=self.tmp.name, capture_authorized=True, send_authorized=True)
            self.assertEqual(result["status"], "ENQUEUED", result)
            self.assertTrue(result["sent"])
            self.assertIn("dispatch:" + t["dispatch_id"], send.call_args.args[0])
            native["result"]["message"]["body"] = "different guidance"
            send.return_value = (__import__("json").dumps(native).encode(), {})
            result = worker_contract.send_orca_message(self.plan, "guidance", executable=sys.executable,
                capture_root=self.tmp.name, capture_authorized=True, send_authorized=True)
            self.assertEqual(result["status"], "STOP")
            self.assertIsNone(result["sent"], "mismatched reply cannot prove the mutation did not happen")

    def test_cli_preflight_is_read_only_and_reports_stop_for_sealed_authority(self):
        authority, _ = self.authority(observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        plan_file = Path(self.tmp.name) / "plan.json"
        authority_file = Path(self.tmp.name) / "authority.json"
        plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        authority_file.write_text(json.dumps(authority), encoding="utf-8")
        output = io.StringIO()
        args = ["preflight", "--plan", str(plan_file), "--authority", str(authority_file), "--message", "Check"]
        with contextlib.redirect_stdout(output):
            result = worker_contract.main(args)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["recipient"], "dispatch:ctx_123456789abc")
        authority_file.write_text(json.dumps({**authority, "sealed": True}), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = worker_contract.main(args)
        self.assertEqual(result, 2)
        self.assertFalse(json.loads(output.getvalue())["sent"])


if __name__ == "__main__":
    unittest.main()
