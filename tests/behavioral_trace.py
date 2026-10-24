#!/usr/bin/env python3
"""Offline behavioral trace collector and mock orchestrator event runner.

Provides deterministic execution tracing for coordinator-worker interactions
using standard library dependencies only. Captures action types, target IDs,
payload digests, status codes, and control metadata.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Sequence

# Ensure access to luucycle script modules and test fixtures
_ROOT_DIR = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = str(_ROOT_DIR / "skills" / "luucycle" / "scripts")
_TESTS_DIR = str(_ROOT_DIR / "tests")

for directory in (_SCRIPTS_DIR, _TESTS_DIR):
    if directory not in sys.path:
        sys.path.insert(0, directory)

from compact import (
    STOP_STATUSES,
    TERMINAL_STATUSES,
    check_input,
    decode,
    encode,
    project,
)
from synthetic_returns import envelope, record, worker_returns


# Authoritative action types
ACTION_DISPATCH = "dispatch"
ACTION_PROMPT = "prompt"
ACTION_INPUT = "input"
ACTION_RELEASE_TERMINAL = "release_terminal"
ACTION_READ_PROJECTION = "read_projection"
ACTION_READ_DETAIL = "read_detail"

VALID_ACTIONS = frozenset({
    ACTION_DISPATCH,
    ACTION_PROMPT,
    ACTION_INPUT,
    ACTION_RELEASE_TERMINAL,
    ACTION_READ_PROJECTION,
    ACTION_READ_DETAIL,
})

# Authoritative behavioral invariants
INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS = "zero_post_settlement_prompts"
INVARIANT_IMMEDIATE_TERMINAL_RELEASE = "immediate_terminal_release"
INVARIANT_PROJECTION_BOUNDARY_RESPECT = "projection_boundary_respect"

ALL_INVARIANTS = frozenset({
    INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS,
    INVARIANT_IMMEDIATE_TERMINAL_RELEASE,
    INVARIANT_PROJECTION_BOUNDARY_RESPECT,
})


def compute_digest_and_size(payload: Any) -> tuple[str | None, int]:
    """Deterministically compute sha256 hex digest and byte size for payloads."""
    if payload is None:
        return None, 0
    if isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    elif isinstance(payload, (dict, list)):
        raw = encode(payload)
    else:
        raw = str(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def format_virtual_timestamp(base_iso: str, offset_ms: int) -> str:
    """Format a deterministic virtual timestamp from a base ISO string and millisecond offset."""
    base_clean = base_iso.replace("Z", "+00:00")
    base_dt = datetime.datetime.fromisoformat(base_clean)
    target_dt = base_dt + datetime.timedelta(milliseconds=offset_ms)
    return target_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass(frozen=True)
class TraceEvent:
    """Immutable record capturing an orchestration event in the execution trace."""

    seq: int
    timestamp: str
    action_type: str
    worker_id: str | None = None
    task_id: str | None = None
    terminal_id: str | None = None
    payload_digest: str | None = None
    payload_bytes: int = 0
    status: str = "OK"
    controls: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    metadata: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def create(
        cls,
        seq: int,
        action_type: str,
        *,
        timestamp: str,
        worker_id: str | None = None,
        task_id: str | None = None,
        terminal_id: str | None = None,
        payload: Any = None,
        payload_digest: str | None = None,
        payload_bytes: int | None = None,
        status: str = "OK",
        controls: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        if payload is not None:
            calc_digest, calc_size = compute_digest_and_size(payload)
            final_digest = calc_digest if payload_digest is None else payload_digest
            final_bytes = calc_size if payload_bytes is None else payload_bytes
        else:
            final_digest = payload_digest
            final_bytes = payload_bytes if payload_bytes is not None else 0

        frozen_controls = MappingProxyType(deepcopy(controls) if controls else {})
        frozen_metadata = MappingProxyType(deepcopy(metadata) if metadata else {})

        return cls(
            seq=seq,
            timestamp=timestamp,
            action_type=action_type,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload_digest=final_digest,
            payload_bytes=final_bytes,
            status=status,
            controls=frozen_controls,
            metadata=frozen_metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a mutable serializable representation of this trace event."""
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "worker_id": self.worker_id,
            "task_id": self.task_id,
            "terminal_id": self.terminal_id,
            "payload_digest": self.payload_digest,
            "payload_bytes": self.payload_bytes,
            "status": self.status,
            "controls": dict(self.controls),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class InvariantViolation:
    """Actionable record capturing a behavioral invariant violation in an execution trace."""

    invariant_name: str
    seq: int
    timestamp: str
    action_type: str | None = None
    worker_id: str | None = None
    terminal_id: str | None = None
    task_id: str | None = None
    diagnostic: str = ""

    @property
    def line(self) -> int:
        """Trace event line number (1-based index)."""
        return self.seq + 1

    @property
    def invariant(self) -> str:
        """Alias for invariant_name."""
        return self.invariant_name

    def format_report(self) -> str:
        """Format an actionable diagnostic report line."""
        worker_part = f" worker={self.worker_id}" if self.worker_id else ""
        term_part = f" terminal={self.terminal_id}" if self.terminal_id else ""
        action_part = f" action={self.action_type}" if self.action_type else ""
        task_part = f" task={self.task_id}" if self.task_id else ""
        return (
            f"[seq={self.seq} | line={self.line}] [{self.timestamp}] "
            f"Invariant '{self.invariant_name}' VIOLATED{action_part}{worker_part}{term_part}{task_part}: "
            f"{self.diagnostic}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary representation."""
        return {
            "invariant_name": self.invariant_name,
            "invariant": self.invariant_name,
            "seq": self.seq,
            "line": self.line,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "worker_id": self.worker_id,
            "terminal_id": self.terminal_id,
            "task_id": self.task_id,
            "diagnostic": self.diagnostic,
        }

    def __str__(self) -> str:
        return self.format_report()


@dataclass
class ScenarioComparison:
    """Quantitative comparison of execution metrics and invariant compliance between two traces."""

    label_a: str
    label_b: str
    turn_count_a: int
    turn_count_b: int
    turn_count_diff: int
    turn_count_reduction_pct: float
    payload_bytes_a: int
    payload_bytes_b: int
    payload_bytes_diff: int
    payload_bytes_reduction_pct: float
    action_counts_a: dict[str, int]
    action_counts_b: dict[str, int]
    violations_a: list[InvariantViolation]
    violations_b: list[InvariantViolation]
    is_compliant_a: bool
    is_compliant_b: bool

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "label_a": self.label_a,
            "label_b": self.label_b,
            "turn_count_a": self.turn_count_a,
            "turn_count_b": self.turn_count_b,
            "turn_count_diff": self.turn_count_diff,
            "turn_count_reduction_pct": self.turn_count_reduction_pct,
            "payload_bytes_a": self.payload_bytes_a,
            "payload_bytes_b": self.payload_bytes_b,
            "payload_bytes_diff": self.payload_bytes_diff,
            "payload_bytes_reduction_pct": self.payload_bytes_reduction_pct,
            "action_counts_a": dict(self.action_counts_a),
            "action_counts_b": dict(self.action_counts_b),
            "violations_a": [v.to_dict() for v in self.violations_a],
            "violations_b": [v.to_dict() for v in self.violations_b],
            "is_compliant_a": self.is_compliant_a,
            "is_compliant_b": self.is_compliant_b,
        }

    def format_report(self) -> str:
        """Produce a formatted markdown comparative diagnostic report."""
        all_actions = sorted(set(self.action_counts_a.keys()) | set(self.action_counts_b.keys()))
        action_rows = []
        for action in all_actions:
            count_a = self.action_counts_a.get(action, 0)
            count_b = self.action_counts_b.get(action, 0)
            diff = count_b - count_a
            action_rows.append(f"| {action} | {count_a} | {count_b} | {diff:+d} |")
        action_table = "\n".join(action_rows) if action_rows else "| (none) | 0 | 0 | 0 |"

        status_a = "COMPLIANT" if self.is_compliant_a else f"NON-COMPLIANT ({len(self.violations_a)} violations)"
        status_b = "COMPLIANT" if self.is_compliant_b else f"NON-COMPLIANT ({len(self.violations_b)} violations)"

        return (
            f"# Scenario Comparison: {self.label_a} vs {self.label_b}\n\n"
            f"## Summary Metrics\n"
            f"- Turns: {self.turn_count_a} -> {self.turn_count_b} "
            f"(diff: {self.turn_count_diff:+d}, reduction: {self.turn_count_reduction_pct:.1f}%)\n"
            f"- Payload Volume: {self.payload_bytes_a} B -> {self.payload_bytes_b} B "
            f"(diff: {self.payload_bytes_diff:+d} B, reduction: {self.payload_bytes_reduction_pct:.1f}%)\n"
            f"- Invariant Compliance ({self.label_a}): {status_a}\n"
            f"- Invariant Compliance ({self.label_b}): {status_b}\n\n"
            f"## Action Distribution\n"
            f"| Action Type | {self.label_a} | {self.label_b} | Diff |\n"
            f"| :--- | :--- | :--- | :--- |\n"
            f"{action_table}\n"
        )


class TraceCollector:
    """In-memory collector recording and querying chronological orchestration trace events."""

    def __init__(
        self,
        base_timestamp: str = "2026-10-24T09:00:00.000Z",
        clock_step_ms: int = 100,
    ) -> None:
        self._base_timestamp = base_timestamp
        self._clock_step_ms = clock_step_ms
        self._events: list[TraceEvent] = []
        self._seq_counter = 0

    def record(
        self,
        action_type: str,
        *,
        worker_id: str | None = None,
        task_id: str | None = None,
        terminal_id: str | None = None,
        payload: Any = None,
        payload_digest: str | None = None,
        payload_bytes: int | None = None,
        status: str = "OK",
        controls: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> TraceEvent:
        """Create and store an immutable trace event with strictly monotonic sequencing."""
        event_seq = self._seq_counter
        self._seq_counter += 1

        if timestamp is None:
            event_ts = format_virtual_timestamp(self._base_timestamp, event_seq * self._clock_step_ms)
        else:
            event_ts = timestamp

        event = TraceEvent.create(
            seq=event_seq,
            action_type=action_type,
            timestamp=event_ts,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload=payload,
            payload_digest=payload_digest,
            payload_bytes=payload_bytes,
            status=status,
            controls=controls,
            metadata=metadata,
        )
        self._events.append(event)
        return event

    def get_events(self) -> list[TraceEvent]:
        """Return a copy of the ordered events list."""
        return list(self._events)

    def events_by_worker(self, worker_id: str) -> list[TraceEvent]:
        """Return all events targeting the given worker ID."""
        return [e for e in self._events if e.worker_id == worker_id]

    def events_by_action(self, action_type: str) -> list[TraceEvent]:
        """Return all events matching the specified action type."""
        return [e for e in self._events if e.action_type == action_type]

    def events_by_task(self, task_id: str) -> list[TraceEvent]:
        """Return all events targeting the given task ID."""
        return [e for e in self._events if e.task_id == task_id]

    def events_by_terminal(self, terminal_id: str) -> list[TraceEvent]:
        """Return all events targeting the given terminal ID."""
        return [e for e in self._events if e.terminal_id == terminal_id]

    def actions_after_status(
        self,
        worker_id: str,
        status: str,
        *,
        target_worker_only: bool = True,
    ) -> list[TraceEvent]:
        """Return all events occurring chronologically after a worker emitted the given status.

        If target_worker_only is True, filters only events targeting this worker.
        If False, returns all subsequent events across the entire orchestration.
        """
        status_event = next(
            (e for e in self._events if e.worker_id == worker_id and e.status == status),
            None,
        )
        if status_event is None:
            return []

        if target_worker_only:
            return [
                e for e in self._events
                if e.seq > status_event.seq and e.worker_id == worker_id
            ]
        return [e for e in self._events if e.seq > status_event.seq]

    def has_action_after(
        self,
        worker_id: str,
        status: str,
        action_types: set[str] | list[str],
    ) -> bool:
        """Check if any specified action occurred after worker transitioned to status."""
        action_set = set(action_types)
        subsequent = self.actions_after_status(worker_id, status, target_worker_only=True)
        return any(e.action_type in action_set for e in subsequent)

    def total_payload_bytes(self) -> int:
        """Compute the sum of payload byte sizes across all captured events."""
        return sum(e.payload_bytes for e in self._events)

    def turn_count(self) -> int:
        """Return total number of captured action turns."""
        return len(self._events)

    def summary_metrics(self) -> dict[str, Any]:
        """Return aggregate diagnostic metrics for this execution trace."""
        return {
            "turn_count": len(self._events),
            "total_payload_bytes": self.total_payload_bytes(),
            "action_counts": dict(sorted(Counter(e.action_type for e in self._events).items())),
            "status_counts": dict(sorted(Counter(e.status for e in self._events).items())),
            "workers": sorted(list({e.worker_id for e in self._events if e.worker_id})),
            "tasks": sorted(list({e.task_id for e in self._events if e.task_id})),
            "terminals": sorted(list({e.terminal_id for e in self._events if e.terminal_id})),
        }

    def clear(self) -> None:
        """Reset the collector to an empty state."""
        self._events.clear()
        self._seq_counter = 0

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    def __getitem__(self, index: int) -> TraceEvent:
        return self._events[index]

    def verify_all_invariants(self) -> list[InvariantViolation]:
        """Verify all authoritative behavioral invariants on this trace."""
        return verify_all_invariants(self)

    def check_zero_post_settlement_prompts(self) -> list[InvariantViolation]:
        """Verify zero post-settlement prompt or input actions on this trace."""
        return check_zero_post_settlement_prompts(self)

    def check_immediate_terminal_release(self) -> list[InvariantViolation]:
        """Verify immediate terminal release upon task settlement on this trace."""
        return check_immediate_terminal_release(self)

    def check_projection_boundary_respect(self) -> list[InvariantViolation]:
        """Verify projection boundary respect and detail read restrictions on this trace."""
        return check_projection_boundary_respect(self)

    def compare(
        self,
        other: TraceCollector | Sequence[TraceEvent],
        *,
        label_self: str = "current",
        label_other: str = "other",
    ) -> ScenarioComparison:
        """Compare execution metrics and invariant compliance against another trace."""
        return compare_scenarios(self, other, label_a=label_self, label_b=label_other)


class MockOrchestratorRunner:
    """Simulates coordinator-worker lifecycle event sequences and records execution traces."""

    def __init__(self, collector: TraceCollector | None = None) -> None:
        self.collector = collector if collector is not None else TraceCollector()

    def dispatch(
        self,
        task_id: str,
        worker_id: str,
        terminal_id: str,
        *,
        payload: Any = None,
        controls: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "RUNNING",
    ) -> TraceEvent:
        """Simulate coordinator dispatching a worker to an allocated terminal."""
        return self.collector.record(
            action_type=ACTION_DISPATCH,
            task_id=task_id,
            worker_id=worker_id,
            terminal_id=terminal_id,
            payload=payload,
            status=status,
            controls=controls,
            metadata=metadata,
        )

    def read_projection(
        self,
        worker_id: str,
        return_payload: dict[str, Any] | bytes,
        *,
        task_id: str | None = None,
        terminal_id: str | None = None,
        source_ref: str = "fixture:worker_return.json",
    ) -> tuple[TraceEvent, dict[str, Any]]:
        """Simulate coordinator projecting a worker receipt using compact.project."""
        if isinstance(return_payload, dict):
            raw_bytes = encode(return_payload)
        else:
            raw_bytes = return_payload

        projection = project(raw_bytes, source_ref)

        # Find status and controls from projected items matching worker
        worker_status = "UNKNOWN"
        worker_controls = {}
        for item in projection.get("items", []):
            if item.get("id") == worker_id or item.get("ids", {}).get("worker") == worker_id:
                worker_status = item.get("status", "UNKNOWN")
                worker_controls = item.get("controls", {})
                if not task_id:
                    task_id = item.get("ids", {}).get("task")
                if not terminal_id:
                    terminal_id = item.get("ids", {}).get("terminal")
                break

        event = self.collector.record(
            action_type=ACTION_READ_PROJECTION,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload=projection,
            status=worker_status,
            controls=worker_controls,
            metadata={"projection_status": projection.get("status")},
        )
        return event, projection

    def read_detail(
        self,
        worker_id: str,
        return_payload: dict[str, Any] | bytes,
        record_id: str,
        *,
        task_id: str | None = None,
        terminal_id: str | None = None,
        source_ref: str = "fixture:worker_return.json",
    ) -> tuple[TraceEvent, dict[str, Any]]:
        """Simulate coordinator reading detailed report for a specific record."""
        if isinstance(return_payload, (bytes, bytearray)):
            decoded = decode(bytes(return_payload))
        else:
            decoded = return_payload

        matches = [item for item in decoded.get("items", []) if item.get("id") == record_id]
        detail_data = matches[0].get("detail", {}) if matches else {}
        item_status = matches[0].get("status", "UNKNOWN") if matches else "UNKNOWN"
        item_controls = matches[0].get("controls", {}) if matches else {}

        event = self.collector.record(
            action_type=ACTION_READ_DETAIL,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload=detail_data,
            status=item_status,
            controls=item_controls,
            metadata={"record_id": record_id},
        )
        return event, detail_data

    def release_terminal(
        self,
        worker_id: str,
        terminal_id: str,
        *,
        task_id: str | None = None,
        status: str = "SEALED",
        controls: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Simulate coordinator releasing worker terminal immediately upon settlement."""
        return self.collector.record(
            action_type=ACTION_RELEASE_TERMINAL,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            status=status,
            controls=controls,
        )

    def send_input(
        self,
        worker_id: str,
        terminal_id: str,
        payload: Any,
        *,
        task_id: str | None = None,
        return_payload: dict[str, Any] | bytes | None = None,
        source_ref: str = "<memory>",
        sha256: str | None = None,
        controls: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Simulate coordinator sending interactive input to a worker session.

        Interfaces directly with compact.check_input when return_payload is supplied.
        """
        metadata: dict[str, Any] = {}
        status = "OK"

        if return_payload is not None:
            check_result = check_input(
                raw=return_payload,
                source=source_ref,
                worker_id=worker_id,
                sha256=sha256,
            )
            metadata["check_input"] = check_result
            if check_result.get("status") == "STOP":
                status = "STOP"
                metadata["rejected"] = True
                metadata["diagnostic"] = check_result.get("diagnostic")
        else:
            # Check internal collector trace for terminal statuses
            prior_events = self.collector.events_by_worker(worker_id)
            if any(e.status in TERMINAL_STATUSES for e in prior_events):
                status = "STOP"
                metadata["rejected"] = True
                metadata["diagnostic"] = "worker is sealed; post-completion input is rejected"

        return self.collector.record(
            action_type=ACTION_INPUT,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload=payload,
            status=status,
            controls=controls,
            metadata=metadata,
        )

    def prompt(
        self,
        worker_id: str,
        prompt_text: str,
        *,
        terminal_id: str | None = None,
        task_id: str | None = None,
        return_payload: dict[str, Any] | bytes | None = None,
        source_ref: str = "<memory>",
        sha256: str | None = None,
        controls: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Simulate coordinator sending a prompt to a worker session."""
        metadata: dict[str, Any] = {}
        status = "OK"

        if return_payload is not None:
            check_result = check_input(
                raw=return_payload,
                source=source_ref,
                worker_id=worker_id,
                sha256=sha256,
            )
            metadata["check_input"] = check_result
            if check_result.get("status") == "STOP":
                status = "STOP"
                metadata["rejected"] = True
                metadata["diagnostic"] = check_result.get("diagnostic")
        else:
            prior_events = self.collector.events_by_worker(worker_id)
            if any(e.status in TERMINAL_STATUSES for e in prior_events):
                status = "STOP"
                metadata["rejected"] = True
                metadata["diagnostic"] = "worker is sealed; post-completion input is rejected"

        return self.collector.record(
            action_type=ACTION_PROMPT,
            worker_id=worker_id,
            task_id=task_id,
            terminal_id=terminal_id,
            payload=prompt_text,
            status=status,
            controls=controls,
            metadata=metadata,
        )

    # -------------------------------------------------------------------------
    # Pre-packaged Synthetic Scenarios
    # -------------------------------------------------------------------------

    def run_nominal_scenario(
        self,
        task_id: str = "task:SYNTH-0001",
        worker_id: str = "worker:SYNTH-0001",
        terminal_id: str = "terminal:SYNTH-0001",
    ) -> TraceCollector:
        """Nominal scenario: Worker dispatched, completes DONE, projects return, terminal released."""
        workers_data = worker_returns()
        # Item 0 is DONE in worker_returns()
        single_worker = deepcopy(workers_data["items"][0])
        single_worker["ids"]["task"] = task_id
        single_worker["ids"]["worker"] = worker_id
        single_worker["ids"]["terminal"] = terminal_id
        worker_packet = envelope("workers", [single_worker])

        # 1. Dispatch
        self.dispatch(
            task_id=task_id,
            worker_id=worker_id,
            terminal_id=terminal_id,
            payload={"instruction": f"Implement {task_id}"},
            controls=single_worker["controls"],
        )

        # 2. Worker completes and emits receipt -> coordinator reads projection
        self.read_projection(
            worker_id=worker_id,
            return_payload=worker_packet,
            task_id=task_id,
            terminal_id=terminal_id,
        )

        # 3. Terminal released immediately upon settlement
        self.release_terminal(
            worker_id=worker_id,
            terminal_id=terminal_id,
            task_id=task_id,
            status="SEALED",
        )

        return self.collector

    def run_verbose_scenario(
        self,
        task_id: str = "task:SYNTH-0001",
        worker_id: str = "worker:SYNTH-0001",
        terminal_id: str = "terminal:SYNTH-0001",
        inspect_detail: bool = False,
    ) -> TraceCollector:
        """Verbose scenario: Worker DONE with heavy narrative detail in detail field."""
        workers_data = worker_returns()
        verbose_worker = deepcopy(workers_data["items"][0])
        verbose_worker["ids"]["task"] = task_id
        verbose_worker["ids"]["worker"] = worker_id
        verbose_worker["ids"]["terminal"] = terminal_id
        worker_packet = envelope("workers", [verbose_worker])

        # 1. Dispatch
        self.dispatch(
            task_id=task_id,
            worker_id=worker_id,
            terminal_id=terminal_id,
            payload={"instruction": f"Execute verbose task {task_id}"},
            controls=verbose_worker["controls"],
        )

        # 2. Coordinator reads compact projection (keeps detailed report outside context)
        self.read_projection(
            worker_id=worker_id,
            return_payload=worker_packet,
            task_id=task_id,
            terminal_id=terminal_id,
        )

        # 3. Optional detailed inspection if specifically requested
        if inspect_detail:
            self.read_detail(
                worker_id=worker_id,
                return_payload=worker_packet,
                record_id=verbose_worker["id"],
                task_id=task_id,
                terminal_id=terminal_id,
            )

        # 4. Release terminal
        self.release_terminal(
            worker_id=worker_id,
            terminal_id=terminal_id,
            task_id=task_id,
            status="SEALED",
        )

        return self.collector

    def run_warning_fallback_scenario(
        self,
        task_id: str = "task:SYNTH-0003",
        primary_worker_id: str = "worker:SYNTH-0003",
        primary_terminal_id: str = "terminal:SYNTH-0003",
        fallback_worker_id: str = "worker:SYNTH-0003-fallback",
        fallback_terminal_id: str = "terminal:SYNTH-0003-fallback",
    ) -> TraceCollector:
        """Warning / fallback scenario: Primary worker reports BLOCKED, terminal released, fresh fallback dispatched."""
        workers_data = worker_returns()
        # Item 2 is BLOCKED with selection warnings/blockers in worker_returns()
        blocked_worker = deepcopy(workers_data["items"][2])
        blocked_worker["ids"]["task"] = task_id
        blocked_worker["ids"]["worker"] = primary_worker_id
        blocked_worker["ids"]["terminal"] = primary_terminal_id
        blocked_packet = envelope("workers", [blocked_worker], errors=[{"code": "SYNTH_BLOCKED", "resolved": False}])

        # 1. Dispatch primary worker
        self.dispatch(
            task_id=task_id,
            worker_id=primary_worker_id,
            terminal_id=primary_terminal_id,
            payload={"instruction": f"Primary dispatch for {task_id}"},
            controls=blocked_worker["controls"],
        )

        # 2. Coordinator reads projection and observes BLOCKED / warnings
        self.read_projection(
            worker_id=primary_worker_id,
            return_payload=blocked_packet,
            task_id=task_id,
            terminal_id=primary_terminal_id,
        )

        # 3. Immediately release primary terminal (one-shot disposal)
        self.release_terminal(
            worker_id=primary_worker_id,
            terminal_id=primary_terminal_id,
            task_id=task_id,
            status="SEALED",
        )

        # 4. Dispatch fallback worker to a fresh terminal
        fallback_worker = deepcopy(workers_data["items"][0])  # nominal DONE worker template
        fallback_worker["ids"]["task"] = task_id
        fallback_worker["ids"]["worker"] = fallback_worker_id
        fallback_worker["ids"]["terminal"] = fallback_terminal_id
        fallback_worker["controls"]["fallback_used"] = True
        fallback_packet = envelope("workers", [fallback_worker])

        self.dispatch(
            task_id=task_id,
            worker_id=fallback_worker_id,
            terminal_id=fallback_terminal_id,
            payload={"instruction": f"Fallback dispatch for {task_id}"},
            controls=fallback_worker["controls"],
        )

        # 5. Read fallback projection
        self.read_projection(
            worker_id=fallback_worker_id,
            return_payload=fallback_packet,
            task_id=task_id,
            terminal_id=fallback_terminal_id,
        )

        # 6. Release fallback terminal
        self.release_terminal(
            worker_id=fallback_worker_id,
            terminal_id=fallback_terminal_id,
            task_id=task_id,
            status="SEALED",
        )

        return self.collector

    def run_post_completion_input_scenario(
        self,
        task_id: str = "task:SYNTH-0001",
        worker_id: str = "worker:SYNTH-0001",
        terminal_id: str = "terminal:SYNTH-0001",
        input_payload: str = "echo 'attempted follow-up input'",
    ) -> tuple[TraceCollector, TraceEvent]:
        """Post-completion scenario: Attempts input to completed worker, verified via compact.check_input."""
        workers_data = worker_returns()
        settled_worker = deepcopy(workers_data["items"][0])  # status: DONE
        settled_worker["ids"]["task"] = task_id
        settled_worker["ids"]["worker"] = worker_id
        settled_worker["ids"]["terminal"] = terminal_id
        settled_packet = envelope("workers", [settled_worker])

        # 1. Normal dispatch
        self.dispatch(
            task_id=task_id,
            worker_id=worker_id,
            terminal_id=terminal_id,
            payload={"instruction": f"Run {task_id}"},
            controls=settled_worker["controls"],
        )

        # 2. Worker settles with DONE
        self.read_projection(
            worker_id=worker_id,
            return_payload=settled_packet,
            task_id=task_id,
            terminal_id=terminal_id,
        )

        # 3. Terminal released
        self.release_terminal(
            worker_id=worker_id,
            terminal_id=terminal_id,
            task_id=task_id,
            status="SEALED",
        )

        # 4. Attempt post-completion input (interfaces with compact.check_input)
        rejected_event = self.send_input(
            worker_id=worker_id,
            terminal_id=terminal_id,
            payload=input_payload,
            task_id=task_id,
            return_payload=settled_packet,
        )

        return self.collector, rejected_event


# -----------------------------------------------------------------------------
# Invariant Evaluation Engine & Scenario Reporting
# -----------------------------------------------------------------------------


def _normalize_trace(trace: TraceCollector | Sequence[TraceEvent]) -> list[TraceEvent]:
    """Normalize input trace to an ordered list of TraceEvent objects."""
    if isinstance(trace, TraceCollector):
        return trace.get_events()
    return list(trace)


def check_zero_post_settlement_prompts(
    trace: TraceCollector | Sequence[TraceEvent],
) -> list[InvariantViolation]:
    """Verify that exactly zero prompt or input actions target a worker once its terminal status is emitted.

    Prohibits ACTION_PROMPT and ACTION_INPUT targeting a worker_id or terminal_id that has transitioned
    to any terminal status (DONE, BLOCKED, FAILED, SEALED).
    """
    events = _normalize_trace(trace)
    violations: list[InvariantViolation] = []

    # Map worker_id -> settlement TraceEvent
    settled_workers: dict[str, TraceEvent] = {}
    # Map terminal_id -> (worker_id, settlement TraceEvent)
    settled_terminals: dict[str, tuple[str | None, TraceEvent]] = {}

    for event in events:
        target_worker = event.worker_id
        target_term = event.terminal_id

        # Check if event attempts prompt or input to an already settled worker/terminal
        is_post_prompt = (
            event.action_type in (ACTION_PROMPT, ACTION_INPUT)
            and (
                (target_worker and target_worker in settled_workers)
                or (target_term and target_term in settled_terminals)
            )
        )

        if is_post_prompt:
            settlement_event = (
                settled_workers.get(target_worker)  # type: ignore
                if target_worker and target_worker in settled_workers
                else settled_terminals[target_term][1]  # type: ignore
            )
            reported_worker = target_worker or (
                settled_terminals[target_term][0] if target_term and target_term in settled_terminals else None
            )
            reported_terminal = target_term or settlement_event.terminal_id

            diag = (
                f"Action '{event.action_type}' at seq {event.seq} targeted worker '{reported_worker}' "
                f"(terminal '{reported_terminal}') after it transitioned to terminal status "
                f"'{settlement_event.status}' at seq {settlement_event.seq} ({settlement_event.timestamp}). "
                f"Post-settlement input or prompting is strictly prohibited."
            )
            violations.append(
                InvariantViolation(
                    invariant_name=INVARIANT_ZERO_POST_SETTLEMENT_PROMPTS,
                    seq=event.seq,
                    timestamp=event.timestamp,
                    action_type=event.action_type,
                    worker_id=reported_worker,
                    terminal_id=reported_terminal,
                    task_id=event.task_id or settlement_event.task_id,
                    diagnostic=diag,
                )
            )

        # Update settled records if this event emits a terminal status
        if target_worker and event.status in TERMINAL_STATUSES:
            if target_worker not in settled_workers:
                settled_workers[target_worker] = event
            if target_term and target_term not in settled_terminals:
                settled_terminals[target_term] = (target_worker, event)

        payload = getattr(event, "payload", None)
        if isinstance(payload, dict):
            for item in payload.get("items", []):
                item_worker = item.get("ids", {}).get("worker") or item.get("id")
                item_status = item.get("status")
                item_terminal = item.get("ids", {}).get("terminal") or target_term
                if item_worker and item_status in TERMINAL_STATUSES:
                    if item_worker not in settled_workers:
                        settled_workers[item_worker] = event
                    if item_terminal and item_terminal not in settled_terminals:
                        settled_terminals[item_terminal] = (item_worker, event)

    return violations


def check_immediate_terminal_release(
    trace: TraceCollector | Sequence[TraceEvent],
) -> list[InvariantViolation]:
    """Assert that a terminal release action occurs immediately upon task settlement before subsequent dispatches or phase end."""
    events = _normalize_trace(trace)
    violations: list[InvariantViolation] = []

    # Map worker_id -> terminal_id
    active_terminals: dict[str, str] = {}
    # Map worker_id -> (settled_event, terminal_id)
    settled_unreleased: dict[str, tuple[TraceEvent, str | None]] = {}
    # Track worker IDs that have already been reported for dispatch violation
    reported_workers: set[str] = set()

    for event in events:
        if event.action_type == ACTION_DISPATCH:
            # Check if any settled worker has not had its terminal released prior to this dispatch
            if settled_unreleased:
                for unreleased_worker, (settled_ev, term_id) in list(settled_unreleased.items()):
                    if unreleased_worker not in reported_workers:
                        diag = (
                            f"Terminal '{term_id}' for worker '{unreleased_worker}' was not released "
                            f"immediately upon task settlement (settled '{settled_ev.status}' at seq {settled_ev.seq}); "
                            f"subsequent dispatch for worker '{event.worker_id}' occurred at seq {event.seq} "
                            f"before terminal disposal."
                        )
                        violations.append(
                            InvariantViolation(
                                invariant_name=INVARIANT_IMMEDIATE_TERMINAL_RELEASE,
                                seq=event.seq,
                                timestamp=event.timestamp,
                                action_type=event.action_type,
                                worker_id=unreleased_worker,
                                terminal_id=term_id,
                                task_id=settled_ev.task_id,
                                diagnostic=diag,
                            )
                        )
                        reported_workers.add(unreleased_worker)

            if event.worker_id and event.terminal_id:
                active_terminals[event.worker_id] = event.terminal_id

        elif event.action_type == ACTION_RELEASE_TERMINAL:
            # Release matching worker or terminal
            if event.worker_id:
                settled_unreleased.pop(event.worker_id, None)
                active_terminals.pop(event.worker_id, None)
            if event.terminal_id:
                matching = [
                    w for w, (_, tid) in settled_unreleased.items()
                    if tid == event.terminal_id
                ]
                for w in matching:
                    settled_unreleased.pop(w, None)
                term_workers = [w for w, tid in active_terminals.items() if tid == event.terminal_id]
                for w in term_workers:
                    active_terminals.pop(w, None)

        # Check if this event transitions a worker to terminal status
        if event.action_type != ACTION_RELEASE_TERMINAL:
            if event.worker_id and event.status in TERMINAL_STATUSES:
                term_id = event.terminal_id or active_terminals.get(event.worker_id)
                if event.worker_id not in settled_unreleased:
                    settled_unreleased[event.worker_id] = (event, term_id)

            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                for item in payload.get("items", []):
                    item_worker = item.get("ids", {}).get("worker") or item.get("id")
                    item_status = item.get("status")
                    if item_worker and item_status in TERMINAL_STATUSES:
                        item_term = (
                            item.get("ids", {}).get("terminal")
                            or active_terminals.get(item_worker)
                            or event.terminal_id
                        )
                        if item_worker not in settled_unreleased:
                            settled_unreleased[item_worker] = (event, item_term)

    # End of trace: verify all settled workers released their terminals before phase/trace conclusion
    if settled_unreleased:
        last_ev = events[-1] if events else None
        last_seq = last_ev.seq if last_ev else 0
        last_ts = last_ev.timestamp if last_ev else ""
        for unreleased_worker, (settled_ev, term_id) in settled_unreleased.items():
            if unreleased_worker not in reported_workers:
                diag = (
                    f"Worker '{unreleased_worker}' reached terminal status '{settled_ev.status}' "
                    f"at seq {settled_ev.seq} ({settled_ev.timestamp}), but terminal '{term_id}' "
                    f"was never released before end of phase / trace."
                )
                violations.append(
                    InvariantViolation(
                        invariant_name=INVARIANT_IMMEDIATE_TERMINAL_RELEASE,
                        seq=last_seq,
                        timestamp=last_ts,
                        action_type=ACTION_RELEASE_TERMINAL,
                        worker_id=unreleased_worker,
                        terminal_id=term_id,
                        task_id=settled_ev.task_id,
                        diagnostic=diag,
                    )
                )

    return violations


def check_projection_boundary_respect(
    trace: TraceCollector | Sequence[TraceEvent],
) -> list[InvariantViolation]:
    """Verify that coordinator reads utilize compact projections and avoid raw detail payloads in normal operations."""
    events = _normalize_trace(trace)
    violations: list[InvariantViolation] = []

    # Map worker_id / task_id -> has explicit error or stop status
    error_entities: set[str] = set()

    for event in events:
        # Check if event introduces error or stop status for worker/task
        if event.status in STOP_STATUSES or event.status == "ERROR":
            if event.worker_id:
                error_entities.add(event.worker_id)
            if event.task_id:
                error_entities.add(event.task_id)

        # Check metadata/controls for errors
        if event.metadata.get("projection_status") in ("STOP", "ERROR"):
            if event.worker_id:
                error_entities.add(event.worker_id)
            if event.task_id:
                error_entities.add(event.task_id)

        payload = getattr(event, "payload", None)
        if isinstance(payload, dict):
            if payload.get("errors"):
                if event.worker_id:
                    error_entities.add(event.worker_id)
                if event.task_id:
                    error_entities.add(event.task_id)
            for item in payload.get("items", []):
                item_status = item.get("status")
                item_worker = item.get("ids", {}).get("worker") or item.get("id")
                item_task = item.get("ids", {}).get("task")
                if item_status in STOP_STATUSES or item.get("blockers") or item_status == "ERROR":
                    if item_worker:
                        error_entities.add(item_worker)
                    if item_task:
                        error_entities.add(item_task)

        # Evaluate read actions
        if event.action_type == ACTION_READ_DETAIL:
            # Check if this read_detail is justified by error or explicit inspection need
            has_error = (
                (event.worker_id and event.worker_id in error_entities)
                or (event.task_id and event.task_id in error_entities)
                or event.status in STOP_STATUSES
                or event.status == "ERROR"
            )
            has_explicit_justification = (
                bool(event.metadata.get("justified"))
                or bool(event.metadata.get("inspect_detail"))
                or bool(event.controls.get("inspect_detail"))
                or bool(event.controls.get("allow_detail"))
                or bool(event.controls.get("audit"))
                or bool(event.metadata.get("error"))
                or event.metadata.get("reason") in (
                    "error",
                    "diagnostic",
                    "investigation",
                    "inspection",
                    "audit",
                )
            )

            if not (has_error or has_explicit_justification):
                diag = (
                    f"Action '{event.action_type}' at seq {event.seq} inspected raw detail payload "
                    f"for worker '{event.worker_id}' during normal operations without an explicit error "
                    f"condition or targeted inspection requirement. Compact projections must be used."
                )
                violations.append(
                    InvariantViolation(
                        invariant_name=INVARIANT_PROJECTION_BOUNDARY_RESPECT,
                        seq=event.seq,
                        timestamp=event.timestamp,
                        action_type=event.action_type,
                        worker_id=event.worker_id,
                        terminal_id=event.terminal_id,
                        task_id=event.task_id,
                        diagnostic=diag,
                    )
                )

        # If any other read action that is not read_projection:
        elif event.action_type.startswith("read_") and event.action_type != ACTION_READ_PROJECTION:
            diag = (
                f"Action '{event.action_type}' at seq {event.seq} bypassed compact projection "
                f"boundary. Ordinary data reads must use '{ACTION_READ_PROJECTION}'."
            )
            violations.append(
                InvariantViolation(
                    invariant_name=INVARIANT_PROJECTION_BOUNDARY_RESPECT,
                    seq=event.seq,
                    timestamp=event.timestamp,
                    action_type=event.action_type,
                    worker_id=event.worker_id,
                    terminal_id=event.terminal_id,
                    task_id=event.task_id,
                    diagnostic=diag,
                )
            )

    return violations


def verify_all_invariants(
    trace: TraceCollector | Sequence[TraceEvent],
) -> list[InvariantViolation]:
    """Execute all authoritative behavioral invariants and return ordered list of violations (empty if compliant)."""
    violations: list[InvariantViolation] = []
    violations.extend(check_zero_post_settlement_prompts(trace))
    violations.extend(check_immediate_terminal_release(trace))
    violations.extend(check_projection_boundary_respect(trace))
    violations.sort(key=lambda v: (v.seq, v.timestamp, v.invariant_name))
    return violations


def format_violations_report(violations: Sequence[InvariantViolation]) -> str:
    """Format an actionable diagnostic report for a list of invariant violations."""
    if not violations:
        return "Trace is 100% compliant with all behavioral invariants (0 violations)."

    lines = [
        f"Behavioral Invariant Violations Detected ({len(violations)} total):",
        "=" * 70,
    ]
    for v in violations:
        lines.append(v.format_report())
    lines.append("=" * 70)
    return "\n".join(lines)


def compare_scenarios(
    trace_a: TraceCollector | Sequence[TraceEvent],
    trace_b: TraceCollector | Sequence[TraceEvent],
    label_a: str = "scenario_a",
    label_b: str = "scenario_b",
) -> ScenarioComparison:
    """Compare execution metrics and invariant compliance between two execution traces."""
    events_a = _normalize_trace(trace_a)
    events_b = _normalize_trace(trace_b)

    turns_a = len(events_a)
    turns_b = len(events_b)
    turns_diff = turns_b - turns_a
    turns_reduc = round(((turns_a - turns_b) / turns_a * 100.0), 2) if turns_a > 0 else 0.0

    bytes_a = sum(e.payload_bytes for e in events_a)
    bytes_b = sum(e.payload_bytes for e in events_b)
    bytes_diff = bytes_b - bytes_a
    bytes_reduc = round(((bytes_a - bytes_b) / bytes_a * 100.0), 2) if bytes_a > 0 else 0.0

    actions_a = dict(sorted(Counter(e.action_type for e in events_a).items()))
    actions_b = dict(sorted(Counter(e.action_type for e in events_b).items()))

    violations_a = verify_all_invariants(events_a)
    violations_b = verify_all_invariants(events_b)

    return ScenarioComparison(
        label_a=label_a,
        label_b=label_b,
        turn_count_a=turns_a,
        turn_count_b=turns_b,
        turn_count_diff=turns_diff,
        turn_count_reduction_pct=turns_reduc,
        payload_bytes_a=bytes_a,
        payload_bytes_b=bytes_b,
        payload_bytes_diff=bytes_diff,
        payload_bytes_reduction_pct=bytes_reduc,
        action_counts_a=actions_a,
        action_counts_b=actions_b,
        violations_a=violations_a,
        violations_b=violations_b,
        is_compliant_a=len(violations_a) == 0,
        is_compliant_b=len(violations_b) == 0,
    )


class _CheckerMethod:
    """Descriptor allowing invariant check methods to be invoked on class or instance."""

    def __init__(self, fn: Any) -> None:
        self.fn = fn

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self.fn

        def wrapper(trace: TraceCollector | Sequence[TraceEvent] | None = None) -> Any:
            target = trace if trace is not None else obj.trace
            if target is None:
                raise ValueError("No trace provided for invariant evaluation.")
            return self.fn(target)

        return wrapper


class BehavioralInvariantChecker:
    """Evaluates orchestration execution traces against strict behavioral invariants."""

    def __init__(self, trace: TraceCollector | Sequence[TraceEvent] | None = None) -> None:
        self.trace = trace

    check_zero_post_settlement_prompts = _CheckerMethod(check_zero_post_settlement_prompts)
    check_immediate_terminal_release = _CheckerMethod(check_immediate_terminal_release)
    check_projection_boundary_respect = _CheckerMethod(check_projection_boundary_respect)
    verify_all_invariants = _CheckerMethod(verify_all_invariants)
