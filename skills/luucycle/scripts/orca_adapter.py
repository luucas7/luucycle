#!/usr/bin/env python3
"""Fail-closed Orca 1.4.229 local inventory boundary, standard library only.

``inspect_fixture`` checks offline specimens, never authenticates a source.
``collect`` owns fixed read-only subprocess retrieval and explicit capture storage.
No mutation, inbox consumption, acknowledgment, remote operation, or worker input.
REVIEW means inspect controls, not permission or accepted worker completion.
Supported native lifecycle: local contract-v1 succeeded/completed/released workers
with current Dispatch authority and no retry/creator lineage. Other lifecycle,
remote, inbox/delivery, or version shapes stop. Live retrieval is bounded to 64
workers, 128 subprocess calls, 30 seconds and 8 MiB per stream, 64 MiB total.
Archive metadata is retained, but archive content is not retrieved or certified.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import tempfile
import threading
from pathlib import Path
from decimal import Decimal
from typing import Any

VERSION = "1.4.229"
SCHEMA = "luucycle.orca-adapter.v1"


class AdapterError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdapterError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise AdapterError("non-finite JSON number")


def _float(value):
    result = float(value)
    _require(math.isfinite(result) and Decimal(value) == Decimal(str(result)), "unrepresentable JSON number")
    return result


def _decode(raw):
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                        parse_constant=_constant, parse_float=_float)
    json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return result


def _require(condition, issue):
    if not condition:
        raise AdapterError(issue)


def _shape(keys, **children):
    return {**dict.fromkeys(keys.split()), **children}


# Deliberately closed 1.4.229 shapes, not a schema inferred from caller data.
# Unknown controls stop and remain available by native source hash/reference.
_RESOURCE = _shape("id state terminalState ownershipState releaseState retainedReason terminalHandle worktreeId "
                   "endpointId endpointIncarnation originDispatchId ownerDispatchId releaseRequestedAt "
                   "releaseCompletedAt releaseError recoveryAttemptCount lastRecoveryAt",
                   archive=_shape("source status truncated errors"))
_PROJECTION = _shape("id dispatchId taskId runId role parent provider outcome",
    host=_shape("kind id"), workspace=_shape("id kind"),
    stage=_shape("worker dispatch detail activity"), liveness=_shape("verdict source"),
    evidence=_shape("durable liveStatus lastObservedAt"), resource=_RESOURCE,
    nextAction=_shape("kind argv"), attention=_shape("categories requiresAction"))
_ROW = _shape("dispatchId taskId runId workerState dispatchStatus agentTerminalHandle terminalState",
              resource=_RESOURCE, projection=_PROJECTION)
_LAUNCH = _shape("agent model effort")
_EFFECT = _shape("kind action id role state surface")
_WORKER = _shape("dispatchId runtimeEpoch state stage worktreeId agentTerminalHandle setupState lastError "
                 "failedStage createdAt updatedAt", effects=[_EFFECT], residualResources=[_EFFECT],
    startOptions=_shape("worktree resolvedWorktreeId name repo baseBranch terminal agent timeoutMs setup setupSource",
        mode=_shape("mode preferred reason detail"), launch=_shape("", requested=_LAUNCH, effective=_LAUNCH)))
_DISPATCH = _shape("id runId taskId task_id contractVersion assigneeHandle assigneePaneKey processIncarnation "
                   "capabilityRevokedAt retryOfDispatchId creatorDispatchId status failureCount lastFailure "
                   "terminationReason depth dispatchedAt completedAt createdAt lastHeartbeatAt",
                   hostScope=_shape("kind hostId"))
_CURRENT = _shape("id run_id task_id assignee_handle assignee_orca_session_id assignee_pane_key capability_hash "
                  "capability_revoked_at completed_at consumer_generation contract_version created_at creator_dispatch_id "
                  "creator_handle creator_orca_session_id creator_pane_key depth dispatched_at failure_count host_scope "
                  "last_failure last_heartbeat_at launch_token_hash process_incarnation retry_of_dispatch_id status termination_reason")
_RESULTS = {
    "status": _shape("", target=_shape("kind"), app=_shape("running pid desktopWindowStatus"),
        graph=_shape("state"), runtime=_shape("state reachable connectionState runtimeId appVersion capabilities",
            remoteUpdateSupport=_shape("installMode automatic reason"))),
    "run-show": _shape("", run=_shape("id objective coordinator_handle consumer_generation legacy created_at updated_at")),
    "task-list": _shape("runId legacyReadOnly count", tasks=[_shape(
        "id run_id parent_id created_by_terminal_handle task_title display_name spec status deps result created_at "
        "completed_at created_by_pane_key created_by_process_incarnation created_by_run_generation spec_truncated")]),
    "explicit-workers": _shape("warnings", workers=[_ROW], counts=_shape("released"),
        page=_shape("limit total hasMore nextCursor"), scope=_shape("run source")),
    "worker-show": _shape("terminal", dispatch=_DISPATCH, worker=_WORKER, projection=_PROJECTION,
        observation=_shape("exactWorker status"), terminalResource=_RESOURCE),
    "dispatch-show": _shape("", dispatch=_CURRENT),
}

# Native shape recognition is shared with the live inbox reader. Inventory
# normalization below still enforces its narrower settled/released lifecycle.
_PROJECTION["provider"] = (_shape("id model"), None)
_PROJECTION["liveness"] = _shape("verdict source reason observedAt")
_RESULTS["explicit-workers"]["counts"] = _shape("active reclaimable released retained releasing release_unknown")
_RESULTS["worker-show"]["terminal"] = (_shape(
    "handle ptyId incarnationId orphaned recordedPaneKey worktreeId worktreePath branch tabId leafId title "
    "connected writable lastOutputAt preview executionHostId agentIdentity paneRuntimeId rendererGraphEpoch agentWait"), None)
_RESULTS["worker-show"]["observation"] = _shape("exactWorker status agentWait")
_RESULTS["worker-show"]["terminal"][0]["exitCause"] = (_shape("kind"), None)
_RESULTS["task-list"]["tasks"][0].update(assignee_handle=None, dispatch_id=None)


def _check_shape(value, shape):
    if isinstance(shape, tuple):
        for candidate in shape:
            if candidate is None:
                if value is None:
                    return
                continue
            try:
                _check_shape(value, candidate)
                return
            except AdapterError:
                pass
        raise AdapterError("unsupported nullable native shape")
    elif isinstance(shape, dict):
        _require(isinstance(value, dict) and value.keys() <= shape.keys(), "unsupported native control shape")
        for key, child in value.items():
            _check_shape(child, shape[key])
    elif isinstance(shape, list):
        _require(isinstance(value, list), "unsupported native collection shape")
        for child in value:
            _check_shape(child, shape[0])
    else:
        _require(not isinstance(value, dict) and
                 (not isinstance(value, list) or all(not isinstance(x, (dict, list)) for x in value)),
                 "unsupported native scalar shape")


def _check_receipt(name, doc):
    kind = ("worker-show" if name.startswith("worker-show-") else
            "dispatch-show" if name.startswith("dispatch-show-") else
            "explicit-workers" if name.startswith("workers-page-") else name)
    _require(isinstance(doc, dict) and doc.get("ok") is True and isinstance(doc.get("result"), dict),
             "native error or unsupported envelope")
    _require(not doc.get("error") and not doc.get("errors") and
             not doc["result"].get("error") and not doc["result"].get("errors") and
             not doc["result"].get("partialHostErrors"), "unresolved native error")
    _check_shape(doc, _shape("id ok", result=_RESULTS[kind], _meta=_shape("runtimeId")))
    _require((kind == "status" and doc.get("id") == "local-status") or
             (kind != "status" and isinstance(doc.get("id"), str) and
              re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", doc["id"])),
             "native receipt identity absent or malformed")


def _normalize(version: str, run_id: str, records: dict[str, bytes]) -> dict[str, Any]:
    _require(version == VERSION, "unsupported CLI version")
    _require(isinstance(records, dict) and {"status", "explicit-workers", "run-show", "task-list"} <= records.keys(),
             "missing authoritative receipts")
    _require(all(name in {"status", "explicit-workers", "run-show", "task-list"} or
                 name.startswith("worker-show-") or name.startswith("dispatch-show-") or name.startswith("workers-page-") for name in records),
             "unsupported operation")
    parsed = {name: _decode(raw) for name, raw in records.items()}
    for name, doc in parsed.items():
        _check_receipt(name, doc)
    runtime = parsed["status"]["result"]["runtime"]
    _require(runtime["appVersion"] == VERSION, "unsupported runtime version")
    first = parsed["explicit-workers"]["result"]
    listing = copy.deepcopy(first)
    rows = []
    page_controls = []
    cursors = set()
    index = 0
    while True:
        name = "explicit-workers" if index == 0 else f"workers-page-{index}"
        _require(name in parsed, "missing inventory page")
        current = parsed[name]["result"]
        page = current["page"]
        _require(current["scope"] == {"run": run_id, "source": "flag"}, "unproven Run scope")
        _require(not current.get("partialHostErrors") and not current.get("errors"), "partial source errors")
        _require(type(page["total"]) is int and page["total"] >= 0 and page["total"] == first["page"]["total"],
                 "inventory total mismatch")
        _require(type(page["limit"]) is int and 1 <= page["limit"] <= 100 and
                 len(current["workers"]) <= page["limit"] and page["limit"] == first["page"]["limit"],
                 "invalid page size")
        _require(type(page["hasMore"]) is bool, "unproven page completeness")
        warnings = current.get("warnings", [])
        expected_warning = (f"Showing {len(current['workers'])} of {page['total']} Dispatches, newest first; "
                            "more are on later pages. Follow page.nextCursor with --cursor.")
        _require(warnings == [] or (page["hasMore"] and warnings == [expected_warning]),
                 "unsupported native inventory warning")
        _require(current["counts"] == first["counts"], "inventory counts changed")
        rows.extend(current["workers"])
        page_controls.append({"envelope": {k: v for k, v in parsed[name].items() if k != "result"},
                              "result": {k: v for k, v in current.items() if k != "workers"}})
        if not page["hasMore"]:
            _require(page["nextCursor"] is None, "unfollowed cursor")
            break
        cursor = page["nextCursor"]
        _require(isinstance(cursor, str) and cursor and cursor not in cursors and current["workers"],
                 "invalid or repeated page cursor")
        cursors.add(cursor)
        index += 1
        _require(index < 100, "inventory page bound exceeded")
    _require(sum(name.startswith("workers-page-") for name in parsed) == index,
             "extra or noncontiguous pages")
    _require(len(rows) == first["page"]["total"], "inventory total mismatch")
    _require(len({row["dispatchId"] for row in rows}) == len(rows), "duplicate Dispatch ID")
    from collections import Counter
    counts = dict(Counter(row["terminalState"] for row in rows))
    _require(all(type(v) is int and v >= 0 for v in first["counts"].values()) and counts == first["counts"],
             "inventory counts mismatch")
    listing["workers"] = rows
    task_receipt = parsed["task-list"]["result"]
    _require(type(task_receipt["count"]) is int and task_receipt["count"] == len(task_receipt["tasks"]),
             "task count mismatch")
    _require(all(not task.get("spec_truncated") for task in task_receipt["tasks"]), "truncated task source")
    tasks = {task["id"]: task for task in task_receipt["tasks"]}
    _require(len(tasks) == task_receipt["count"], "duplicate Task ID")
    _require(tasks and len(rows) == len(tasks) and {row["taskId"] for row in rows} == set(tasks),
             "unsupported empty scope or unmatched Task/worker inventory")
    run = parsed["run-show"]["result"]["run"]
    shows = {doc["result"]["dispatch"]["id"]: doc["result"]
             for name, doc in parsed.items() if name.startswith("worker-show-")}
    _require(isinstance(run_id, str) and re.fullmatch(r"run_[0-9a-f]{12}", run_id), "invalid exact Run ID")
    _require(runtime["state"] == "ready" and runtime["reachable"] is True and
             parsed["status"]["result"]["target"] == {"kind": "local"}, "local runtime unavailable")
    runtime_id = runtime["runtimeId"]
    _require(isinstance(runtime_id, str) and runtime_id, "runtime identity absent")
    _require(all(doc.get("_meta", {}).get("runtimeId") == runtime_id for doc in parsed.values()),
             "foreign runtime receipt")
    _require(run["id"] == run_id and run["legacy"] == 0 and task_receipt["runId"] == run_id and
             task_receipt["legacyReadOnly"] is False, "foreign or legacy Run")
    for task in tasks.values():
        _require(isinstance(task["spec"], str) and isinstance(task["result"], str), "unsupported task narrative shape")
        _require(re.fullmatch(r"task_[0-9a-f]{12}", task["id"]) and task["run_id"] == run_id,
                 "foreign Task record")
        _require(task["parent_id"] is None or task["parent_id"] in tasks, "missing parent Task")
        deps = _decode(task["deps"].encode())
        _require(isinstance(deps, list) and len(deps) == len(set(deps)) and
                 all(dep in tasks and dep != task["id"] for dep in deps), "missing dependency Task")
    _require(len(shows) == sum(name.startswith("worker-show-") for name in parsed) == len(rows) and
             set(shows) == {row["dispatchId"] for row in rows}, "missing or duplicate worker authority")
    latest = {doc["result"]["dispatch"]["task_id"]: doc for name, doc in parsed.items()
              if name.startswith("dispatch-show-")}
    _require(len(latest) == len(rows) == sum(name.startswith("dispatch-show-") for name in parsed),
             "missing or ambiguous current Dispatch authority")
    items = []
    for row in listing["workers"]:
        _require(re.fullmatch(r"ctx_[0-9a-f]{12}", row["dispatchId"]) and row["runId"] == run_id and
                 row["taskId"] in tasks, "foreign worker ID")
        show = shows[row["dispatchId"]]
        dispatch = show["dispatch"]
        current_dispatch = latest[row["taskId"]]["result"]["dispatch"]
        _require(current_dispatch["id"] == dispatch["id"] == row["dispatchId"] and
                 current_dispatch["task_id"] == row["taskId"] and current_dispatch["run_id"] == run_id and
                 current_dispatch["status"] == dispatch["status"] and
                 current_dispatch["assignee_handle"] == dispatch["assigneeHandle"] and
                 current_dispatch["process_incarnation"] == dispatch["processIncarnation"] and
                 current_dispatch["contract_version"] == dispatch["contractVersion"] == 1 and
                 _decode(current_dispatch["host_scope"].encode("utf-8")) == dispatch["hostScope"] == {"kind": "local", "hostId": "local"},
                 "current Dispatch authority mismatch or unsupported host/contract")
        _require(type(current_dispatch["contract_version"]) is int and type(dispatch["contractVersion"]) is int,
                 "unsupported Dispatch contract type")
        _require(dispatch["retryOfDispatchId"] is None and dispatch["creatorDispatchId"] is None and
                 current_dispatch["retry_of_dispatch_id"] is None and current_dispatch["creator_dispatch_id"] is None,
                 "unretrieved Dispatch lineage unsupported")
        worker = show["worker"]
        projection = row["projection"]
        _require(projection["outcome"] == "succeeded" and
                 projection["attention"]["requiresAction"] is False and
                 projection["nextAction"] == {"kind": "none", "argv": []},
                 "unresolved native outcome or action-required control")
        resource = row["resource"]
        _require(re.fullmatch(r"wtr_[0-9a-f]{12}", resource["id"]), "unsupported resource ID")
        for candidate in (resource, show["terminalResource"], projection["resource"], show["projection"]["resource"]):
            # Native projections intentionally have different key sets. Validate
            # each known cross-reference that is actually present, not shape equality.
            for key, value in candidate.items():
                if key in {"state", "terminalState", "ownershipState", "releaseState"}:
                    _require(value == "released", "unresolved resource lifecycle")
                elif key in {"retainedReason", "releaseError"}:
                    _require(value is None, "unresolved resource retention or release error")
                if key in resource:
                    _require(value == resource[key], "resource projection authority mismatch")
        _require(projection["liveness"]["verdict"] == "exited" and
                 show["projection"]["resource"]["id"] == resource["id"] and
                 show["projection"]["resource"]["ownerDispatchId"] == row["dispatchId"],
                 "unsupported liveness or foreign projected resource")
        _require((row["workerState"], row["dispatchStatus"], row["terminalState"]) ==
                 ("succeeded", "completed", "released"), "unsupported native lifecycle shape")
        _require(tasks[row["taskId"]]["status"] == "completed", "Task settlement mismatch")
        _require(dispatch["id"] == row["dispatchId"] and
                 dispatch["taskId"] == dispatch["task_id"] == row["taskId"] and
                 dispatch["runId"] == run_id and dispatch["status"] == row["dispatchStatus"],
                 "foreign Dispatch authority")
        _require(worker["dispatchId"] == row["dispatchId"] and worker["state"] == row["workerState"] and
                 worker["agentTerminalHandle"] == dispatch["assigneeHandle"] == row["agentTerminalHandle"],
                 "foreign worker terminal authority")
        _require({k: v for k, v in show["projection"].items() if k != "resource"} ==
                 {k: v for k, v in projection.items() if k != "resource"} and
                 show["projection"]["resource"]["state"] == projection["resource"]["state"] == row["terminalState"] and
                 projection["id"] == projection["dispatchId"] == row["dispatchId"] and
                 projection["taskId"] == row["taskId"] and projection["runId"] == run_id,
                 "projection authority mismatch")
        _require(resource == show["terminalResource"] and
                 resource["terminalHandle"] == row["agentTerminalHandle"] and
                 resource["ownerDispatchId"] == resource["originDispatchId"] == row["dispatchId"] and
                 resource["worktreeId"] == worker["worktreeId"] == projection["workspace"]["id"],
                 "resource authority mismatch")
        _require(resource["ownershipState"] == resource["releaseState"] == "released" and
                 resource["releaseError"] is None and worker["lastError"] is None and not worker.get("failedStage"),
                 "unresolved worker error")
        archive = resource["archive"]
        _require(isinstance(archive, dict) and archive.get("status") == "captured" and
                 archive.get("source") in {"terminal", "transcript"} and not archive.get("truncated") and
                 not archive.get("errors"), "malformed or truncated archive metadata")
        task = copy.deepcopy(tasks[row["taskId"]])
        run_controls = copy.deepcopy(run)
        detail = {"task_spec": task.pop("spec"), "task_result": task.pop("result"),
                  "run_objective": run_controls.pop("objective")}
        items.append({"id": row["dispatchId"], "status": "DONE", "decision": None,
                      "ids": {"run": run_id, "task": row["taskId"],
                              "dispatch": row["dispatchId"], "terminal": row["agentTerminalHandle"]},
                      "evidence": [], "changes": [], "blockers": [],
                      "controls": {"sealed": True, "native_worker": row,
                                   "native_worker_show": shows[row["dispatchId"]],
                                   "native_task": task, "native_run": run_controls,
                                   "native_current_dispatch": latest[row["taskId"]],
                                   "native_context": {
                                       "status": parsed["status"], "inventory_pages": page_controls,
                                       "task_list": {"envelope": {k: v for k, v in parsed["task-list"].items() if k != "result"},
                                                     "result": {k: v for k, v in task_receipt.items() if k != "tasks"}},
                                       "run_show": {"envelope": {k: v for k, v in parsed["run-show"].items() if k != "result"},
                                                    "result": {k: v for k, v in parsed["run-show"]["result"].items() if k != "run"}},
                                       "worker_show": {k: v for k, v in next(doc for name, doc in parsed.items()
                                                       if name.startswith("worker-show-") and
                                                       doc["result"]["dispatch"]["id"] == row["dispatchId"]).items()
                                                       if k != "result"}}},
                      "detail": detail})
    return {"schema": "luucycle.return.v1", "kind": "orca", "complete": True,
            "expected_count": listing["page"]["total"], "items": items, "errors": []}


def inspect_fixture(version: str, run_id: str, records: dict[str, bytes], *, expectations=None) -> dict[str, Any]:
    """Offline structure/cross-reference checks only; caller bytes are not trusted."""
    result = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
              "verification": "offline_fixture", "issues": []}
    try:
        result["sources"] = {name: {"ref": f"fixture:{name}", "bytes": len(raw),
                                    "sha256": hashlib.sha256(raw).hexdigest()}
                             for name, raw in records.items()}
        result["envelope"] = _normalize(version, run_id, records)
        result["status"] = "REVIEW"
        result["acceptance"] = _apply_expectations(result["envelope"], expectations)
        if result["acceptance"] == "INCOMPLETE":
            result["status"] = "STOP"
    except AdapterError as exc:
        result["status"] = "STOP"
        result["issues"] = [str(exc)]
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError):
        result["status"] = "STOP"
        result["issues"] = ["malformed or unsupported native receipt"]
    return result


def validate_task_evidence(expectation, report, *, task_id, dispatch_id, source_complete):
    """Check task-scoped evidence, not authenticity, actual loading, or authority.

    Expectations are caller policy. Reports are untrusted worker assertions. The
    local file digest proves only current content at the exact expected path.
    Live callers must separately bind the report to a retrieved native Task.
    """
    result = {"status": "STOP", "source_verified": False, "acceptance": "NOT_GRANTED",
              "issues": [], "next": "inspect_existing_records",
              "limits": "not proof of worker loading"}
    try:
        _require(source_complete is True, "acceptance incomplete: source retrieval unproven")
        _require(isinstance(expectation, dict) and isinstance(report, dict), "task evidence missing")
        _require(report["schema"] == "luucycle.task-evidence.v1", "unsupported task evidence schema")
        _require(report["task_id"] == task_id and report["dispatch_id"] == dispatch_id,
                 "foreign task evidence")
        skill = expectation["routed_skill"]
        _require(isinstance(skill, dict) and set(skill) == {"identity", "path", "sha256"} and
                 all(isinstance(value, str) and value for value in skill.values()) and
                 re.fullmatch(r"[0-9a-f]{64}", skill["sha256"]) and Path(skill["path"]).is_absolute(),
                 "routed skill identity/path/hash policy required")
        _require(report["routed_skill"] == report["loaded_skill"] == skill, "routed/loaded skill mismatch")
        path = Path(skill["path"])
        _require(path.is_file() and path.stat().st_size <= 1024 * 1024 and
                 hashlib.sha256(path.read_bytes()).hexdigest() == skill["sha256"],
                 "loaded skill path/hash evidence mismatch")
        permissions = expectation["permissions"]
        writes = report["writes"]
        _require(set(permissions) == {"artifact_write", "report_write"} and
                 all(type(value) is bool for value in permissions.values()) and
                 set(writes) == {"artifact", "report"} and all(type(value) is bool for value in writes.values()),
                 "explicit storage permissions and write declarations required")
        _require(all(not writes[k] or permissions[k + "_write"] for k in writes), "unauthorized artifact/report write")
        storage = report["storage"]
        _require(expectation["storage"] == storage["kind"], "report storage policy mismatch")
        if storage["kind"] == "existing_record":
            _require(storage["ref"] == f"orca:task:{task_id}:result" and not any(writes.values()),
                     "existing read-only report record required")
        elif storage["kind"] == "artifact":
            _require(permissions["artifact_write"] and permissions["report_write"] and
                     writes["artifact"] and writes["report"], "artifact/report storage permission required")
            _require(storage["path"] == expectation["report_path"] and Path(storage["path"]).is_absolute() and
                     re.fullmatch(r"[0-9a-f]{64}", storage["sha256"]), "exact report path/hash policy required")
            report_path = Path(storage["path"])
            _require(report_path.is_file() and report_path.stat().st_size <= 8 * 1024 * 1024,
                     "report artifact unavailable or oversized")
            raw_report = report_path.read_bytes()
            _require(hashlib.sha256(raw_report).hexdigest() == storage["sha256"],
                     "report artifact content mismatch")
            artifact = _decode(raw_report)
            # The storage-free receipt avoids a circular self-hash. This binds
            # content to assertions, not assertions to truth or acceptance.
            _require(isinstance(artifact, dict) and set(artifact) == {"schema", "receipt", "detail"} and
                     artifact["schema"] == "luucycle.task-report.v1" and
                     artifact["receipt"] == {k: v for k, v in report.items() if k != "storage"} and
                     isinstance(artifact["detail"], str) and artifact["detail"].strip(),
                     "report artifact lacks exact task receipt binding or detail")
        else:
            raise AdapterError("unsupported report storage")
        result["status"] = "EVIDENCE_REVIEW"
        result["reported"] = copy.deepcopy(report)
    except AdapterError as exc:
        result["issues"] = [str(exc)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result["issues"] = ["acceptance incomplete: malformed or unavailable task evidence"]
    return result


def _apply_expectations(envelope, expectations):
    if expectations is None:
        return "NOT_EVALUATED"
    _require(isinstance(expectations, dict) and expectations, "nonempty exact Task evidence expectations required")
    by_task = {item["ids"]["task"]: item for item in envelope["items"]}
    _require(set(expectations) <= by_task.keys(), "expected Task absent from native worker scope")
    complete = True
    for task_id, policy in expectations.items():
        item = by_task[task_id]
        try:
            report = _decode(item["detail"]["task_result"].encode("utf-8"))
        except (ValueError, TypeError, AttributeError, UnicodeError, RecursionError):
            report = None
        check = validate_task_evidence(policy, report, task_id=task_id,
                                       dispatch_id=item["ids"]["dispatch"], source_complete=envelope["complete"])
        item["controls"]["task_evidence"] = check
        if check["status"] != "EVIDENCE_REVIEW":
            complete = False
            item["blockers"].append({"task_evidence": check["issues"]})
            item["decision"] = {"action": "inspect_existing_records", "worker_input_allowed": False}
    return "EVIDENCE_REVIEW_NOT_ACCEPTED" if complete else "INCOMPLETE"


def _ref(path):
    raw = path.read_bytes()
    return {"ref": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _store(path, raw):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(raw)
    return _ref(path)


def _capture(argv, directory, name, *, timeout=30, max_bytes=8 * 1024 * 1024):
    """Retain bounded raw streams before parsing; never surface stderr text."""
    paths = [directory / (name + suffix) for suffix in (".stdout", ".stderr")]
    outputs = [os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") for p in paths]
    exceeded = threading.Event()
    failures = []
    process = None
    timed_out = False
    threads = []
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        def drain(source, target):
            remaining = max_bytes
            try:
                while True:
                    data = source.read(min(65536, remaining + 1))
                    if not data:
                        break
                    target.write(data[:remaining])
                    if len(data) > remaining:
                        exceeded.set()
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    remaining -= len(data)
            except (OSError, ValueError):
                failures.append(True)
            finally:
                source.close()
                target.close()
        threads = [threading.Thread(target=drain, args=pair, daemon=True)
                   for pair in zip((process.stdout, process.stderr), outputs)]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise AdapterError("read-only command timed out; retained capture is incomplete")
        finally:
            for thread in threads:
                thread.join(timeout=2)
        _require(not exceeded.is_set() and not failures and all(not t.is_alive() for t in threads),
                 "read-only capture exceeded bound or is incomplete")
    finally:
        for output in outputs:
            if not output.closed:
                output.close()
        complete = process is not None and process.returncode is not None and not timed_out and not exceeded.is_set() and not failures and all(not t.is_alive() for t in threads)
        receipt = {"argv": list(argv), "exit_code": process.returncode if process is not None else None,
                   "complete": complete, "timed_out": timed_out, "truncated": exceeded.is_set(),
                   "stdout": _ref(paths[0]), "stderr": _ref(paths[1]),
                   "successful": bool(complete and process.returncode == 0 and paths[1].stat().st_size == 0)}
        _store(directory / (name + ".process.json"), (json.dumps(receipt, sort_keys=True) + "\n").encode())
    _require(process.returncode == 0, "read-only command failed; inspect retained exit/stderr")
    _require(paths[1].stat().st_size == 0, "read-only command emitted stderr; inspect retained source")
    return paths[0].read_bytes(), _ref(paths[0])


def collect(run_id: str, capture_root: str, *, executable: str | None = None,
            capture_authorized: bool = False, expectations=None) -> dict[str, Any]:
    """Retrieve one exact local Run. No caller JSON can become source-verified.

    Storage must already be authorized; Audit callers must stop instead. The
    executable must be explicitly selected by absolute path; there is no search
    or fallback. This assumes a trusted selected runtime, not authentication of
    an adversarial binary. Diagnostics never certify archives or accept work.
    """
    result = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
              "verification": "live_read_only_source", "acceptance": "NOT_EVALUATED",
              "issues": [], "sources": {}}
    try:
        _require(isinstance(executable, str) and executable and Path(executable).is_absolute(),
                 "explicit absolute Orca executable required")
        selected = Path(executable)
        _require(selected.resolve() != Path("/usr/bin/orca") and selected.is_file() and
                 os.access(selected, os.X_OK), "selected executable unavailable or screenreader forbidden")
        _require(capture_authorized is True, "capture storage permission required; no Audit writes")
        _require(isinstance(run_id, str) and re.fullmatch(r"run_[0-9a-f]{12}", run_id), "invalid exact Run ID")
        _require(not os.environ.get("ORCA_ENVIRONMENT") and not os.environ.get("ORCA_PAIRING_CODE"),
                 "implicit remote target unsupported")
        root = Path(capture_root).resolve(strict=True)
        _require(root.is_dir(), "capture root must be an existing authorized directory")
        directory = Path(tempfile.mkdtemp(prefix="orca-native-", dir=root))
        result["capture_directory"] = str(directory)
        receipts = {}
        total = 0
        def get(name, args, *, native=True):
            nonlocal total
            _require(len(result["sources"]) < 128, "read-only retrieval count bound exceeded")
            raw, ref = _capture([executable, *args], directory, name)
            result["sources"][name] = ref
            total += len(raw)
            _require(total <= 64 * 1024 * 1024, "total capture bound exceeded")
            if native:
                doc = _decode(raw)
                _require(isinstance(doc, dict) and doc.get("ok") is True and isinstance(doc.get("result"), dict),
                         "native command failed or unsupported receipt")
                receipts[name] = raw
                return doc
            return raw
        version = get("version", ["--version"], native=False).decode("utf-8").strip()
        _require(version == VERSION, "unsupported CLI version")
        guide = get("guide", ["skills", "get", "orchestration", "--json"], native=False)
        _require(_decode(guide).get("name") == "orchestration", "version-matched guide unavailable")
        get("status", ["status", "--json"])
        get("run-show", ["orchestration", "run-show", "--id", run_id, "--json"])
        tasks = get("task-list", ["orchestration", "task-list", "--run", run_id, "--json"])
        cursor = None
        dispatches = []
        for index in range(64):
            args = ["orchestration", "worker-list", "--run", run_id, "--limit", "100", "--json"]
            if cursor is not None:
                args += ["--cursor", cursor]
            name = "explicit-workers" if index == 0 else f"workers-page-{index}"
            doc = get(name, args)
            dispatches.extend(row["dispatchId"] for row in doc["result"]["workers"])
            _require(len(dispatches) <= 64, "worker authority retrieval bound exceeded")
            page = doc["result"]["page"]
            if page["hasMore"] is False:
                break
            _require(page["hasMore"] is True and isinstance(page["nextCursor"], str), "unproven page completeness")
            _require(page["nextCursor"] != cursor, "repeated page cursor")
            cursor = page["nextCursor"]
        else:
            raise AdapterError("page retrieval bound exceeded")
        for index, dispatch in enumerate(dispatches):
            _require(re.fullmatch(r"ctx_[0-9a-f]{12}", dispatch), "invalid exact Dispatch ID")
            show = get(f"worker-show-{index}", ["orchestration", "worker-show", "--dispatch", dispatch, "--json"])
            task_id = show["result"]["dispatch"]["taskId"]
            _require(re.fullmatch(r"task_[0-9a-f]{12}", task_id), "invalid exact Task ID")
            get(f"dispatch-show-{index}", ["orchestration", "dispatch-show", "--task", task_id, "--json"])
        envelope = _normalize(version, run_id, receipts)
        opening = dict(receipts)
        # Optimistic closing fence, not a lock or atomic snapshot. Any mismatch
        # stops; every closing authority is validated as a native receipt too.
        closing = dict(opening)
        for name in ("run-show", "task-list", *[n for n in opening if n == "explicit-workers" or n.startswith("workers-page-")],
                     *[n for n in opening if n.startswith("dispatch-show-")]):
            before = _decode(opening[name])
            if name == "run-show":
                args = ["orchestration", "run-show", "--id", run_id, "--json"]
            elif name == "task-list":
                args = ["orchestration", "task-list", "--run", run_id, "--json"]
            elif name.startswith("dispatch-show-"):
                args = ["orchestration", "dispatch-show", "--task", before["result"]["dispatch"]["task_id"], "--json"]
            else:
                args = ["orchestration", "worker-list", "--run", run_id, "--limit", "100", "--json"]
                if name != "explicit-workers":
                    index = int(name.rsplit("-", 1)[1])
                    previous = "explicit-workers" if index == 1 else f"workers-page-{index - 1}"
                    args += ["--cursor", _decode(opening[previous])["result"]["page"]["nextCursor"]]
            after = get("final-" + name, args)
            _check_receipt(name, after)
            _require(after["result"] == before["result"] and after["_meta"] == before["_meta"],
                     "native authority changed during retrieval")
            closing[name] = receipts["final-" + name]
        final_status = get("final-status", ["status", "--json"])
        closing["status"] = receipts["final-status"]
        _normalize(version, run_id, closing)
        initial = _decode(opening["status"])
        _require(final_status["_meta"] == initial["_meta"] and final_status["result"] == initial["result"],
                 "runtime changed during retrieval")
        result["acceptance"] = _apply_expectations(envelope, expectations)
        for item in envelope["items"]:
            item["evidence"].append({"native_sources": copy.deepcopy(result["sources"]),
                                     "scope": "read-only local inventory; archive content not retrieved"})
        from compact import encode, project
        raw = encode(envelope)
        ref = _store(directory / "normalized.json", raw)
        result["sources"]["normalized"] = ref
        result["projection"] = project(raw, ref["ref"])
        result["status"] = result["projection"]["status"]
        result["source_verified"] = result["status"] == "REVIEW"
    except AdapterError as exc:
        result["issues"] = [str(exc)]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, AttributeError):
        result["issues"] = ["native retrieval unavailable or unsupported; inspect retained source"]
    return result


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("collect", help="owned local read-only retrieval; explicit storage permission required")
    live.add_argument("--run", required=True)
    live.add_argument("--orca-executable", help="explicit absolute trusted Orca CLI path; no fallback")
    live.add_argument("--capture-root", required=True)
    live.add_argument("--capture-authorized", action="store_true", default=False)
    live.add_argument("--expectations", help="exact Task-keyed policy JSON; not worker observations")
    offline = commands.add_parser("fixture", help="offline structural check only; never authenticates supplied JSON")
    offline.add_argument("--run", required=True)
    offline.add_argument("--version", required=True)
    offline.add_argument("--directory", required=True)
    offline.add_argument("--expectations")
    args = parser.parse_args(argv)
    try:
        expectations = _decode(Path(args.expectations).read_bytes()) if args.expectations else None
        if args.command == "collect":
            result = collect(args.run, args.capture_root, capture_authorized=args.capture_authorized,
                             executable=args.orca_executable, expectations=expectations)
        else:
            directory = Path(args.directory).resolve(strict=True)
            records = {p.stem: p.read_bytes() for p in directory.glob("*.json") if p.name != "provenance.json"}
            result = inspect_fixture(args.version, args.run, records, expectations=expectations)
            if "envelope" in result:
                from compact import encode, project
                envelope = result.pop("envelope")
                result["projection"] = project(encode(envelope), f"offline-fixture:{directory}")
    except (OSError, ValueError, TypeError, RecursionError):
        result = {"schema": SCHEMA, "status": "STOP", "source_verified": False,
                  "issues": ["unable to read adapter input; no verification or acceptance"]}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return 0 if result["status"] == "REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
