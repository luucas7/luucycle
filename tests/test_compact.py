import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
from compact import encode, project
from synthetic_returns import envelope, record, scenario
from benchmark_compact import CRITICAL, measure


SCRIPT = Path(__file__).resolve().parents[1] / "skills/luucycle/scripts/compact.py"


class CompactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets = scenario()

    def cli(self, *args, raw=None):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=raw,
                                capture_output=True, check=False)
        self.assertEqual(result.stderr, b"")
        return result.returncode, json.loads(result.stdout)

    def test_same_inputs_exact_critical_values_and_accounting(self):
        for name, packet in self.packets.items():
            with self.subTest(kind=name):
                raw = encode(packet)
                result = project(raw, f"fixture:{name}.json")
                self.assertEqual(result["source"]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(result["actual_count"], len(packet["items"]))
                self.assertEqual(sum(result["counts"].values()), len(packet["items"]))
                self.assertEqual(len(result["items"]), len(packet["items"]))
                for before, after in zip(packet["items"], result["items"]):
                    self.assertEqual(set(after), set(CRITICAL))
                    for key in CRITICAL:
                        self.assertEqual(encode(after[key]), encode(before[key]), key)
                for key in ("schema", "kind", "complete", "expected_count", "errors"):
                    self.assertEqual(result[key], packet[key])

    def test_large_list_reduction_at_least_80_percent(self):
        rows = measure()
        self.assertGreaterEqual(rows[0][1], 90)
        self.assertGreaterEqual(rows[0][4], 80)

    def test_distinct_ids_multiple_workers_failure_partial_state(self):
        workers = self.packets["workers"]["items"]
        self.assertGreaterEqual(len(workers), 3)
        self.assertIn("FAILED", [item["status"] for item in workers])
        for item in workers:
            ids = item["ids"]
            self.assertEqual(len(set(ids.values())), len(ids))
            self.assertNotEqual(ids["dispatch"], ids["task"])
            self.assertNotEqual(ids["worker"], item["controls"]["primary_agent"])
        partial = project(encode(self.packets["orca"]), "fixture:orca.json")
        self.assertEqual(partial["status"], "STOP")
        self.assertIn("incomplete_result", partial["issues"])
        self.assertIn("count_mismatch", partial["issues"])
        self.assertEqual(project(encode(self.packets["workers"]), "fixture:workers.json")["status"], "STOP")

    def test_long_critical_values_and_future_controls_are_never_truncated(self):
        item = record(1)
        long_value = "preuve-échec-" * 5000
        for key in ("evidence", "changes", "blockers"):
            item[key] = [{"exact": long_value}]
        item["decision"] = {"exact": long_value}
        item["controls"]["future_safety_field"] = {"nested": [long_value, {"keep": True}]}
        result = project(encode(envelope("tasks", [item])), "fixture:long.json")
        for key in CRITICAL:
            self.assertEqual(result["items"][0][key], item[key])
        self.assertEqual(result["status"], "STOP")

    def test_each_incomplete_count_or_error_stops_independently(self):
        base = envelope("tasks", [record(1)])
        for key, value, issue in (("complete", False, "incomplete_result"),
                                  ("expected_count", 2, "count_mismatch"),
                                  ("errors", [{"exit": 7, "stderr": "synthetic failure"}], "unresolved_errors")):
            packet = deepcopy(base)
            packet[key] = value
            result = project(encode(packet), "fixture:bad.json")
            self.assertEqual(result["status"], "STOP")
            self.assertIn(issue, result["issues"])
            self.assertEqual(result["items"][0]["ids"], base["items"][0]["ids"])

    def test_blocked_failed_unknown_paused_and_blockers_stop(self):
        for status in ("BLOCKED", "FAILED", "UNKNOWN", "PAUSED"):
            item = record(1, status=status)
            self.assertEqual(project(encode(envelope("workers", [item])), "fixture:x")["status"], "STOP")
        item = record(1, status="DONE")
        item["blockers"] = ["unresolved"]
        self.assertEqual(project(encode(envelope("workers", [item])), "fixture:x")["status"], "STOP")

    def test_missing_unknown_malformed_fields_fail_closed(self):
        base = envelope("tasks", [record(1)])
        cases = []
        for key in CRITICAL + ("detail",):
            packet = deepcopy(base)
            del packet["items"][0][key]
            cases.append(packet)
        for key, value in (("schema", "future"), ("kind", "future"), ("complete", None),
                           ("expected_count", True), ("expected_count", -1),
                           ("items", {}), ("errors", "hidden error"), ("new_control", True)):
            packet = deepcopy(base)
            packet[key] = value
            cases.append(packet)
        for key, value in (("status", "unrecognized"), ("id", ""), ("ids", {}),
                           ("ids", {"task": 42}), ("decision", "guess"), ("evidence", "lost"),
                           ("controls", []), ("detail", []), ("unknown_safety", True)):
            packet = deepcopy(base)
            packet["items"][0][key] = value
            cases.append(packet)
        for packet in cases:
            with self.subTest(packet_key=list(packet)):
                result = project(encode(packet), "fixture:bad.json")
                self.assertEqual(result["status"], "STOP")
                self.assertNotIn("items", result)

    def test_invalid_json_duplicate_keys_nonfinite_and_duplicate_ids(self):
        for raw in (b"{", b'{} {}', b'\xff', b'{"secret":"DO_NOT_ECHO", "secret":2}', b'{"x":NaN}',
                    b'{"x":1e999}', b'{"x":' + b'9' * 5000 + b'}'):
            result = project(raw, "fixture:invalid.json")
            self.assertEqual(result["status"], "STOP")
            self.assertNotIn("DO_NOT_ECHO", encode(result).decode())
        item = record(1)
        self.assertEqual(project(encode(envelope("tasks", [item, item])), "fixture:duplicate")["status"], "STOP")

    def test_empty_verified_scope_is_distinct_from_incomplete_scope(self):
        self.assertEqual(project(encode(envelope("tasks", [])), "fixture:empty")["status"], "REVIEW")
        self.assertEqual(project(encode(envelope("tasks", [], complete=False)), "fixture:partial")["status"], "STOP")

    def test_native_orca_shape_is_not_silently_treated_as_normalized(self):
        raw = encode({"ok": True, "result": {"workers": [], "page": {"hasMore": True}}})
        result = project(raw, "fixture:native-orca.json")
        self.assertEqual(result["status"], "STOP")
        self.assertNotIn("items", result)
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_precision_loss_or_invalid_unicode_stops_instead_of_changing_controls(self):
        item = record(1)
        item["controls"]["future_value"] = "numeric-marker"
        raw = encode(envelope("tasks", [item]))
        for literal in (b"0.12345678901234567890123456789", b"1e-999", b'"\\ud800"'):
            result = project(raw.replace(b'"numeric-marker"', literal), "fixture:unsupported-value.json")
            self.assertEqual(result["status"], "STOP")
        supported = raw.replace(b'"numeric-marker"', b"0.125")
        result = project(supported, "fixture:exact-value.json")
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["items"][0]["controls"]["future_value"], 0.125)

    def test_full_exact_id_lookup_keeps_details_and_source_unchanged(self):
        raw = encode(self.packets["tasks"])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "retained.json"
            source.write_bytes(raw)
            before = set(Path(directory).iterdir())
            code, projected = self.cli("project", str(source))
            self.assertEqual(code, 0)
            self.assertNotIn("acceptance_checks", json.dumps(projected))
            code, item = self.cli("get", str(source), "--id", "record:SYNTH-0096", "--sha256", projected["source"]["sha256"])
            self.assertEqual(code, 0)
            self.assertEqual(item["item"], self.packets["tasks"]["items"][95])
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(set(Path(directory).iterdir()), before)

    def test_detailed_worker_reports_remain_in_artifact_and_are_readable_by_id(self):
        packet = self.packets["workers"]
        raw = encode(packet)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "reports.json"
            source.write_bytes(raw)
            code, projection = self.cli("project", str(source))
            self.assertEqual(code, 2)
            for original in packet["items"]:
                code, result = self.cli("get", str(source), "--id", original["id"],
                                        "--sha256", projection["source"]["sha256"])
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "STOP")
                self.assertEqual(result["mode"], "INSPECT")
                self.assertEqual(encode(result["item"]), encode(original))
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_targeted_lookup_rejects_prefix_missing_id_changed_artifact_and_duplicates(self):
        raw = encode(envelope("tasks", [record(1)]))
        digest = hashlib.sha256(raw).hexdigest()
        for identity, checksum in (("record:SYNTH", digest), ("absent", digest), ("record:SYNTH-0001", "0" * 64)):
            code, result = self.cli("get", "-", "--source-ref", "fixture:message:01", "--id", identity, "--sha256", checksum, raw=raw)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "STOP")
        duplicate = encode(envelope("tasks", [record(1), record(1)]))
        code, result = self.cli("get", "-", "--source-ref", "fixture:duplicate", "--id", "record:SYNTH-0001",
                                "--sha256", hashlib.sha256(duplicate).hexdigest(), raw=duplicate)
        self.assertEqual(code, 2)

    def test_audit_style_pipe_has_reference_and_no_file_write(self):
        raw = encode(self.packets["workers"])
        code, projected = self.cli("project", "-", "--source-ref", "fixture:existing-message:01", raw=raw)
        self.assertEqual(code, 2)
        self.assertEqual(projected["source"]["ref"], "fixture:existing-message:01")
        self.assertEqual(projected["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        code, result = self.cli("project", "-", raw=raw)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "STOP")

    def test_get_partial_item_preserves_stop_and_allows_inspection(self):
        raw = encode(self.packets["orca"])
        code, result = self.cli("get", "-", "--source-ref", "fixture:state:01", "--id", "observation:SYNTH-0003",
                                "--sha256", hashlib.sha256(raw).hexdigest(), raw=raw)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "STOP")
        self.assertEqual(result["mode"], "INSPECT")
        self.assertFalse(result["complete"])
        self.assertNotEqual(result["actual_count"], result["expected_count"])
        self.assertEqual(result["errors"], self.packets["orca"]["errors"])

    def test_relay_keeps_approvals_ids_verified_state_incidents_and_next_decision(self):
        packet = self.packets["relay"]
        item = project(encode(packet), "fixture:relay")["items"][0]
        original = packet["items"][0]
        for key in ("approvals", "verified_state", "incidents"):
            self.assertEqual(item["controls"][key], original["controls"][key])
            bad = deepcopy(packet)
            del bad["items"][0]["controls"][key]
            self.assertEqual(project(encode(bad), "fixture:bad")["status"], "STOP")
        self.assertEqual(item["ids"], original["ids"])
        self.assertEqual(item["decision"], original["decision"])


if __name__ == "__main__":
    unittest.main()
