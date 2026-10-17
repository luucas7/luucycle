"""Deterministic public fixtures. No repository, issue, network or session lookup."""

from copy import deepcopy


def envelope(kind, items, *, complete=True, expected_count=None, errors=None):
    return {"schema": "luucycle.return.v1", "kind": kind, "complete": complete,
            "expected_count": len(items) if expected_count is None else expected_count,
            "items": items, "errors": errors or []}


def record(number, *, status="PENDING"):
    suffix = f"SYNTH-{number:04d}"
    return {"id": f"record:{suffix}", "status": status, "decision": None,
            "ids": {"task": f"task:{suffix}", "run": "run:SYNTH-2026"},
            "evidence": [{"ref": f"fixture:source:{suffix}", "synthetic": True}],
            "changes": [], "blockers": [],
            "controls": {"phase": "Execution", "approval": {"plan": "plan:SYNTH-EXEC-01",
                         "evidence": "fixture:approval:EXEC-01"}, "routed_skill": "implement",
                         "primary_agent": f"roster:primary:{number:04d}",
                         "fallback_agent": f"roster:fallback:{number:04d}",
                         "cost_ceiling": "medium", "selection_warnings": []},
            "detail": {}}


def task_list():
    tasks = []
    components = ("catalogue", "calendar", "inventory", "routing", "editor", "search", "export", "history")
    checks = (
        "Keep the original object identifier when opening, editing, saving and reopening the synthetic record; compare the stored value with the initial fixture identifier.",
        "Exercise the empty collection and the single item collection with the same operation; the resulting receipt must account for every selected record exactly once.",
        "Inject a validation failure before persistence and confirm the displayed error identifies the rejected field and retains the user's pending value for correction.",
        "Compare the persisted revision with the revision returned by the save receipt; if they differ, stop dependent operations and retain the observed mismatch as evidence.",
        "Check that a cancelled operation produces no write receipt, no revision increment and no completion event; record the cancellation separately from a successful save.",
        "Repeat the operation with accented labels and Unicode identifiers; compare the exact strings after serialization and retrieval without shortening or normalizing them.",
        "Verify that each accepted action has one independently observed result and that an unsuccessful action does not inherit the preceding successful action's evidence.",
        "Supply an outdated revision during the final save and confirm that conflict handling preserves the current stored object while making the rejected update inspectable.",
        "Observe the pending state while a synthetic response is delayed; a timeout must remain a checkpoint until a definite result or explicit failure is available.",
        "Open two distinct fixture records with similar labels and verify that every follow-up operation uses the full identifier of its intended record and its own revision.",
        "Inspect the final interface after the merged change and record the design review verdict against that exact revision, including any unresolved interaction defect.",
        "Capture the command, actual result, changed fixture paths and relevant revision in the task report so a reviewer can reproduce the observation without a private service.",
    )
    for number in range(1, 97):
        component = components[(number - 1) // 12]
        item = record(number)
        item["detail"] = {
            "title": f"Synthetic {component} operation {number}",
            "description": (
                f"Implement operation {number} in the fictional {component} component. "
                "The fixture represents a local application with revisioned records and explicit save receipts. "
                "A user opens a record, changes a value, requests persistence and then inspects the saved result. "
                "The operation must retain enough diagnostic information to distinguish cancellation, validation "
                "failure, conflicting revisions, delayed responses and an accepted write. All sources and commands "
                "in this scenario are synthetic; none names a real tracker issue or an installed consumer project."
            ),
            "acceptance_checks": list(checks),
            "source_context": [
                f"Fixture boundary {boundary} for operation {number}: use the {component} record supplied by the "
                "scenario, retain its independent revision and attach observations to this exact task. The source "
                "includes a saved value, a pending edit, an expected validation result and a separate conflict "
                "response; these examples explain the operation while decision fields remain in the receipt."
                for boundary in ("read", "validate", "persist", "reopen")
            ],
        }
        tasks.append(item)
    return envelope("tasks", tasks)


def worker_returns():
    workers = []
    for number, status in enumerate(("DONE", "FAILED", "BLOCKED", "RUNNING"), 1):
        item = record(number, status=status)
        item["id"] = f"report:SYNTH-{number:04d}"
        item["ids"].update({"dispatch": f"dispatch:SYNTH-{number:04d}-attempt-A",
                            "worker": f"worker:SYNTH-{number:04d}",
                            "terminal": f"terminal:SYNTH-{number:04d}",
                            "worktree": f"worktree:SYNTH-{number:04d}-full-id",
                            "message": f"message:SYNTH-{number:04d}",
                            "delivery": "delivery:SYNTH-batch-01"})
        item["controls"].update({"loaded_skill": "implement", "primary_cli": "synthetic-cli-a",
                                "fallback_cli": "synthetic-cli-b", "fallback_used": False,
                                "expected_dispatch": item["ids"]["dispatch"],
                                "active_dispatch": item["ids"]["dispatch"],
                                "ack": {"processed": False, "acknowledged": False},
                                "lifecycle": {"settlement": "pending-verification", "terminal_disposition": "pending"},
                                "ui_gate": {"required": True, "verdict": "PENDING", "revision": "revision:SYNTH-42", "cycle": 0}})
        item["evidence"].append({"command": f"synthetic-check --task task:SYNTH-{number:04d}",
                                 "exit": 1 if status == "FAILED" else 0,
                                 "observed": status, "synthetic": True})
        item["changes"] = [{"path": f"fictional/component-{number}.txt", "revision": f"revision:SYNTH-{number:04d}",
                             "partial": status != "DONE"}]
        if status in {"FAILED", "BLOCKED"}:
            item["decision"] = {"action": "verify_before_approved_fallback", "task": item["ids"]["task"]}
            item["blockers"] = [{"capability": "synthetic-readback", "observed_failure": "revision mismatch échec",
                                  "unresolved": True}]
            item["controls"]["external_write"] = {"target": "fixture:external:02", "authorized_revision": "rev:expected",
                                                    "receipt": "receipt:SYNTH-02", "readback_revision": "rev:other", "verified": False}
        item["detail"] = {"report": task_list()["items"][number - 1]["detail"],
                          "log": [f"Synthetic observation {index}: {status} on {item['ids']['task']}" for index in range(15)]}
        workers.append(item)
    return envelope("workers", workers, errors=[{"code": "SYNTH_WORKER_FAILURE", "resolved": False}])


def partial_orca_state():
    items = []
    for number, liveness in enumerate(("live", "exited", "unverifiable"), 1):
        item = record(number, status="UNKNOWN" if liveness == "unverifiable" else "RUNNING")
        item["id"] = f"observation:SYNTH-{number:04d}"
        item["ids"].update({"dispatch": f"dispatch:SYNTH-{number:04d}-attempt-A",
                            "terminal": f"terminal:SYNTH-{number:04d}",
                            "worktree": f"worktree:SYNTH-{number:04d}-full-id"})
        item["controls"].update({"scope": {"runId": "run:SYNTH-2026", "includeRemote": True},
                                "page": {"hasMore": True, "nextCursor": "cursor:SYNTH-page-02"},
                                "projection": {"liveness": {"verdict": liveness, "reason": f"fixture:{liveness}"},
                                               "attention": {"requiresAction": liveness != "live", "categories": ["synthetic"]},
                                               "nextAction": {"argv": []}},
                                "authority": {"executionHost": "host:SYNTH-REMOTE", "localFallbackAllowed": False},
                                "failedStage": "synthetic-observation" if liveness == "unverifiable" else None,
                                "residualResources": {"terminal": item["ids"]["terminal"]}})
        item["detail"] = {"transcript": [f"Synthetic {liveness} checkpoint {index}: awaiting a verified observation." for index in range(20)]}
        items.append(item)
    return envelope("orca", items, complete=False, expected_count=4,
                    errors=[{"page": "cursor:SYNTH-page-02", "error": "synthetic transport failure"}])


def session_relay():
    item = deepcopy(worker_returns()["items"][1])
    item["id"] = "checkpoint:SYNTH-SESSION-02"
    item["controls"].update({
        "approvals": [{"phase": "Audit", "plan": "plan:SYNTH-AUDIT-01", "evidence": "fixture:approval:AUDIT-01"},
                      {"phase": "Execution", "plan": "plan:SYNTH-EXEC-01", "evidence": "fixture:approval:EXEC-01"}],
        "verified_state": {"observed_at": "2026-01-01T12:00:00Z", "revision": "revision:SYNTH-42",
                           "source": "fixture:state:01", "limit": "partial remote observation", "initial_base_branch": "synthetic-base"},
        "incidents": [{"failure": "SYNTH_WORKER_FAILURE", "partial_changes": item["changes"],
                       "fallback_used": False, "pending_delivery": item["ids"]["delivery"]}]})
    return envelope("relay", [item])


def scenario():
    return {"tasks": task_list(), "workers": worker_returns(),
            "orca": partial_orca_state(), "relay": session_relay()}
