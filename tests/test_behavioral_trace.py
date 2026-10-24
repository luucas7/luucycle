#!/usr/bin/env python3
"""Unit tests for offline behavioral trace collector and mock event runner.

Verifies deterministic capture of action types, target IDs, payload digests,
immutable event storage, query methods, and synthetic lifecycle scenarios.
"""

from __future__ import annotations

import hashlib
import sys
import time
import unittest
from pathlib import Path
from types import MappingProxyType

# Ensure test fixtures and scripts are on sys.path regardless of execution mode
_TESTS_DIR = str(Path(__file__).resolve().parent)
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "skills" / "luucycle" / "scripts")

for directory in (_TESTS_DIR, _SCRIPTS_DIR):
    if directory not in sys.path:
        sys.path.insert(0, directory)

from behavioral_trace import (
    ACTION_DISPATCH,
    ACTION_INPUT,
    ACTION_PROMPT,
    ACTION_READ_DETAIL,
    ACTION_READ_PROJECTION,
    ACTION_RELEASE_TERMINAL,
    ALL_INVARIANTS,
    INVARIANT_IMMEDIATE_TERMINAL_RELEASE,
    INVARIANT_PROJECTION_BOUNDARY_RESPECT,
    INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS,
    VALID_ACTIONS,
    BehavioralInvariantChecker,
    InvariantViolation,
    MockOrchestratorRunner,
    ScenarioComparison,
    TraceCollector,
    TraceEvent,
    check_immediate_terminal_release,
    check_projection_boundary_respect,
    check_zero_post_settlement_prompts,
    compare_scenarios,
    compute_digest_and_size,
    format_violations_report,
    verify_all_invariants,
)
from compact import encode
from synthetic_returns import record, worker_returns


class BehavioralTraceTests(unittest.TestCase):
    def test_compute_digest_and_size_types(self):
        # None
        d, s = compute_digest_and_size(None)
        self.assertIsNone(d)
        self.assertEqual(s, 0)

        # bytes
        payload_bytes = b"hello trace world"
        d, s = compute_digest_and_size(payload_bytes)
        self.assertEqual(d, hashlib.sha256(payload_bytes).hexdigest())
        self.assertEqual(s, len(payload_bytes))

        # string
        payload_str = "utf-8 string with accents: éàï"
        d, s = compute_digest_and_size(payload_str)
        raw = payload_str.encode("utf-8")
        self.assertEqual(d, hashlib.sha256(raw).hexdigest())
        self.assertEqual(s, len(raw))

        # dict
        payload_dict = {"worker": "worker:01", "active": True}
        d, s = compute_digest_and_size(payload_dict)
        raw_encoded = encode(payload_dict)
        self.assertEqual(d, hashlib.sha256(raw_encoded).hexdigest())
        self.assertEqual(s, len(raw_encoded))

    def test_trace_event_immutability(self):
        controls = {"phase": "Execution", "primary_agent": "roster:worker:01"}
        metadata = {"category": "test"}
        event = TraceEvent.create(
            seq=0,
            action_type=ACTION_DISPATCH,
            timestamp="2026-10-24T09:00:00.000Z",
            worker_id="worker:SYNTH-0001",
            task_id="task:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            payload={"instruction": "run task"},
            controls=controls,
            metadata=metadata,
        )

        # Cannot modify fields on frozen dataclass
        with self.assertRaises(AttributeError):
            event.status = "MUTATED"  # type: ignore

        with self.assertRaises(AttributeError):
            event.seq = 999  # type: ignore

        # Cannot mutate mappingproxy
        self.assertIsInstance(event.controls, MappingProxyType)
        with self.assertRaises(TypeError):
            event.controls["phase"] = "Auditing"  # type: ignore

        with self.assertRaises(TypeError):
            event.metadata["new_key"] = "forbidden"  # type: ignore

        # Mutating original dictionary does not alter event
        controls["phase"] = "ModifiedExternally"
        self.assertEqual(event.controls["phase"], "Execution")

    def test_trace_collector_captures_all_authoritative_action_types(self):
        collector = TraceCollector()

        # 1. Dispatch
        ev_dispatch = collector.record(
            action_type=ACTION_DISPATCH,
            worker_id="worker:SYNTH-0001",
            task_id="task:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            payload={"cmd": "start"},
            status="RUNNING",
        )
        self.assertEqual(ev_dispatch.seq, 0)
        self.assertEqual(ev_dispatch.action_type, ACTION_DISPATCH)
        self.assertEqual(ev_dispatch.worker_id, "worker:SYNTH-0001")
        self.assertEqual(ev_dispatch.task_id, "task:SYNTH-0001")
        self.assertEqual(ev_dispatch.terminal_id, "terminal:SYNTH-0001")
        self.assertEqual(ev_dispatch.status, "RUNNING")
        self.assertIsNotNone(ev_dispatch.payload_digest)
        self.assertGreater(ev_dispatch.payload_bytes, 0)

        # 2. Input
        ev_input = collector.record(
            action_type=ACTION_INPUT,
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            payload="user response text",
            status="OK",
        )
        self.assertEqual(ev_input.seq, 1)
        self.assertEqual(ev_input.action_type, ACTION_INPUT)
        self.assertEqual(ev_input.status, "OK")

        # 3. Prompt
        ev_prompt = collector.record(
            action_type=ACTION_PROMPT,
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            payload="prompt instruction",
            status="OK",
        )
        self.assertEqual(ev_prompt.seq, 2)
        self.assertEqual(ev_prompt.action_type, ACTION_PROMPT)

        # 4. Read projection
        ev_proj = collector.record(
            action_type=ACTION_READ_PROJECTION,
            worker_id="worker:SYNTH-0001",
            task_id="task:SYNTH-0001",
            payload={"schema": "luucycle.return.v1", "status": "DONE"},
            status="DONE",
        )
        self.assertEqual(ev_proj.seq, 3)
        self.assertEqual(ev_proj.action_type, ACTION_READ_PROJECTION)
        self.assertEqual(ev_proj.status, "DONE")

        # 5. Read detail
        ev_detail = collector.record(
            action_type=ACTION_READ_DETAIL,
            worker_id="worker:SYNTH-0001",
            task_id="task:SYNTH-0001",
            payload={"report": "full detailed diagnostic report"},
            status="DONE",
        )
        self.assertEqual(ev_detail.seq, 4)
        self.assertEqual(ev_detail.action_type, ACTION_READ_DETAIL)

        # 6. Release terminal
        ev_release = collector.record(
            action_type=ACTION_RELEASE_TERMINAL,
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            status="SEALED",
        )
        self.assertEqual(ev_release.seq, 5)
        self.assertEqual(ev_release.action_type, ACTION_RELEASE_TERMINAL)
        self.assertEqual(ev_release.status, "SEALED")

        # Verify all action types are valid
        recorded_actions = {e.action_type for e in collector}
        self.assertEqual(recorded_actions, VALID_ACTIONS)
        self.assertEqual(len(collector), 6)

    def test_trace_collector_query_methods(self):
        collector = TraceCollector()
        collector.record(ACTION_DISPATCH, worker_id="worker:A", task_id="task:1", terminal_id="term:1", status="RUNNING")
        collector.record(ACTION_READ_PROJECTION, worker_id="worker:A", task_id="task:1", terminal_id="term:1", status="DONE")
        collector.record(ACTION_RELEASE_TERMINAL, worker_id="worker:A", task_id="task:1", terminal_id="term:1", status="SEALED")

        collector.record(ACTION_DISPATCH, worker_id="worker:B", task_id="task:2", terminal_id="term:2", status="RUNNING")
        collector.record(ACTION_READ_PROJECTION, worker_id="worker:B", task_id="task:2", terminal_id="term:2", status="BLOCKED")
        collector.record(ACTION_RELEASE_TERMINAL, worker_id="worker:B", task_id="task:2", terminal_id="term:2", status="SEALED")
        collector.record(ACTION_INPUT, worker_id="worker:B", terminal_id="term:2", status="STOP")

        # Query by worker
        events_a = collector.events_by_worker("worker:A")
        self.assertEqual(len(events_a), 3)
        self.assertTrue(all(e.worker_id == "worker:A" for e in events_a))

        events_b = collector.events_by_worker("worker:B")
        self.assertEqual(len(events_b), 4)

        # Query by action
        dispatches = collector.events_by_action(ACTION_DISPATCH)
        self.assertEqual(len(dispatches), 2)
        self.assertEqual([e.worker_id for e in dispatches], ["worker:A", "worker:B"])

        # Query by task
        task_1_events = collector.events_by_task("task:1")
        self.assertEqual(len(task_1_events), 3)

        # Query by terminal
        term_2_events = collector.events_by_terminal("term:2")
        self.assertEqual(len(term_2_events), 4)

        # Actions after status
        # For worker:A, after DONE: only release_terminal
        after_done_a = collector.actions_after_status("worker:A", "DONE")
        self.assertEqual(len(after_done_a), 1)
        self.assertEqual(after_done_a[0].action_type, ACTION_RELEASE_TERMINAL)

        # For worker:B, after BLOCKED: release_terminal and input
        after_blocked_b = collector.actions_after_status("worker:B", "BLOCKED")
        self.assertEqual(len(after_blocked_b), 2)
        self.assertEqual([e.action_type for e in after_blocked_b], [ACTION_RELEASE_TERMINAL, ACTION_INPUT])

        # Global subsequent events (target_worker_only=False)
        all_after_done_a = collector.actions_after_status("worker:A", "DONE", target_worker_only=False)
        self.assertEqual(len(all_after_done_a), 5)  # release_terminal(A) + 4 events for B

        # has_action_after checks
        self.assertFalse(collector.has_action_after("worker:A", "DONE", [ACTION_INPUT, ACTION_PROMPT]))
        self.assertTrue(collector.has_action_after("worker:B", "BLOCKED", [ACTION_INPUT]))
        self.assertFalse(collector.has_action_after("worker:B", "BLOCKED", [ACTION_PROMPT]))

        # Non-existent status returns empty
        self.assertEqual(collector.actions_after_status("worker:A", "NON_EXISTENT"), [])

    def test_collector_summary_metrics(self):
        collector = TraceCollector()
        collector.record(ACTION_DISPATCH, worker_id="worker:1", task_id="task:1", terminal_id="term:1", payload="abc")
        collector.record(ACTION_RELEASE_TERMINAL, worker_id="worker:1", task_id="task:1", terminal_id="term:1", status="SEALED")

        metrics = collector.summary_metrics()
        self.assertEqual(metrics["turn_count"], 2)
        self.assertEqual(metrics["total_payload_bytes"], 3)
        self.assertEqual(metrics["action_counts"], {ACTION_DISPATCH: 1, ACTION_RELEASE_TERMINAL: 1})
        self.assertEqual(metrics["workers"], ["worker:1"])
        self.assertEqual(metrics["tasks"], ["task:1"])
        self.assertEqual(metrics["terminals"], ["term:1"])

    def test_nominal_scenario_lifecycle(self):
        runner = MockOrchestratorRunner()
        collector = runner.run_nominal_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
        )

        events = collector.get_events()
        self.assertEqual(len(events), 3)

        # Event 0: Dispatch
        self.assertEqual(events[0].action_type, ACTION_DISPATCH)
        self.assertEqual(events[0].worker_id, "worker:SYNTH-0001")
        self.assertEqual(events[0].task_id, "task:SYNTH-0001")
        self.assertEqual(events[0].terminal_id, "terminal:SYNTH-0001")
        self.assertEqual(events[0].status, "RUNNING")

        # Event 1: Read projection (status DONE)
        self.assertEqual(events[1].action_type, ACTION_READ_PROJECTION)
        self.assertEqual(events[1].status, "DONE")
        self.assertIsNotNone(events[1].payload_digest)

        # Event 2: Immediate terminal release
        self.assertEqual(events[2].action_type, ACTION_RELEASE_TERMINAL)
        self.assertEqual(events[2].status, "SEALED")
        self.assertEqual(events[2].terminal_id, "terminal:SYNTH-0001")

        # Invariant check: zero follow-up inputs or prompts after DONE
        self.assertFalse(collector.has_action_after("worker:SYNTH-0001", "DONE", [ACTION_INPUT, ACTION_PROMPT]))

        # Monotonic timestamps
        self.assertLess(events[0].timestamp, events[1].timestamp)
        self.assertLess(events[1].timestamp, events[2].timestamp)

    def test_verbose_scenario_compact_vs_detail_payload(self):
        # Scenario without detail read
        runner_compact = MockOrchestratorRunner()
        collector_compact = runner_compact.run_verbose_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            inspect_detail=False,
        )
        self.assertEqual(len(collector_compact), 3)
        self.assertEqual([e.action_type for e in collector_compact], [
            ACTION_DISPATCH, ACTION_READ_PROJECTION, ACTION_RELEASE_TERMINAL
        ])

        # Scenario with detail read
        runner_detailed = MockOrchestratorRunner()
        collector_detailed = runner_detailed.run_verbose_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            inspect_detail=True,
        )
        self.assertEqual(len(collector_detailed), 4)
        self.assertEqual([e.action_type for e in collector_detailed], [
            ACTION_DISPATCH, ACTION_READ_PROJECTION, ACTION_READ_DETAIL, ACTION_RELEASE_TERMINAL
        ])

        proj_event = collector_detailed.events_by_action(ACTION_READ_PROJECTION)[0]
        detail_event = collector_detailed.events_by_action(ACTION_READ_DETAIL)[0]

        # The raw detail payload is substantial (detailed synthetic report + logs)
        self.assertGreater(detail_event.payload_bytes, 1000)
        self.assertIsNotNone(proj_event.payload_digest)
        self.assertIsNotNone(detail_event.payload_digest)

    def test_warning_fallback_scenario(self):
        runner = MockOrchestratorRunner()
        collector = runner.run_warning_fallback_scenario(
            task_id="task:SYNTH-0003",
            primary_worker_id="worker:SYNTH-0003",
            primary_terminal_id="terminal:SYNTH-0003",
            fallback_worker_id="worker:SYNTH-0003-fallback",
            fallback_terminal_id="terminal:SYNTH-0003-fallback",
        )

        events = collector.get_events()
        # Expect 6 events:
        # dispatch(primary) -> read_projection(primary, BLOCKED) -> release_terminal(primary)
        # dispatch(fallback) -> read_projection(fallback, DONE) -> release_terminal(fallback)
        self.assertEqual(len(events), 6)

        # Primary lifecycle
        self.assertEqual(events[0].worker_id, "worker:SYNTH-0003")
        self.assertEqual(events[0].action_type, ACTION_DISPATCH)

        self.assertEqual(events[1].worker_id, "worker:SYNTH-0003")
        self.assertEqual(events[1].action_type, ACTION_READ_PROJECTION)
        self.assertEqual(events[1].status, "BLOCKED")

        self.assertEqual(events[2].worker_id, "worker:SYNTH-0003")
        self.assertEqual(events[2].action_type, ACTION_RELEASE_TERMINAL)
        self.assertEqual(events[2].terminal_id, "terminal:SYNTH-0003")

        # Fallback dispatched to fresh terminal
        self.assertEqual(events[3].worker_id, "worker:SYNTH-0003-fallback")
        self.assertEqual(events[3].action_type, ACTION_DISPATCH)
        self.assertEqual(events[3].terminal_id, "terminal:SYNTH-0003-fallback")
        self.assertNotEqual(events[3].terminal_id, events[0].terminal_id)

        # Fallback completes DONE and releases terminal
        self.assertEqual(events[4].status, "DONE")
        self.assertEqual(events[5].action_type, ACTION_RELEASE_TERMINAL)
        self.assertEqual(events[5].terminal_id, "terminal:SYNTH-0003-fallback")

        # Confirm primary terminal was released before fallback was dispatched
        primary_release_seq = events[2].seq
        fallback_dispatch_seq = events[3].seq
        self.assertLess(primary_release_seq, fallback_dispatch_seq)

    def test_post_completion_input_rejection_with_compact_check_input(self):
        runner = MockOrchestratorRunner()
        collector, rejected_event = runner.run_post_completion_input_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            input_payload="cat << 'EOF' > unexpected_command\nEOF",
        )

        self.assertEqual(len(collector), 4)

        # Verify the rejected event
        self.assertEqual(rejected_event.action_type, ACTION_INPUT)
        self.assertEqual(rejected_event.status, "STOP")
        self.assertTrue(rejected_event.metadata.get("rejected"))
        self.assertEqual(
            rejected_event.metadata.get("diagnostic"),
            "worker is sealed; post-completion input is rejected",
        )

        # check_input payload is preserved in metadata
        check_input_meta = rejected_event.metadata.get("check_input")
        self.assertIsNotNone(check_input_meta)
        self.assertEqual(check_input_meta.get("status"), "STOP")
        self.assertTrue(check_input_meta.get("sealed"))

        # Invariant query confirms post-DONE input attempt occurred and was marked STOP
        after_done = collector.actions_after_status("worker:SYNTH-0001", "DONE")
        self.assertEqual(len(after_done), 2)
        self.assertEqual([e.action_type for e in after_done], [ACTION_RELEASE_TERMINAL, ACTION_INPUT])
        self.assertEqual(after_done[1].status, "STOP")

    def test_prompt_post_completion_rejection_without_return_payload(self):
        runner = MockOrchestratorRunner()
        collector = runner.collector

        # Dispatch and settle worker directly in collector
        runner.dispatch("task:1", "worker:1", "terminal:1")
        collector.record(ACTION_READ_PROJECTION, worker_id="worker:1", task_id="task:1", status="DONE")
        runner.release_terminal("worker:1", "terminal:1")

        # Prompt worker without passing explicit return_payload
        # Runner checks prior collector events and rejects fail-closed
        prompt_event = runner.prompt("worker:1", "please do more work", terminal_id="terminal:1")
        self.assertEqual(prompt_event.action_type, ACTION_PROMPT)
        self.assertEqual(prompt_event.status, "STOP")
        self.assertTrue(prompt_event.metadata.get("rejected"))
        self.assertEqual(prompt_event.metadata.get("diagnostic"), "worker is sealed; post-completion input is rejected")

    def test_active_worker_input_is_accepted(self):
        runner = MockOrchestratorRunner()
        raw_worker = record(1, status="RUNNING")
        raw_worker["id"] = "report:SYNTH-0001"
        raw_worker["ids"]["worker"] = "worker:SYNTH-0001"
        active_packet = {"schema": "luucycle.return.v1", "kind": "workers", "complete": True,
                         "expected_count": 1, "items": [raw_worker], "errors": []}

        runner.dispatch("task:SYNTH-0001", "worker:SYNTH-0001", "terminal:SYNTH-0001", status="RUNNING")
        input_event = runner.send_input(
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            payload="valid in-flight instruction",
            return_payload=active_packet,
        )
        self.assertEqual(input_event.status, "OK")
        self.assertFalse(input_event.metadata.get("rejected", False))

    def test_execution_speed_is_subsecond_offline(self):
        runner = MockOrchestratorRunner()
        start = time.perf_counter()

        # Run 50 iterations of nominal and warning scenarios
        for _ in range(50):
            r = MockOrchestratorRunner()
            r.run_nominal_scenario()
            r.run_warning_fallback_scenario()
            r.run_post_completion_input_scenario()

        duration = time.perf_counter() - start
        # 150 scenario simulations must complete well under 1 second
        self.assertLess(duration, 1.0)

    def test_invariant_violation_structure_and_formatting(self):
        violation = InvariantViolation(
            invariant_name=INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS,
            seq=3,
            timestamp="2026-10-24T09:00:00.300Z",
            action_type=ACTION_PROMPT,
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            task_id="task:SYNTH-0001",
            diagnostic="Offending post-settlement prompt was dispatched.",
        )

        self.assertEqual(violation.invariant_name, INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS)
        self.assertEqual(violation.invariant, INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS)
        self.assertEqual(violation.seq, 3)
        self.assertEqual(violation.line, 4)
        self.assertEqual(violation.timestamp, "2026-10-24T09:00:00.300Z")
        self.assertEqual(violation.action_type, ACTION_PROMPT)
        self.assertEqual(violation.worker_id, "worker:SYNTH-0001")
        self.assertEqual(violation.terminal_id, "terminal:SYNTH-0001")
        self.assertEqual(violation.task_id, "task:SYNTH-0001")

        report = violation.format_report()
        self.assertIn("seq=3", report)
        self.assertIn("line=4", report)
        self.assertIn("2026-10-24T09:00:00.300Z", report)
        self.assertIn(INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS, report)
        self.assertIn(ACTION_PROMPT, report)
        self.assertIn("worker:SYNTH-0001", report)
        self.assertIn("terminal:SYNTH-0001", report)
        self.assertIn("task:SYNTH-0001", report)
        self.assertIn("Offending post-settlement prompt", report)
        self.assertEqual(str(violation), report)

        as_dict = violation.to_dict()
        self.assertEqual(as_dict["seq"], 3)
        self.assertEqual(as_dict["line"], 4)
        self.assertEqual(as_dict["invariant_name"], INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS)

    def test_zero_post_settlement_prompt_detection(self):
        # 1. Post-completion input scenario from runner
        runner = MockOrchestratorRunner()
        collector, _ = runner.run_post_completion_input_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
        )

        violations = check_zero_post_settlement_prompts(collector)
        self.assertEqual(len(violations), 1)

        v = violations[0]
        self.assertEqual(v.invariant_name, INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS)
        self.assertEqual(v.seq, 3)
        self.assertEqual(v.line, 4)
        self.assertEqual(v.action_type, ACTION_INPUT)
        self.assertEqual(v.worker_id, "worker:SYNTH-0001")
        self.assertEqual(v.terminal_id, "terminal:SYNTH-0001")
        self.assertIn("post-settlement", v.diagnostic.lower())
        self.assertIn("DONE", v.diagnostic)

        # 2. Post-completion prompt after BLOCKED status
        c2 = TraceCollector()
        c2.record(ACTION_DISPATCH, worker_id="worker:B", task_id="task:B", terminal_id="term:B", status="RUNNING")
        c2.record(ACTION_READ_PROJECTION, worker_id="worker:B", task_id="task:B", terminal_id="term:B", status="BLOCKED")
        c2.record(ACTION_RELEASE_TERMINAL, worker_id="worker:B", terminal_id="term:B", status="SEALED")
        c2.record(ACTION_PROMPT, worker_id="worker:B", terminal_id="term:B", payload="can you retry?")

        v2 = check_zero_post_settlement_prompts(c2)
        self.assertEqual(len(v2), 1)
        self.assertEqual(v2[0].action_type, ACTION_PROMPT)
        self.assertEqual(v2[0].worker_id, "worker:B")
        self.assertIn("BLOCKED", v2[0].diagnostic)

        # 3. Post-completion prompt targeting terminal_id without explicit worker_id
        c3 = TraceCollector()
        c3.record(ACTION_DISPATCH, worker_id="worker:C", terminal_id="term:C", status="RUNNING")
        c3.record(ACTION_READ_PROJECTION, worker_id="worker:C", terminal_id="term:C", status="FAILED")
        c3.record(ACTION_PROMPT, terminal_id="term:C", payload="what happened?")

        v3 = check_zero_post_settlement_prompts(c3)
        self.assertEqual(len(v3), 1)
        self.assertEqual(v3[0].terminal_id, "term:C")
        self.assertIn("FAILED", v3[0].diagnostic)

        # 4. In-flight input during active execution is NOT a violation
        c4 = TraceCollector()
        c4.record(ACTION_DISPATCH, worker_id="worker:D", terminal_id="term:D", status="RUNNING")
        c4.record(ACTION_INPUT, worker_id="worker:D", terminal_id="term:D", payload="in flight input")
        c4.record(ACTION_READ_PROJECTION, worker_id="worker:D", terminal_id="term:D", status="DONE")
        c4.record(ACTION_RELEASE_TERMINAL, worker_id="worker:D", terminal_id="term:D", status="SEALED")

        v4 = check_zero_post_settlement_prompts(c4)
        self.assertEqual(v4, [])

    def test_immediate_terminal_release_detection_delayed_and_omitted(self):
        # 1. Omitted terminal release at end of trace
        c_omitted = TraceCollector()
        c_omitted.record(ACTION_DISPATCH, worker_id="worker:1", terminal_id="term:1", status="RUNNING")
        c_omitted.record(ACTION_READ_PROJECTION, worker_id="worker:1", terminal_id="term:1", status="DONE")
        # Trace ends without release_terminal

        v_omitted = check_immediate_terminal_release(c_omitted)
        self.assertEqual(len(v_omitted), 1)
        self.assertEqual(v_omitted[0].invariant_name, INVARIANT_IMMEDIATE_TERMINAL_RELEASE)
        self.assertEqual(v_omitted[0].worker_id, "worker:1")
        self.assertEqual(v_omitted[0].terminal_id, "term:1")
        self.assertEqual(v_omitted[0].action_type, ACTION_RELEASE_TERMINAL)
        self.assertIn("never released before end of phase / trace", v_omitted[0].diagnostic)

        # 2. Delayed terminal release past a subsequent dispatch
        c_delayed = TraceCollector()
        c_delayed.record(ACTION_DISPATCH, worker_id="worker:primary", terminal_id="term:primary", status="RUNNING")
        c_delayed.record(ACTION_READ_PROJECTION, worker_id="worker:primary", terminal_id="term:primary", status="BLOCKED")
        # Subsequent dispatch occurs before releasing primary terminal
        c_delayed.record(ACTION_DISPATCH, worker_id="worker:fallback", terminal_id="term:fallback", status="RUNNING")
        c_delayed.record(ACTION_RELEASE_TERMINAL, worker_id="worker:primary", terminal_id="term:primary", status="SEALED")
        c_delayed.record(ACTION_READ_PROJECTION, worker_id="worker:fallback", terminal_id="term:fallback", status="DONE")
        c_delayed.record(ACTION_RELEASE_TERMINAL, worker_id="worker:fallback", terminal_id="term:fallback", status="SEALED")

        v_delayed = check_immediate_terminal_release(c_delayed)
        self.assertEqual(len(v_delayed), 1)
        self.assertEqual(v_delayed[0].invariant_name, INVARIANT_IMMEDIATE_TERMINAL_RELEASE)
        self.assertEqual(v_delayed[0].seq, 2)  # seq of fallback dispatch
        self.assertEqual(v_delayed[0].action_type, ACTION_DISPATCH)
        self.assertEqual(v_delayed[0].worker_id, "worker:primary")
        self.assertEqual(v_delayed[0].terminal_id, "term:primary")
        self.assertIn("subsequent dispatch for worker 'worker:fallback' occurred at seq 2", v_delayed[0].diagnostic)

        # 3. Multiple settled workers unreleased before next dispatch
        c_multi = TraceCollector()
        c_multi.record(ACTION_DISPATCH, worker_id="w1", terminal_id="t1", status="RUNNING")
        c_multi.record(ACTION_DISPATCH, worker_id="w2", terminal_id="t2", status="RUNNING")
        c_multi.record(ACTION_READ_PROJECTION, worker_id="w1", terminal_id="t1", status="DONE")
        c_multi.record(ACTION_READ_PROJECTION, worker_id="w2", terminal_id="t2", status="FAILED")
        c_multi.record(ACTION_DISPATCH, worker_id="w3", terminal_id="t3", status="RUNNING")

        v_multi = check_immediate_terminal_release(c_multi)
        self.assertEqual(len(v_multi), 2)
        flagged_workers = {v.worker_id for v in v_multi}
        self.assertEqual(flagged_workers, {"w1", "w2"})
        self.assertTrue(all(v.seq == 4 for v in v_multi))

    def test_projection_boundary_respect_unjustified_raw_detail(self):
        # 1. Unjustified read_detail on nominal successful task
        runner = MockOrchestratorRunner()
        collector_detailed = runner.run_verbose_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            inspect_detail=True,
        )

        v_detailed = check_projection_boundary_respect(collector_detailed)
        self.assertEqual(len(v_detailed), 1)
        self.assertEqual(v_detailed[0].invariant_name, INVARIANT_PROJECTION_BOUNDARY_RESPECT)
        self.assertEqual(v_detailed[0].action_type, ACTION_READ_DETAIL)
        self.assertEqual(v_detailed[0].worker_id, "worker:SYNTH-0001")
        self.assertIn("raw detail payload", v_detailed[0].diagnostic)
        self.assertIn("without an explicit error", v_detailed[0].diagnostic)

        # 2. Compact projection without detail read passes cleanly
        collector_compact = MockOrchestratorRunner().run_verbose_scenario(
            task_id="task:SYNTH-0001",
            worker_id="worker:SYNTH-0001",
            terminal_id="terminal:SYNTH-0001",
            inspect_detail=False,
        )
        self.assertEqual(check_projection_boundary_respect(collector_compact), [])

        # 3. Justified read_detail on error / blocked worker
        c_error = TraceCollector()
        c_error.record(ACTION_DISPATCH, worker_id="w_err", status="RUNNING")
        c_error.record(ACTION_READ_PROJECTION, worker_id="w_err", status="BLOCKED")
        c_error.record(ACTION_READ_DETAIL, worker_id="w_err", status="BLOCKED")
        c_error.record(ACTION_RELEASE_TERMINAL, worker_id="w_err", status="SEALED")

        v_error = check_projection_boundary_respect(c_error)
        self.assertEqual(v_error, [])

        # 4. Justified read_detail with explicit metadata justification
        c_justified = TraceCollector()
        c_justified.record(ACTION_DISPATCH, worker_id="w_audit", status="RUNNING")
        c_justified.record(ACTION_READ_PROJECTION, worker_id="w_audit", status="DONE")
        c_justified.record(
            ACTION_READ_DETAIL,
            worker_id="w_audit",
            status="DONE",
            metadata={"justified": True, "reason": "audit"},
        )
        c_justified.record(ACTION_RELEASE_TERMINAL, worker_id="w_audit", status="SEALED")

        v_justified = check_projection_boundary_respect(c_justified)
        self.assertEqual(v_justified, [])

        # 5. Unapproved read action type (e.g. read_raw)
        c_raw = TraceCollector()
        c_raw.record("read_raw", worker_id="w_raw", status="OK")

        v_raw = check_projection_boundary_respect(c_raw)
        self.assertEqual(len(v_raw), 1)
        self.assertEqual(v_raw[0].action_type, "read_raw")

    def test_nominal_and_compliant_scenarios_pass_all_invariants(self):
        # 1. Nominal single-worker scenario
        runner_nominal = MockOrchestratorRunner()
        collector_nominal = runner_nominal.run_nominal_scenario()

        self.assertEqual(collector_nominal.verify_all_invariants(), [])
        self.assertEqual(collector_nominal.check_zero_post_settlement_prompts(), [])
        self.assertEqual(collector_nominal.check_immediate_terminal_release(), [])
        self.assertEqual(collector_nominal.check_projection_boundary_respect(), [])

        # 2. Verbose scenario with compact read
        runner_verbose = MockOrchestratorRunner()
        collector_verbose = runner_verbose.run_verbose_scenario(inspect_detail=False)
        self.assertEqual(collector_verbose.verify_all_invariants(), [])

        # 3. Warning / fallback scenario
        runner_fallback = MockOrchestratorRunner()
        collector_fallback = runner_fallback.run_warning_fallback_scenario()
        self.assertEqual(collector_fallback.verify_all_invariants(), [])

    def test_behavioral_invariant_checker_api_styles(self):
        runner = MockOrchestratorRunner()
        collector = runner.run_nominal_scenario()

        # Calling via instance initialized with trace
        checker_inst = BehavioralInvariantChecker(collector)
        self.assertEqual(checker_inst.verify_all_invariants(), [])
        self.assertEqual(checker_inst.check_zero_post_settlement_prompts(), [])
        self.assertEqual(checker_inst.check_immediate_terminal_release(), [])
        self.assertEqual(checker_inst.check_projection_boundary_respect(), [])

        # Calling via blank instance passing trace
        checker_blank = BehavioralInvariantChecker()
        self.assertEqual(checker_blank.verify_all_invariants(collector), [])

        # Calling directly on class
        self.assertEqual(BehavioralInvariantChecker.verify_all_invariants(collector), [])
        self.assertEqual(BehavioralInvariantChecker.check_zero_post_settlement_prompts(collector), [])

        # Calling top-level functions
        self.assertEqual(verify_all_invariants(collector), [])
        self.assertEqual(check_zero_post_settlement_prompts(collector), [])

        # Blank instance without passing trace raises ValueError
        with self.assertRaises(ValueError):
            checker_blank.verify_all_invariants()

    def test_scenario_comparison_metrics_and_reporting(self):
        runner = MockOrchestratorRunner()
        trace_nominal = runner.run_nominal_scenario()

        runner_detail = MockOrchestratorRunner()
        trace_detailed = runner_detail.run_verbose_scenario(inspect_detail=True)

        comp = compare_scenarios(
            trace_nominal,
            trace_detailed,
            label_a="nominal_compact",
            label_b="verbose_detailed",
        )

        self.assertEqual(comp.label_a, "nominal_compact")
        self.assertEqual(comp.label_b, "verbose_detailed")
        self.assertEqual(comp.turn_count_a, 3)
        self.assertEqual(comp.turn_count_b, 4)
        self.assertEqual(comp.turn_count_diff, 1)

        # Detailed scenario has significantly more payload bytes
        self.assertLess(comp.payload_bytes_a, comp.payload_bytes_b)
        self.assertGreater(comp.payload_bytes_diff, 0)

        # Invariant compliance
        self.assertTrue(comp.is_compliant_a)
        self.assertFalse(comp.is_compliant_b)  # detail read without error is non-compliant
        self.assertEqual(len(comp.violations_a), 0)
        self.assertEqual(len(comp.violations_b), 1)

        # Action counts
        self.assertEqual(comp.action_counts_a[ACTION_DISPATCH], 1)
        self.assertEqual(comp.action_counts_a[ACTION_READ_PROJECTION], 1)
        self.assertEqual(comp.action_counts_a[ACTION_RELEASE_TERMINAL], 1)
        self.assertEqual(comp.action_counts_b[ACTION_READ_DETAIL], 1)

        # Dict access and serialization
        self.assertEqual(comp["turn_count_diff"], 1)
        as_dict = comp.to_dict()
        self.assertEqual(as_dict["turn_count_a"], 3)
        self.assertEqual(as_dict["turn_count_b"], 4)
        self.assertIn("violations_b", as_dict)

        # Formatted markdown report
        report = comp.format_report()
        self.assertIn("# Scenario Comparison: nominal_compact vs verbose_detailed", report)
        self.assertIn("Turns: 3 -> 4", report)
        self.assertIn("COMPLIANT", report)
        self.assertIn("NON-COMPLIANT", report)
        self.assertIn("| read_detail |", report)

        # TraceCollector.compare method
        comp2 = trace_nominal.compare(trace_detailed, label_self="nominal_compact", label_other="verbose_detailed")
        self.assertEqual(comp2.turn_count_diff, comp.turn_count_diff)
        self.assertEqual(comp2.payload_bytes_diff, comp.payload_bytes_diff)

    def test_format_violations_report(self):
        # Empty list -> 100% compliant
        msg_clean = format_violations_report([])
        self.assertIn("100% compliant", msg_clean)

        # Non-empty list -> formats each violation
        v = InvariantViolation(
            invariant_name=INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS,
            seq=1,
            timestamp="2026-10-24T09:00:00.100Z",
            action_type=ACTION_INPUT,
            worker_id="worker:test",
            diagnostic="Test violation",
        )
        msg_viol = format_violations_report([v])
        self.assertIn("Violations Detected (1 total)", msg_viol)
        self.assertIn("worker:test", msg_viol)
        self.assertIn("Test violation", msg_viol)


if __name__ == "__main__":
    unittest.main()
