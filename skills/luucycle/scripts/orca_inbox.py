#!/usr/bin/env python3
"""Read and project one exact Orca Run Delivery without acknowledging it.

The live path deliberately creates/replays the Run's native Delivery by using
`orchestration check --run ID --json`. This is an inbox mutation: callers must
explicitly authorize it for that Run. It never acknowledges, replies, sends, or
retries an ambiguous check. Offline records are never considered authenticated.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orca_adapter as adapter
import compact

VERSION = adapter.VERSION
SCHEMA = "luucycle.orca-inbox.v1"
_RUN = re.compile(r"run_[0-9a-f]{12}\Z")
_TASK = re.compile(r"task_[0-9a-f]{12}\Z")
_DISPATCH = re.compile(r"ctx_[0-9a-f]{12}\Z")


def _need(condition: bool, issue: str) -> None:
    if not condition:
        raise adapter.AdapterError(issue)


def _check_delivery_receipt(doc: Any, run_id: str) -> dict[str, Any]:
    _need(isinstance(doc, dict) and doc.get("ok") is True and isinstance(doc.get("result"), dict),
          "native check error or unsupported envelope")
    _need(not doc.get("error") and not doc.get("errors") and
          not doc["result"].get("error") and not doc["result"].get("errors"),
          "native check error")
    # Orca 1.4.229 native check result controls. Unknown controls are retained
    # by their raw-source digest and stop projection.
    _need(doc.keys() <= {"id", "ok", "result", "_meta"}, "unsupported native check envelope controls")
    _need(doc["_meta"].keys() <= {"runtimeId"}, "unsupported native check metadata")
    result = doc["result"]
    _need(isinstance(result, dict) and result.keys() <= {
        "runId", "deliveryId", "messages", "count", "acknowledged", "replayed",
        "timedOut", "cancelled", "connectionLost", "mutation"}, "unsupported native check controls")
    if "mutation" in result:
        mutation = result["mutation"]
        _need(isinstance(mutation, dict) and set(mutation) == {"requestId", "replayed"} and
              isinstance(mutation["requestId"], str) and type(mutation["replayed"]) is bool,
              "unsupported native check mutation receipt")
    _need(isinstance(doc.get("id"), str) and doc["id"], "native check receipt identity absent")
    _need(isinstance(doc.get("_meta", {}).get("runtimeId"), str) and doc["_meta"]["runtimeId"],
          "native runtime identity absent")
    _need(result["runId"] == run_id, "foreign Run delivery")
    _need(isinstance(result.get("messages"), list) and type(result.get("count")) is int and
          result["count"] == len(result["messages"]),
          "delivery count mismatch")
    _need(result["timedOut"] is False and result["cancelled"] is False and
          result["connectionLost"] is False, "incomplete or interrupted delivery")
    _need(result["acknowledged"] is None, "check unexpectedly acknowledged a delivery")
    _need(type(result["replayed"]) is bool, "unproven delivery replay state")
    _need(result["count"] > 0 and isinstance(result["deliveryId"], str) and result["deliveryId"],
          "empty check is a checkpoint; no native Delivery to project")
    return result


def _check_message_shape(message: Any) -> None:
    # Orca's public message projection is snake_case. Optional source fields
    # are preserved; additional fields require a reviewed version update.
    allowed = {"id", "run_id", "from_handle", "to_handle", "subject", "body", "type",
               "priority", "thread_id", "payload", "created_at", "delivered_at", "delivery_contract"}
    _need(isinstance(message, dict) and message.keys() <= allowed, "unsupported native message controls")
    required = {"id", "run_id", "from_handle", "subject", "type"}
    _need(required <= message.keys(), "incomplete native message")
    _need(all(isinstance(message[k], str) and message[k] for k in required), "invalid native message identity")
    _need(message["type"] in {"question", "worker_done", "escalation", "status"},
          "unsupported native message type")
    for key in ("to_handle", "body", "priority", "thread_id", "payload", "created_at", "delivered_at", "delivery_contract"):
        _need(key not in message or message[key] is None or isinstance(message[key], str),
              "unsupported native message value")


def _receipt(records: dict[str, bytes], name: str, kind: str) -> dict[str, Any]:
    _need(name in records, f"missing authoritative receipt: {name}")
    doc = adapter._decode(records[name])
    adapter._check_receipt(kind, doc)
    return doc


def _check_closing(opening: dict[str, Any], closing: dict[str, Any]) -> None:
    def authority(doc):
        result = copy.deepcopy(doc.get("result"))
        # Terminal text and liveness timestamps can change while the same exact
        # authority remains current. Preserve them in sources, not in the fence.
        def strip(value):
            if isinstance(value, dict):
                for key in ("observedAt", "lastObservedAt", "lastOutputAt", "preview", "agentWait"):
                    value.pop(key, None)
                for child in value.values(): strip(child)
            elif isinstance(value, list):
                for child in value: strip(child)
        strip(result)
        return result
    _need(authority(opening) == authority(closing) and
          opening.get("_meta") == closing.get("_meta"), "native authority changed during delivery collection")


def _capture_owned(executable: Path, args: list[str], directory: Path, name: str,
                   sources: dict[str, Any], *, terminal: str | None = None) -> bytes:
    _need(len(sources) < 128, "native retrieval subprocess bound exceeded")
    argv = [str(executable), *args]
    if terminal and args[:2] == ["orchestration", "check"] and "--terminal" not in args:
        argv += ["--terminal", terminal]
    argv.append("--json") if args[-1:] != ["--version"] else None
    try:
        raw, ref = adapter._capture(argv, directory, name)
        sources[name] = ref
        _need(sum(item.get("bytes", 0) for item in sources.values()) <= 64 * 1024 * 1024,
              "native retrieval aggregate byte bound exceeded")
        return raw
    except adapter.AdapterError:
        # _capture persists partial stdout, stderr and process status before it
        # raises. Keep digests/references available to the caller on STOP.
        for suffix in (".stdout", ".stderr", ".process.json"):
            path = directory / f"{name}{suffix}"
            if path.is_file():
                sources[name + suffix] = adapter._ref(path)
        raise


def _normalize(version: str, run_id: str, records: dict[str, bytes]) -> dict[str, Any]:
    _need(version == VERSION, "unsupported CLI version")
    _need(isinstance(run_id, str) and _RUN.fullmatch(run_id), "invalid exact Run ID")
    _need(isinstance(records, dict) and "check" in records, "missing native check receipt")
    allowed_names = {"check", "status", "run-show", "task-list", "explicit-workers", "final-status",
                     "final-run-show", "final-task-list", "final-explicit-workers"}
    allowed_names |= {f"worker-show-{i}" for i in range(64)} | {f"dispatch-show-{i}" for i in range(64)}
    allowed_names |= {f"final-worker-show-{i}" for i in range(64)} | {f"final-dispatch-show-{i}" for i in range(64)}
    _need(records.keys() <= allowed_names, "unsupported retrieval operation")

    check_doc = adapter._decode(records["check"])
    check = _check_delivery_receipt(check_doc, run_id)
    opening_status = _receipt(records, "status", "status")
    opening_run = _receipt(records, "run-show", "run-show")
    task_doc = _receipt(records, "task-list", "task-list")
    inventory = _receipt(records, "explicit-workers", "explicit-workers")
    runtime = opening_status["result"]["runtime"]
    runtime_id = runtime.get("runtimeId")
    _need(opening_status["result"].get("target") == {"kind": "local"} and
          runtime.get("appVersion") == VERSION and runtime.get("state") == "ready" and
          runtime.get("reachable") is True and isinstance(runtime_id, str) and runtime_id,
          "local runtime unavailable or mismatched")
    _need(all(doc.get("_meta", {}).get("runtimeId") == runtime_id for doc in
              [check_doc, opening_status, opening_run, task_doc, inventory]), "foreign runtime receipt")
    _need(opening_run["result"]["run"]["id"] == run_id and opening_run["result"]["run"]["legacy"] == 0 and
          task_doc["result"]["runId"] == run_id and task_doc["result"]["legacyReadOnly"] is False,
          "foreign or legacy Run authority")
    _need(inventory["result"]["scope"] == {"run": run_id, "source": "flag"}, "foreign worker inventory scope")

    tasks_list = task_doc["result"]["tasks"]
    _need(type(task_doc["result"]["count"]) is int and task_doc["result"]["count"] == len(tasks_list) and
          all(not t.get("spec_truncated") for t in tasks_list), "incomplete Task inventory")
    tasks = {task["id"]: task for task in tasks_list}
    _need(len(tasks) == len(tasks_list) and all(t["run_id"] == run_id and _TASK.fullmatch(t["id"]) for t in tasks_list),
          "foreign or duplicate Task authority")
    rows = inventory["result"]["workers"]
    _need(len(rows) <= 64, "worker inventory bound exceeded")
    _need(type(inventory["result"]["page"]["total"]) is int and
          inventory["result"]["page"]["hasMore"] is False and inventory["result"]["page"]["nextCursor"] is None and
          len(rows) == inventory["result"]["page"]["total"], "partial worker inventory")
    _need(all(row["runId"] == run_id and row["taskId"] in tasks and
              _DISPATCH.fullmatch(row["dispatchId"]) for row in rows), "foreign worker inventory row")
    _need(len({row["dispatchId"] for row in rows}) == len(rows), "duplicate worker Dispatch")

    messages = check["messages"]
    message_ids = set()
    projected = []
    by_assignee: dict[str, list[dict[str, Any]]] = {}
    by_dispatch = {row["dispatchId"]: row for row in rows}
    task_by_dispatch = {row["dispatchId"]: row["taskId"] for row in rows}
    for i, message in enumerate(messages):
        _check_message_shape(message)
        _need(message["id"] not in message_ids and message["run_id"] == run_id, "foreign or duplicate delivery message")
        message_ids.add(message["id"])
        payload: dict[str, Any] = {}
        if message.get("payload"):
            payload = adapter._decode(message["payload"].encode("utf-8"))
            _need(isinstance(payload, dict), "unsupported structured message payload")
        dispatch_id = payload.get("dispatchId")
        task_id = payload.get("taskId")
        if message["type"] == "worker_done":
            _need(isinstance(dispatch_id, str) and _DISPATCH.fullmatch(dispatch_id) and
                  isinstance(task_id, str) and _TASK.fullmatch(task_id) and
                  payload.get("outcome") in {"succeeded", "failed"}, "worker_done lacks exact lifecycle IDs/outcome")
            # Missing task evidence makes acceptance incomplete, but must not
            # erase a native settlement or prevent release of its terminal.
        if dispatch_id is None or task_id is None:
            candidates = [row for row in rows
                          if row["agentTerminalHandle"] == message["from_handle"] and row["taskId"] in tasks]
            _need(len(candidates) == 1, "message sender has missing or ambiguous current Dispatch authority")
            dispatch_id, task_id = candidates[0]["dispatchId"], candidates[0]["taskId"]
        _need(dispatch_id in by_dispatch and task_by_dispatch[dispatch_id] == task_id and task_id in tasks,
              "message has foreign or mismatched Task/Dispatch IDs")
        show_name, dispatch_name = f"worker-show-{i}", f"dispatch-show-{i}"
        show_doc = _receipt(records, show_name, "worker-show")
        dispatch_doc = _receipt(records, dispatch_name, "dispatch-show")
        show = show_doc["result"]
        native_dispatch = show["dispatch"]
        current = dispatch_doc["result"]["dispatch"]
        row = by_dispatch[dispatch_id]
        _need(show_doc.get("_meta", {}).get("runtimeId") == runtime_id and
              dispatch_doc.get("_meta", {}).get("runtimeId") == runtime_id, "foreign authority runtime")
        _need(native_dispatch["id"] == current["id"] == row["dispatchId"] == dispatch_id and
              native_dispatch["taskId"] == current["task_id"] == row["taskId"] == task_id and
              native_dispatch["runId"] == current["run_id"] == run_id and
              native_dispatch["assigneeHandle"] == current["assignee_handle"] == row["agentTerminalHandle"] and
              native_dispatch["status"] == current["status"] == row["dispatchStatus"] and
              current["contract_version"] == native_dispatch["contractVersion"] == 1,
              "current Dispatch authority mismatch")
        _need(native_dispatch["hostScope"] == {"kind": "local", "hostId": "local"} and
              adapter._decode(current["host_scope"].encode()) == native_dispatch["hostScope"] and
              row["resource"]["ownerDispatchId"] == dispatch_id,
              "foreign host/runtime or terminal resource owner")
        _need(message["from_handle"] in {current["assignee_handle"], f"dispatch:{dispatch_id}"},
              "message sender is not current Dispatch assignee")
        if "taskId" in payload:
            _need(payload["taskId"] == task_id, "payload Task ID mismatch")
        if message["type"] == "worker_done":
            _need(current["status"] == "completed" and
                  tasks[task_id]["status"] == ("completed" if payload["outcome"] == "succeeded" else "failed") and
                  row["workerState"] == payload["outcome"] and
                  row["terminalState"] in {"reclaimable", "released", "retained"},
                  "worker_done has no matching authoritative settlement")
            try:
                report = adapter._decode(tasks[task_id]["result"].encode("utf-8"))
            except (ValueError, TypeError, AttributeError, UnicodeError, RecursionError):
                report = None
            report_keys = {"provenance", "outcome", "messageId", "reportedBy", "subject", "body",
                           "completedBy", "filesModified", "reportPath", "completedAt"}
            _need(isinstance(report, dict) and set(report) == report_keys and
                  report.get("provenance") == "worker_report" and report.get("messageId") == message["id"] and
                  report.get("outcome") == payload["outcome"] and
                  report.get("reportedBy") == report.get("completedBy") == message["from_handle"] and
                  report.get("subject") == message["subject"] and report.get("body") == message.get("body") and
                  report.get("filesModified") == payload.get("filesModified", []) and
                  report.get("reportPath") == payload.get("reportPath"),
                  "native Task worker_report is not linked to this exact worker_done message")
            _need(isinstance(report.get("completedAt"), str) and report["completedAt"],
                  "native worker_report completion time absent")
        item = {"native_message": message,
                "ids": {"run": run_id, "task": task_id, "dispatch": dispatch_id},
                "native_task": tasks[task_id], "native_worker": row,
                "native_worker_show": show, "native_current_dispatch": current}
        # Preserve complete source payload/body exactly; only parsed payload is
        # supplemental and never replaces the native message.
        if payload:
            item["parsed_payload"] = payload
        projected.append(item)
    final_names = {"final-status": "status", "final-run-show": "run-show",
                   "final-task-list": "task-list", "final-explicit-workers": "explicit-workers"}
    opening_by_name = {"status": opening_status, "run-show": opening_run,
                       "task-list": task_doc, "explicit-workers": inventory}
    for name, kind in final_names.items():
        closing = _receipt(records, name, kind)
        _need(closing.get("_meta", {}).get("runtimeId") == runtime_id, "foreign closing runtime receipt")
        _check_closing(opening_by_name[kind], closing)
    for i in range(len(messages)):
        for prefix, kind in (("worker-show", "worker-show"), ("dispatch-show", "dispatch-show")):
            opening_name, closing_name = f"{prefix}-{i}", f"final-{prefix}-{i}"
            opening = _receipt(records, opening_name, kind)
            closing = _receipt(records, closing_name, kind)
            _need(closing.get("_meta", {}).get("runtimeId") == runtime_id, "foreign closing authority")
            _check_closing(opening, closing)

    return {"schema": SCHEMA, "kind": "orca_delivery", "complete": True,
            "delivery": check_doc, "messages": projected,
            "authority": {"status": opening_status, "run": opening_run,
                          "task_list": task_doc, "worker_inventory": inventory},
            "errors": []}


def inspect_delivery(version: str, run_id: str, records: dict[str, bytes]) -> dict[str, Any]:
    """Check captured native receipts offline. Does not certify caller bytes."""
    result: dict[str, Any] = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                              "verification": "offline_fixture", "issues": [], "sources": {}}
    try:
        result["sources"] = {name: {"ref": f"fixture:{name}", "bytes": len(raw),
                                    "sha256": hashlib.sha256(raw).hexdigest()}
                             for name, raw in records.items()}
        result["projection"] = _normalize(version, run_id, records)
        result["status"] = "REVIEW"
    except adapter.AdapterError as exc:
        result["issues"] = [str(exc)]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError):
        result["issues"] = ["malformed or unsupported native Delivery source"]
    return result


def compact_delivery(result: dict[str, Any], source: str) -> tuple[dict[str, Any], bytes]:
    """Mechanically project verified identities and all non-narrative controls.

    Return the compact view and exact normalized bytes to retain at ``source``.
    Offline provenance stays false. No decision is authenticated by this call.
    """
    _need(result.get("status") == "REVIEW", "complete Delivery evidence required before projection")
    projection = result["projection"]
    delivery = projection["delivery"]
    delivery_controls = copy.deepcopy(delivery)
    delivery_controls["result"].pop("messages")
    collection_controls = copy.deepcopy(projection["authority"])
    collection_narratives = {}
    for task_record in collection_controls["task_list"]["result"]["tasks"]:
        collection_narratives[task_record["id"]] = {
            name: task_record.pop(name) for name in ("spec", "result")}
    collection_narratives["run_objective"] = collection_controls["run"]["result"]["run"].pop("objective")
    items = []
    for record in projection["messages"]:
        message = record["native_message"]
        payload = record.get("parsed_payload", {})
        task = copy.deepcopy(record["native_task"])
        detail = {"task_spec": task.pop("spec"), "task_result": task.pop("result"),
                  "subject": message["subject"], "collection_narratives": collection_narratives}
        worker_show = copy.deepcopy(record["native_worker_show"])
        if isinstance(worker_show.get("terminal"), dict):
            for name in ("preview", "title"):
                detail["terminal_" + name] = worker_show["terminal"].pop(name, None)
        msg_controls = {k: v for k, v in message.items() if k not in {"subject", "body"}}
        settled = message["type"] == "worker_done"
        status = ("DONE" if payload["outcome"] == "succeeded" else "FAILED") if settled else "RUNNING"
        row = record["native_worker"]
        ids = {**record["ids"], "message": message["id"],
               "delivery": delivery["result"]["deliveryId"], "terminal": row["agentTerminalHandle"],
               "worktree": row["resource"]["worktreeId"]}
        items.append({"id": message["id"], "status": status,
                      "decision": {"action": "release_settled_terminal" if settled else "process_message"},
                      "ids": ids, "evidence": [{"native_body": message.get("body"),
                                                "native_task_report": adapter._decode(record["native_task"]["result"].encode()) if settled else None}],
                      "changes": payload.get("filesModified", []), "blockers": [],
                      "controls": {"sealed": settled, "source_verified": result["source_verified"],
                                   "delivery": delivery_controls, "message": msg_controls,
                                   "task": task, "worker": row, "worker_show": worker_show,
                                   "current_dispatch": record["native_current_dispatch"],
                                   "collection_authority": collection_controls},
                      "detail": detail})
    envelope = {"schema": "luucycle.return.v1", "kind": "orca", "complete": True,
                "expected_count": delivery["result"]["count"], "items": items, "errors": []}
    raw = compact.encode(envelope)
    return compact.project(raw, source), raw


def _validate_target(run_id: str, root: str, executable: str | None, terminal: str | None,
                     *, capture_authorized: bool, consume_authorized: bool | None) -> tuple[Path, Path]:
    _need(isinstance(executable, str) and Path(executable).is_absolute(), "explicit absolute Orca executable required")
    selected = Path(executable)
    _need(selected.resolve() != Path("/usr/bin/orca") and selected.is_file() and os.access(selected, os.X_OK),
          "selected executable unavailable or screenreader forbidden")
    _need(_RUN.fullmatch(run_id) is not None, "invalid exact Run ID")
    _need(capture_authorized is True, "capture storage permission required")
    if consume_authorized is not None:
        _need(consume_authorized is True,
              "creating/replaying a native Delivery mutates the selected Run inbox; explicit collect authorization required")
    _need(not os.environ.get("ORCA_ENVIRONMENT") and not os.environ.get("ORCA_PAIRING_CODE"),
          "implicit remote target unsupported")
    if terminal is not None:
        _need(isinstance(terminal, str) and re.fullmatch(r"term_[0-9a-f-]{36}", terminal),
              "invalid exact coordinator terminal")
    root_path = Path(root).resolve(strict=True)
    _need(root_path.is_dir(), "capture root must be an existing authorized directory")
    return selected, root_path


def collect_delivery(run_id: str, capture_root: str, *, executable: str | None = None,
                     terminal: str | None = None, capture_authorized: bool = False,
                     consume_authorized: bool = False) -> dict[str, Any]:
    """Capture one native Delivery from one explicitly authorized local Run.

    `check --run` creates/replays the native Delivery and is therefore an inbox
    mutation. The raw receipt is stored before parsing. Never ack or retry it.
    """
    result: dict[str, Any] = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                              "verification": "owned_local_retrieval_with_authorized_delivery_creation",
                              "acceptance": "NOT_EVALUATED", "issues": [], "sources": {}}
    try:
        selected, root = _validate_target(run_id, capture_root, executable, terminal,
                                          capture_authorized=capture_authorized,
                                          consume_authorized=consume_authorized)
        directory = Path(tempfile.mkdtemp(prefix="orca-delivery-", dir=root))
        result["capture_directory"] = str(directory)
        receipts: dict[str, bytes] = {}

        def get(name: str, args: list[str]) -> dict[str, Any]:
            raw = _capture_owned(selected, args, directory, name, result["sources"], terminal=terminal)
            receipts[name] = raw
            doc = adapter._decode(raw)
            _need(isinstance(doc, dict) and doc.get("ok") is True and isinstance(doc.get("result"), dict),
                  "native read command failed or unsupported; inspect retained process/stderr receipt")
            return doc

        # This single default check intentionally creates/replays one Delivery.
        # It must not be retried after an ambiguous transport failure.
        version_raw = _capture_owned(selected, ["--version"], directory, "version", result["sources"])
        _need(version_raw.decode("utf-8").strip() == VERSION, "unsupported CLI version")
        guide_raw = _capture_owned(selected, ["skills", "get", "orchestration", "--json"],
                                    directory, "guide", result["sources"])
        _need(adapter._decode(guide_raw).get("name") == "orchestration", "version-matched orchestration guide unavailable")
        get("check", ["orchestration", "check", "--run", run_id])
        get("status", ["status"])
        get("run-show", ["orchestration", "run-show", "--id", run_id])
        get("task-list", ["orchestration", "task-list", "--run", run_id])
        get("explicit-workers", ["orchestration", "worker-list", "--run", run_id, "--limit", "100"])
        check_doc = adapter._decode(receipts["check"])
        empty = check_doc.get("result", {})
        if empty.get("count") == 0 and empty.get("messages") == [] and empty.get("deliveryId") is None:
            status_doc = adapter._decode(receipts["status"])
            run_doc = adapter._decode(receipts["run-show"])
            adapter._check_receipt("status", status_doc)
            adapter._check_receipt("run-show", run_doc)
            _need(empty.get("runId") == run_id and empty.get("acknowledged") is None and
                  empty.get("cancelled") is False and empty.get("connectionLost") is False and
                  run_doc["result"]["run"]["id"] == run_id and
                  check_doc.get("_meta") == status_doc.get("_meta") == run_doc.get("_meta") and
                  status_doc["result"]["runtime"]["appVersion"] == VERSION,
                  "unproven empty inbox checkpoint")
            result.update(status="CHECKPOINT", source_verified=True,
                          checkpoint="empty inbox; keep waiting", delivery_id=None)
            return result
        check = _check_delivery_receipt(adapter._decode(receipts["check"]), run_id)
        _need(check["count"] <= 64, "delivery message bound exceeded")
        # The payload and sender are native inputs; do not guess authority if an
        # exact Task/Dispatch join cannot be made.
        worker_rows = adapter._decode(receipts["explicit-workers"])["result"]["workers"]
        tasks = {x["id"]: x for x in adapter._decode(receipts["task-list"])["result"]["tasks"]}
        shows, dispatches = [], []
        for index, message in enumerate(check["messages"]):
            _check_message_shape(message)
            payload = adapter._decode(message["payload"].encode()) if message.get("payload") else {}
            task_id, dispatch_id = payload.get("taskId"), payload.get("dispatchId")
            matches = [row for row in worker_rows if message["from_handle"] in
                       {row["agentTerminalHandle"], f"dispatch:{row['dispatchId']}"}]
            if isinstance(task_id, str) and isinstance(dispatch_id, str):
                matches = [row for row in matches if row["taskId"] == task_id and row["dispatchId"] == dispatch_id]
            _need(len(matches) == 1, "message authority missing or ambiguous; no Dispatch inferred")
            row = matches[0]
            _need(row["taskId"] in tasks, "message references missing Task")
            shows.append(get(f"worker-show-{index}", ["orchestration", "worker-show", "--dispatch", row["dispatchId"]]))
            dispatches.append(get(f"dispatch-show-{index}", ["orchestration", "dispatch-show", "--task", row["taskId"]]))
        # Optimistic close fence checks all current authority used in projection.
        for name, args in (("status", ["status"]),
                           ("run-show", ["orchestration", "run-show", "--id", run_id]),
                           ("task-list", ["orchestration", "task-list", "--run", run_id]),
                           ("explicit-workers", ["orchestration", "worker-list", "--run", run_id, "--limit", "100"])):
            get("final-" + name, args)
        for index, message in enumerate(check["messages"]):
            payload = adapter._decode(message["payload"].encode()) if message.get("payload") else {}
            matches = [row for row in worker_rows if message["from_handle"] in
                       {row["agentTerminalHandle"], f"dispatch:{row['dispatchId']}"}]
            if payload.get("taskId") and payload.get("dispatchId"):
                matches = [row for row in matches if row["taskId"] == payload["taskId"] and row["dispatchId"] == payload["dispatchId"]]
            row = matches[0]
            get(f"final-worker-show-{index}", ["orchestration", "worker-show", "--dispatch", row["dispatchId"]])
            get(f"final-dispatch-show-{index}", ["orchestration", "dispatch-show", "--task", row["taskId"]])
        projection = _normalize(VERSION, run_id, receipts)
        result["projection"] = projection
        result["status"] = "REVIEW"
        result["source_verified"] = True
    except adapter.AdapterError as exc:
        result["issues"] = [str(exc)]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError):
        result["issues"] = ["native Delivery collection failed; inspect retained raw/process receipts"]
    return result


def read_dispatch_authority(run_id: str, task_id: str, dispatch_id: str, capture_root: str, *,
                            executable: str | None = None, terminal: str | None = None,
                            capture_authorized: bool = False) -> dict[str, Any]:
    """Capture and fence exact current local Task/Dispatch authority read-only."""
    result: dict[str, Any] = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                              "verification": "live_read_only_authority", "complete": False,
                              "sealed": False, "issues": [], "sources": {}}
    try:
        selected, root = _validate_target(run_id, capture_root, executable, terminal,
                                          capture_authorized=capture_authorized,
                                          consume_authorized=None)
        _need(_TASK.fullmatch(task_id) is not None and _DISPATCH.fullmatch(dispatch_id) is not None,
              "invalid exact Task or Dispatch ID")
        directory = Path(tempfile.mkdtemp(prefix="orca-authority-", dir=root))
        result["capture_directory"] = str(directory)
        records: dict[str, bytes] = {}

        def get(name: str, args: list[str], kind: str) -> dict[str, Any]:
            raw = _capture_owned(selected, args, directory, name, result["sources"], terminal=terminal)
            records[name] = raw
            doc = adapter._decode(raw)
            _need(isinstance(doc, dict) and doc.get("ok") is True and isinstance(doc.get("result"), dict),
                  "native authority command failed or unsupported; inspect retained process/stderr receipt")
            adapter._check_receipt(kind, doc)
            return doc

        version_raw = _capture_owned(selected, ["--version"], directory, "version", result["sources"])
        _need(version_raw.decode("utf-8").strip() == VERSION, "unsupported CLI version")
        guide_raw = _capture_owned(selected, ["skills", "get", "orchestration", "--json"],
                                    directory, "guide", result["sources"])
        _need(adapter._decode(guide_raw).get("name") == "orchestration", "version-matched orchestration guide unavailable")
        opening = {
            "status": get("status", ["status"], "status"),
            "run": get("run-show", ["orchestration", "run-show", "--id", run_id], "run-show"),
            "tasks": get("task-list", ["orchestration", "task-list", "--run", run_id], "task-list"),
            "workers": get("explicit-workers", ["orchestration", "worker-list", "--run", run_id, "--limit", "100"], "explicit-workers"),
            "worker": get("worker-show", ["orchestration", "worker-show", "--dispatch", dispatch_id], "worker-show"),
            "dispatch": get("dispatch-show", ["orchestration", "dispatch-show", "--task", task_id], "dispatch-show"),
        }
        status, run_doc = opening["status"], opening["run"]
        task_doc, workers_doc = opening["tasks"], opening["workers"]
        worker_doc, dispatch_doc = opening["worker"], opening["dispatch"]
        runtime = status["result"]["runtime"]
        runtime_id = runtime.get("runtimeId")
        _need(status["result"].get("target") == {"kind": "local"} and runtime.get("appVersion") == VERSION and
              runtime.get("state") == "ready" and runtime.get("reachable") is True and runtime_id,
              "local runtime unavailable or mismatched")
        _need(all(doc.get("_meta", {}).get("runtimeId") == runtime_id for doc in opening.values()),
              "foreign runtime authority")
        _need(run_doc["result"]["run"]["id"] == run_id and run_doc["result"]["run"]["legacy"] == 0 and
              task_doc["result"]["runId"] == run_id and task_doc["result"]["legacyReadOnly"] is False and
              workers_doc["result"]["scope"] == {"run": run_id, "source": "flag"}, "foreign or legacy Run")
        task_matches = [task for task in task_doc["result"]["tasks"] if task["id"] == task_id]
        worker_matches = [row for row in workers_doc["result"]["workers"] if row["dispatchId"] == dispatch_id]
        page = workers_doc["result"]["page"]
        _need(len(workers_doc["result"]["workers"]) <= 64 and
              page["hasMore"] is False and page["nextCursor"] is None and
              type(page["total"]) is int and page["total"] == len(workers_doc["result"]["workers"]) and
              type(task_doc["result"]["count"]) is int and
              task_doc["result"]["count"] == len(task_doc["result"]["tasks"]) and
              all(not task.get("spec_truncated") for task in task_doc["result"]["tasks"]),
              "current authority inventory is partial or truncated")
        _need(len(task_matches) == len(worker_matches) == 1, "exact Task or Dispatch absent/ambiguous")
        task, row = task_matches[0], worker_matches[0]
        native_dispatch = worker_doc["result"]["dispatch"]
        current = dispatch_doc["result"]["dispatch"]
        _need(worker_doc.get("_meta", {}).get("runtimeId") == dispatch_doc.get("_meta", {}).get("runtimeId") == runtime_id,
              "foreign current Dispatch authority")
        _need(task["run_id"] == row["runId"] == run_id and row["taskId"] == task_id and
              task["id"] == task_id and row["dispatchId"] == dispatch_id and
              native_dispatch["id"] == current["id"] == dispatch_id and
              native_dispatch["taskId"] == current["task_id"] == task_id and
              native_dispatch["runId"] == current["run_id"] == run_id and
              native_dispatch["assigneeHandle"] == current["assignee_handle"] == row["agentTerminalHandle"] and
              native_dispatch["status"] == current["status"] == row["dispatchStatus"] and
              native_dispatch["contractVersion"] == current["contract_version"] == 1 and
              native_dispatch["hostScope"] == {"kind": "local", "hostId": "local"} and
              adapter._decode(current["host_scope"].encode("utf-8")) == {"kind": "local", "hostId": "local"} and
              native_dispatch["retryOfDispatchId"] is None and native_dispatch["creatorDispatchId"] is None and
              current["retry_of_dispatch_id"] is None and current["creator_dispatch_id"] is None,
              "current Dispatch authority mismatch or unsupported lineage")
        for name, args, kind in (
            ("status", ["status"], "status"),
            ("run", ["orchestration", "run-show", "--id", run_id], "run-show"),
            ("tasks", ["orchestration", "task-list", "--run", run_id], "task-list"),
            ("workers", ["orchestration", "worker-list", "--run", run_id, "--limit", "100"], "explicit-workers"),
            ("worker", ["orchestration", "worker-show", "--dispatch", dispatch_id], "worker-show"),
            ("dispatch", ["orchestration", "dispatch-show", "--task", task_id], "dispatch-show"),
        ):
            closing = get("final-" + name, args, kind)
            _need(closing.get("_meta", {}).get("runtimeId") == runtime_id, "foreign closing authority")
            _check_closing(opening[name], closing)
        resource = row["resource"]
        sealed = (bool(current.get("capability_revoked_at")) or
                  current["status"] in {"completed", "failed", "stopped", "abandoned"} or
                  row["terminalState"] == "released" or resource.get("releaseState") == "released")
        result.update({"status": "REVIEW", "source_verified": True, "complete": True,
                       "sealed": sealed, "runtime_id": runtime_id,
                       "observed_at": datetime.now(timezone.utc).isoformat(),
                       "ids": {"run": run_id, "task": task_id, "dispatch": dispatch_id,
                               "assignee": current["assignee_handle"]},
                       "task_status": task["status"], "dispatch_status": current["status"],
                       "worker_state": row["workerState"], "terminal_state": row["terminalState"],
                       "native": {"task": task, "worker": row, "worker_show": worker_doc["result"],
                                  "current_dispatch": current}})
    except adapter.AdapterError as exc:
        result["issues"] = [str(exc)]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError):
        result["issues"] = ["native authority retrieval failed or unsupported; inspect retained source/process receipts"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser("collect-delivery")
    live.add_argument("--run", required=True)
    live.add_argument("--orca-executable", required=True)
    live.add_argument("--capture-root", required=True)
    live.add_argument("--terminal")
    live.add_argument("--capture-authorized", action="store_true")
    live.add_argument("--consume-authorized", action="store_true",
                      help="authorize creating/replaying one native Delivery for this exact Run")
    authority = sub.add_parser("read-dispatch")
    authority.add_argument("--run", required=True)
    authority.add_argument("--task", required=True)
    authority.add_argument("--dispatch", required=True)
    authority.add_argument("--orca-executable", required=True)
    authority.add_argument("--capture-root", required=True)
    authority.add_argument("--terminal")
    authority.add_argument("--capture-authorized", action="store_true")
    fixture = sub.add_parser("fixture-delivery")
    fixture.add_argument("--run", required=True)
    fixture.add_argument("--version", required=True)
    fixture.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    if args.command == "collect-delivery":
        result = collect_delivery(args.run, args.capture_root, executable=args.orca_executable,
                                  terminal=args.terminal, capture_authorized=args.capture_authorized,
                                  consume_authorized=args.consume_authorized)
    elif args.command == "read-dispatch":
        result = read_dispatch_authority(args.run, args.task, args.dispatch, args.capture_root,
                                         executable=args.orca_executable, terminal=args.terminal,
                                         capture_authorized=args.capture_authorized)
    else:
        try:
            directory = Path(args.directory).resolve(strict=True)
            records = {p.stem: p.read_bytes() for p in directory.glob("*.json") if p.name != "provenance.json"}
            result = inspect_delivery(args.version, args.run, records)
        except (OSError, ValueError, TypeError):
            result = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                      "issues": ["unable to read fixture input"]}
    try:
        if result["status"] == "REVIEW" and args.command != "read-dispatch":
            capture = result.get("capture_directory")
            source = str(Path(capture) / "normalized.json") if capture else f"fixture-normalized:{directory}"
            projected, normalized = compact_delivery(result, source)
            if capture:
                adapter._store(Path(capture) / "delivery-evidence.json", compact.encode(result))
                adapter._store(Path(source), normalized)
            result = {"schema": SCHEMA, "status": projected["status"],
                      "source_verified": result["source_verified"],
                      "capture_directory": capture, "projection": projected,
                      "verification": result["verification"]}
        elif result["status"] == "REVIEW":
            capture = Path(result["capture_directory"])
            adapter._store(capture / "authority-evidence.json", compact.encode(result))
            native = copy.deepcopy(result.pop("native"))
            native["task"].pop("spec", None)
            native["task"].pop("result", None)
            if isinstance(native["worker_show"].get("terminal"), dict):
                native["worker_show"]["terminal"].pop("preview", None)
                native["worker_show"]["terminal"].pop("title", None)
            result["native_controls"] = native
    except (adapter.AdapterError, OSError, ValueError, TypeError) as exc:
        result = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                  "issues": ["projection/retention failed; inspect authorized capture"],
                  "capture_directory": result.get("capture_directory")}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return 0 if result["status"] in {"REVIEW", "CHECKPOINT"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
