"""Shared prompt, receipt, and guarded Dispatch-message contract for luucycle.

This module is a local policy wrapper. It does not intercept other Orca clients,
and its authority check followed by a send is not an atomic runtime operation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class ContractError(ValueError):
    """An explicit worker contract or Orca authority check failed closed."""


_ID_PATTERNS = {
    "run_id": re.compile(r"run_[0-9a-f]{12}"),
    "task_id": re.compile(r"task_[0-9a-f]{12}"),
    "dispatch_id": re.compile(r"ctx_[0-9a-f]{12}"),
}
_PERMISSION_KEYS = {"artifact_write", "report_write"}
_TARGET_KEYS = {"run_id", "task_id", "dispatch_id", "terminal_id"}
_SETTLED_TASK = {"done", "completed", "settled", "blocked", "failed", "sealed", "released"}
_SETTLED_DISPATCH = {"done", "completed", "settled", "blocked", "failed", "sealed", "released"}
_SETTLED_TERMINAL = {"done", "completed", "settled", "blocked", "failed", "sealed", "released", "terminated", "exited"}


def _adapter_validator():
    """Load the existing authoritative task-evidence validator without copying it."""
    path = Path(__file__).with_name("orca_adapter.py")
    spec = importlib.util.spec_from_file_location("luucycle_orca_adapter_for_worker_contract", path)
    if spec is None or spec.loader is None:
        raise ContractError("cannot load orca_adapter task evidence validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_task_evidence


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _exact_keys(value: Any, keys: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, f"{label} must contain exactly {sorted(keys)}")


def _nonempty_string(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label} must be a non-empty string")
    return value


def _check_id(value: Any, field: str) -> str:
    value = _nonempty_string(value, field)
    pattern = _ID_PATTERNS.get(field)
    if pattern:
        _require(pattern.fullmatch(value) is not None, f"invalid exact {field}")
    return value


def _skill_snapshot(skill: Any) -> dict[str, str]:
    _exact_keys(skill, {"identity", "path", "sha256"}, "skill contract")
    identity = _nonempty_string(skill["identity"], "skill identity")
    raw_path = _nonempty_string(skill["path"], "skill path")
    path = Path(raw_path)
    _require(path.is_absolute(), "skill path must be absolute")
    digest = _nonempty_string(skill["sha256"], "skill sha256")
    _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "skill sha256 must be lowercase hex")
    _require(path.is_file(), "routed skill source is unavailable")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(actual == digest, "routed skill digest changed")
    return {"identity": identity, "path": str(path), "sha256": digest}


def _plan_snapshot(plan: Any, *, allow_native_ids: bool = False) -> dict[str, Any]:
    """Validate a fully approved, task-specific dispatch plan and freeze it."""
    fields = {"approval", "target", "task", "skill", "permissions", "targets", "model", "evidence"}
    _exact_keys(plan, fields, "dispatch plan")
    _require(plan["approval"] is True, "explicit approval of this exact dispatch plan is required")
    _exact_keys(plan["target"], _TARGET_KEYS, "dispatch target")
    target = {"run_id": _check_id(plan["target"]["run_id"], "run_id")}
    for key in ("task_id", "dispatch_id", "terminal_id"):
        value = plan["target"][key]
        if allow_native_ids and value is None:
            target[key] = None
        elif key == "terminal_id":
            target[key] = _nonempty_string(value, "terminal_id")
        else:
            target[key] = _check_id(value, key)
    task = _nonempty_string(plan["task"], "task")
    _exact_keys(plan["permissions"], _PERMISSION_KEYS, "task rights")
    _require(all(type(v) is bool for v in plan["permissions"].values()),
             "explicit artifact/report permissions are required")
    targets = plan["targets"]
    _require(isinstance(targets, list) and targets and all(isinstance(x, str) and x for x in targets),
             "at least one exact target path or scope is required")
    _require(len(targets) == len(set(targets)), "duplicate target scope")
    _exact_keys(plan["model"], {"agent_id", "cli", "alias", "model"}, "model selection")
    model = {key: _nonempty_string(value, f"model {key}") for key, value in plan["model"].items()}
    _exact_keys(plan["evidence"], {"required", "completion_criterion", "storage", "report_path"}, "evidence policy")
    required = plan["evidence"]["required"]
    _require(isinstance(required, list) and required and all(isinstance(x, str) and x for x in required),
             "required evidence list must be explicit and nonempty")
    criterion = _nonempty_string(plan["evidence"]["completion_criterion"], "completion criterion")
    storage = _nonempty_string(plan["evidence"]["storage"], "evidence storage")
    report_path = plan["evidence"]["report_path"]
    if storage == "artifact":
        _require(plan["permissions"]["artifact_write"] and plan["permissions"]["report_write"],
                 "artifact evidence requires artifact and report write rights")
        _require(isinstance(report_path, str) and Path(report_path).is_absolute(),
                 "artifact evidence requires an exact absolute report path")
        _require(report_path in targets, "authorized report path must be an explicit task target")
    elif storage == "existing_record":
        _require(report_path is None, "existing-record evidence has no new report path")
    else:
        raise ContractError("unsupported evidence storage policy")
    skill = _skill_snapshot(plan["skill"])
    # Encode/decode to reject non-JSON values and detach from caller mutation.
    snapshot = {"approval": True, "target": target, "task": task, "skill": skill,
                "permissions": dict(plan["permissions"]), "targets": list(targets), "model": model,
                "evidence": {"required": list(required), "completion_criterion": criterion,
                             "storage": storage, "report_path": report_path}}
    return json.loads(json.dumps(snapshot, ensure_ascii=False, allow_nan=False))


def build_dispatch_prompt(plan: dict[str, Any]) -> str:
    """Build a deterministic prompt from an explicitly approved dispatch plan."""
    frozen = _plan_snapshot(plan, allow_native_ids=True)
    target = frozen["target"]
    evidence = frozen["evidence"]
    native_ids = any(target[key] is None for key in ("task_id", "dispatch_id", "terminal_id"))
    receipt_task_id = target["task_id"] or "<exact Task ID from Orca preamble>"
    receipt_dispatch_id = target["dispatch_id"] or "<exact Dispatch ID from Orca preamble>"
    skill_attestation = dict(frozen["skill"])
    if evidence["storage"] == "existing_record":
        storage_attestation = {"kind": "existing_record", "ref": f"orca:task:{receipt_task_id}:result"}
        writes = {"artifact": False, "report": False}
    else:
        storage_attestation = {"kind": "artifact", "path": evidence["report_path"],
                              "sha256": "<lowercase SHA-256 of exact report file>"}
        writes = {"artifact": True, "report": True}
    payload_template = {
        "taskId": receipt_task_id, "dispatchId": receipt_dispatch_id,
        "outcome": "succeeded", "filesModified": [],
        "task_evidence": {
            "schema": "luucycle.task-evidence.v1", "task_id": receipt_task_id,
            "dispatch_id": receipt_dispatch_id, "routed_skill": skill_attestation,
            "loaded_skill": skill_attestation, "writes": writes, "storage": storage_attestation,
        },
    }
    lines = [
        "# luucycle one-shot worker contract",
        "",
        "## Exact lifecycle identity",
        f"- Run: `{target['run_id']}`",
        f"- Task: `{target['task_id'] or 'assigned by Orca; use the exact live preamble'}`",
        f"- Dispatch: `{target['dispatch_id'] or 'assigned by Orca; use the exact live preamble'}`",
        f"- Terminal: `{target['terminal_id'] or 'assigned by Orca; use the exact live preamble'}`",
        "",
        "## Assignment",
        frozen["task"],
        "",
        "## Routed skill",
        f"- Identity: `{frozen['skill']['identity']}`",
        f"- Source: `{frozen['skill']['path']}`",
        f"- Required SHA-256: `{frozen['skill']['sha256']}`",
        "- Load this exact skill before acting. Report the same identity, path, and digest as both routed and loaded skill.",
        "",
        "## Rights and scope",
        f"- Rights: `{json.dumps(frozen['permissions'], sort_keys=True, separators=(',', ':'))}`",
        *[f"- Target: `{item}`" for item in frozen["targets"]],
        "- Do not exceed these rights or targets.",
        "",
        "## Launch selection",
        f"- Agent: `{frozen['model']['agent_id']}`",
        f"- CLI: `{frozen['model']['cli']}`",
        f"- Orca alias: `{frozen['model']['alias']}`",
        f"- Requested model: `{frozen['model']['model']}`",
        "- Preserve this selection; report any mismatch as BLOCKED.",
        "",
        "## Required evidence and completion",
        *[f"- Evidence: {item}" for item in evidence["required"]],
        f"- Completion criterion: {evidence['completion_criterion']}",
        f"- Evidence storage: `{evidence['storage']}`" +
        (f" at `{evidence['report_path']}`" if evidence["report_path"] else ""),
        "- Put the exact JSON `luucycle.task-evidence.v1` attestation under `task_evidence` in the native worker_done `--payload` object. Since raw payload mode carries lifecycle fields itself, include exact camelCase `taskId`, `dispatchId`, and `outcome` (`succeeded` or `failed`) in that JSON; do not also pass their typed flags. Keep the guide-required three-sentence summary in `--body`.",
        "- `worker_done` is a lifecycle settlement signal, not evidence acceptance. Payload shape: `{'taskId': '<exact task>', 'dispatchId': '<exact dispatch>', 'outcome': 'succeeded|failed', 'task_evidence': <task-evidence-json>}`.",
        "- Concrete payload template (replace assigned IDs and the outcome with actual values; preserve the complete nested field structure):",
        "```json",
        json.dumps(payload_template, ensure_ascii=False, indent=2),
        "```",
        "- A receipt is terminal: after sending it, stop work. Any follow-up requires a new Dispatch and terminal.",
        "- Populate payload.filesModified with every exact changed path relative to the target checkout; use [] only when this task changed no files. The coordinator also compares the independent Git baseline.",
        "- Invoke the exact executable from the live preamble with an argument list (no shell interpolation): `subprocess.run([ORCA, 'orchestration', 'send', '--from', WORKER_HANDLE, '--type', 'worker_done', '--subject', SUBJECT, '--body', THREE_SENTENCES, '--payload', json.dumps(payload), '--json'], check=True)`. `payload` is the complete object shown above.",
    ]
    if native_ids:
        lines.extend(["", "Orca assigns any null Task, Dispatch, or terminal ID during launch. Treat the live Orca preamble as the sole authority for those exact IDs; do not invent or infer them."])
    return "\n".join(lines) + "\n"


def bind_launch_ids(plan: dict[str, Any], launch: dict[str, Any]) -> dict[str, Any]:
    """Bind native IDs returned by launch before validating receipts or messages.

    The caller must derive this compact record from the actual launch receipt,
    not a title, prefilled plan, or guessed ID. This function checks its shape
    and identity consistency but cannot authenticate arbitrary caller bytes.
    """
    frozen = _plan_snapshot(plan, allow_native_ids=True)
    _exact_keys(launch, {"complete", "source_verified", "run_id", "task_id", "dispatch_id", "terminal_id"}, "native launch identity")
    _require(launch["complete"] is True and launch["source_verified"] is True,
             "complete native launch identity is required")
    _require(launch["run_id"] == frozen["target"]["run_id"], "launch belongs to a different Run")
    for key in ("task_id", "dispatch_id", "terminal_id"):
        planned = frozen["target"][key]
        if planned is not None:
            _require(launch[key] == planned, f"launch {key} differs from approved target")
    bound = json.loads(json.dumps(frozen, ensure_ascii=False, allow_nan=False))
    bound["target"] = {
        "run_id": _check_id(launch["run_id"], "run_id"),
        "task_id": _check_id(launch["task_id"], "task_id"),
        "dispatch_id": _check_id(launch["dispatch_id"], "dispatch_id"),
        "terminal_id": _nonempty_string(launch["terminal_id"], "terminal_id"),
    }
    return _plan_snapshot(bound)


def validate_return(expectation: dict[str, Any], receipt: dict[str, Any], *,
                    task_id: str, dispatch_id: str, source_complete: bool) -> dict[str, Any]:
    """Validate a common receipt while keeping settlement separate from acceptance."""
    result: dict[str, Any] = {
        "status": "STOP", "worker_done": False, "acceptance": "INCOMPLETE",
        "issues": [], "limits": ["worker_done proves settlement only", "task evidence is worker assertion, not truth or skill-loading proof"],
    }
    try:
        if not isinstance(receipt, dict) or receipt.get("schema") != "luucycle.worker-receipt.v1":
            receipt = normalize_worker_done_message(receipt)
        _exact_keys(receipt, {"schema", "task_id", "dispatch_id", "worker_status", "worker_done", "task_evidence"}, "worker receipt")
        _require(receipt["schema"] == "luucycle.worker-receipt.v1", "unsupported worker receipt schema")
        _require(receipt["task_id"] == task_id and receipt["dispatch_id"] == dispatch_id,
                 "foreign task/dispatch receipt")
        _require(receipt["worker_status"] in {"DONE", "BLOCKED", "FAILED"}, "receipt is not terminal")
        _require(receipt["worker_done"] is True, "terminal worker_done receipt required")
        check = _adapter_validator()(expectation, receipt["task_evidence"], task_id=task_id,
                                     dispatch_id=dispatch_id, source_complete=source_complete)
        result["task_evidence"] = check
        result["worker_done"] = True
        result["worker_status"] = receipt["worker_status"]
        result["acceptance"] = "EVIDENCE_REVIEW_NOT_ACCEPTED" if check["status"] == "EVIDENCE_REVIEW" else "INCOMPLETE"
        if check["status"] == "EVIDENCE_REVIEW":
            result["status"] = "RECEIVED_TERMINAL"
        else:
            result["issues"] = list(check["issues"])
            result["status"] = "RECEIVED_TERMINAL_EVIDENCE_INCOMPLETE"
    except (ContractError, TypeError, KeyError, AttributeError) as exc:
        result["issues"] = [str(exc) if isinstance(exc, ContractError) else "malformed or incomplete worker receipt"]
    return result


def normalize_worker_done_message(message: dict[str, Any]) -> dict[str, Any]:
    """Normalize the versioned adapter's message/payload projection.

    Typed Orca fields are camelCase in the native parsed payload. The adapter
    may pass its projected `message` object directly or under a `message` key.
    """
    if isinstance(message, dict) and isinstance(message.get("projection"), dict):
        message = message["projection"]
    if isinstance(message, dict) and isinstance(message.get("native_message"), dict):
        native = message["native_message"]
        payload = message.get("parsed_payload")
    else:
        native = message
        payload = message.get("parsed_payload") if isinstance(message, dict) else None
    if isinstance(native, dict) and isinstance(native.get("message"), dict):
        native = native["message"]
    elif isinstance(message, dict) and isinstance(message.get("message"), dict):
        message = message["message"]
        native = message
        payload = message.get("parsed_payload")
    _require(isinstance(native, dict), "native worker_done message required")
    _require(native.get("type") == "worker_done", "message is not a terminal worker_done receipt")
    raw_payload = native.get("payload")
    if payload is None:
        payload = raw_payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                raise ContractError("worker_done payload is not valid JSON") from None
    elif raw_payload is not None:
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except (ValueError, TypeError):
                raise ContractError("native worker_done payload is not valid JSON") from None
        _require(raw_payload == payload, "native and parsed worker_done payloads differ")
    _require(isinstance(payload, dict), "worker_done parsed payload required")
    task_id = _check_id(payload.get("taskId"), "task_id")
    dispatch_id = _check_id(payload.get("dispatchId"), "dispatch_id")
    outcome = payload.get("outcome")
    _require(outcome in {"succeeded", "failed"}, "explicit worker_done outcome required")
    evidence = payload.get("task_evidence")
    _require(isinstance(evidence, dict), "worker_done task_evidence payload is required")
    return {"schema": "luucycle.worker-receipt.v1", "task_id": task_id,
            "dispatch_id": dispatch_id, "worker_status": "DONE" if outcome == "succeeded" else "FAILED",
            "worker_done": True, "task_evidence": evidence}


def validate_native_worker_done(expectation: dict[str, Any], message: dict[str, Any], *,
                                expected_task_id: str, expected_dispatch_id: str,
                                source_complete: bool) -> dict[str, Any]:
    """Parse and validate an adapter-projected native worker_done message."""
    try:
        normalized = normalize_worker_done_message(message)
        _require(normalized["task_id"] == expected_task_id and
                 normalized["dispatch_id"] == expected_dispatch_id,
                 "worker_done payload has foreign Task or Dispatch IDs")
        if isinstance(message, dict) and isinstance(message.get("ids"), dict):
            _require(message["ids"].get("task") == expected_task_id and
                     message["ids"].get("dispatch") == expected_dispatch_id,
                     "adapter message authority differs from worker_done payload")
    except (ContractError, TypeError, AttributeError) as exc:
        return {"status": "STOP", "worker_done": False, "acceptance": "INCOMPLETE",
                "issues": [str(exc) if isinstance(exc, ContractError) else "malformed native worker_done message"]}
    return validate_return(expectation, normalized, task_id=expected_task_id,
                           dispatch_id=expected_dispatch_id, source_complete=source_complete)


def preflight_dispatch_message(plan: dict[str, Any], authority: dict[str, Any], message: str, *,
                               now: datetime | None = None, max_age_seconds: int = 5) -> dict[str, Any]:
    """Pure check for a fresh, exact, active native Dispatch authority snapshot."""
    frozen = _plan_snapshot(plan)
    _require(isinstance(message, str) and bool(message.strip()), "message body must be nonempty")
    _require(type(max_age_seconds) is int and max_age_seconds >= 0, "max_age_seconds must be a nonnegative integer")
    _exact_keys(authority, {"complete", "source_verified", "observed_at", "run_id", "task_id", "dispatch_id",
                            "terminal_id", "task_status", "dispatch_status", "terminal_state", "sealed"},
                "fresh Orca authority")
    _require(authority["complete"] is True and authority["source_verified"] is True,
             "fresh complete Orca authority is required")
    _require(authority["sealed"] is False, "settled or sealed worker rejects follow-up input")
    expected = frozen["target"]
    for key in _TARGET_KEYS:
        _require(authority[key] == expected[key], f"stale or foreign {key} authority")
    observed_text = _nonempty_string(authority["observed_at"], "authority observation time")
    try:
        observed = datetime.fromisoformat(observed_text.replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if observed.tzinfo is None:
            raise ValueError("timezone required")
        age = (current.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    except (ValueError, TypeError):
        raise ContractError("invalid authority observation time") from None
    _require(0 <= age <= max_age_seconds, "stale Orca authority snapshot")
    statuses = ((authority["task_status"], "dispatched", _SETTLED_TASK, "task"),
                (authority["dispatch_status"], "dispatched", _SETTLED_DISPATCH, "dispatch"),
                (authority["terminal_state"], "active", _SETTLED_TERMINAL, "terminal"))
    for status, expected_status, settled, label in statuses:
        _require(isinstance(status, str) and status.lower() not in settled,
                 f"settled/sealed/released {label} rejects follow-up input")
        _require(status.lower() == expected_status,
                 f"unsupported active {label} status; expected {expected_status}")
    return {"status": "OK", "recipient": f"dispatch:{expected['dispatch_id']}",
            "message": message, "identity": dict(expected), "observed_at": observed_text,
            "native_scope": "exact Dispatch address", "atomic": False}


def controlled_dispatch_send(plan: dict[str, Any], message: str, *,
                             read_fresh_authority: Callable[[], dict[str, Any]],
                             send: Callable[[dict[str, Any]], Any],
                             now: datetime | None = None, max_age_seconds: int = 5) -> dict[str, Any]:
    """Read authority immediately before sending to the exact Dispatch address.

    The callbacks are injected so callers can use only the installed Orca guide's
    supported read/send operations. This cannot lock Orca between the read and send.
    """
    authority = read_fresh_authority()
    envelope = preflight_dispatch_message(plan, authority, message, now=now, max_age_seconds=max_age_seconds)
    receipt = send(envelope)
    return {"status": "SEND_ATTEMPTED", "preflight": envelope, "send_receipt": receipt,
            "acceptance": "NOT_EVALUATED", "atomic": False,
            "limits": "check/send is not atomic; accepted enqueue is not worker acknowledgment or acceptance"}


def send_orca_message(plan: dict[str, Any], message: str, *, executable: str,
                      capture_root: str, capture_authorized: bool = False,
                      send_authorized: bool = False) -> dict[str, Any]:
    """Own the fresh native read and exact Dispatch send, without a global lock.

    The caller chooses a trusted local Orca executable and authorizes capture
    storage and this message. No caller-supplied verified snapshot is used here.
    An ambiguous send is retained and never replayed automatically.
    """
    result = {"status": "STOP", "sent": False, "atomic": False,
              "acceptance": "NOT_EVALUATED", "issues": []}
    try:
        _require(capture_authorized is True and send_authorized is True,
                 "capture and exact message send authorization required")
        frozen = _plan_snapshot(plan)
        sibling = str(Path(__file__).resolve().parent)
        if sibling not in sys.path:
            sys.path.insert(0, sibling)
        import orca_inbox
        target = frozen["target"]
        observation = orca_inbox.read_dispatch_authority(
            target["run_id"], target["task_id"], target["dispatch_id"], capture_root,
            executable=executable, capture_authorized=True)
        result["authority_capture"] = observation.get("capture_directory")
        result["authority_issues"] = observation.get("issues", [])
        _require(observation.get("status") == "REVIEW" and observation.get("source_verified") is True,
                 "fresh native authority retrieval incomplete; message not sent")
        ids = observation["ids"]
        authority = {"complete": observation["complete"], "source_verified": True,
                     "observed_at": observation["observed_at"],
                     "run_id": ids["run"], "task_id": ids["task"],
                     "dispatch_id": ids["dispatch"], "terminal_id": ids["assignee"],
                     **{k: observation[k] for k in ("task_status", "dispatch_status", "terminal_state", "sealed")}}
        preflight = preflight_dispatch_message(frozen, authority, message)
        result["preflight"] = preflight
        directory = Path(tempfile.mkdtemp(prefix="orca-send-", dir=capture_root))
        result["send_capture"] = str(directory)
        # Mark possible delivery before calling the mutation: transport failure
        # cannot be interpreted as proof that no input was enqueued.
        result["sent"] = None
        raw, ref = orca_inbox.adapter._capture(
            [executable, "orchestration", "send", "--to", preflight["recipient"],
             "--subject", "luucycle task guidance", "--type", "status", "--body", message,
             "--task-id", target["task_id"], "--dispatch-id", target["dispatch_id"], "--json"],
            directory, "send")
        native = orca_inbox.adapter._decode(raw)
        _require(native.get("ok") is True and not native.get("error") and isinstance(native.get("result"), dict),
                 "native send outcome unresolved; inspect capture and do not resend")
        record = native["result"].get("message")
        _require(isinstance(record, dict) and
                 re.fullmatch(r"msg_[0-9a-f]{12}", record.get("id", "")) is not None and
                 record.get("run_id") == target["run_id"] and
                 record.get("to_handle") == preflight["recipient"] and
                 record.get("type") == "status" and record.get("body") == message and
                 json.loads(record.get("payload", "null")) == {
                     "taskId": target["task_id"], "dispatchId": target["dispatch_id"]} and
                 native.get("_meta", {}).get("runtimeId") == observation.get("runtime_id"),
                 "send receipt does not match exact fresh authority/message; inspect before retry")
        result.update(status="ENQUEUED", sent=True, native_receipt=native, source=ref,
                      limits="durable enqueue only; read/send is non-atomic and other send APIs are not intercepted")
    except (ContractError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result["issues"] = [str(exc) if isinstance(exc, (ContractError, ValueError)) else
                            "native send unavailable; preserve capture and inspect before retry"]
    return result


def _read_json_object(path: str, label: str) -> dict[str, Any]:
    source = Path(path)
    _require(source.is_file(), f"{label} must be a regular JSON file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ContractError(f"{label} is unreadable or invalid JSON") from None
    _require(isinstance(value, dict), f"{label} JSON must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    """Offer snapshot diagnostics and an explicitly authorized native send path."""
    parser = argparse.ArgumentParser(description="luucycle Dispatch contract and controlled messaging")
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight", help="check plan and fresh Orca authority before a separate send")
    preflight.add_argument("--plan", required=True, help="approved dispatch plan JSON file")
    preflight.add_argument("--authority", required=True, help="fresh complete authority JSON from supported Orca reads")
    preflight.add_argument("--message", required=True, help="message body to preflight")
    preflight.add_argument("--max-age-seconds", type=int, default=5)
    live = sub.add_parser("send", help="retrieve fresh native authority then send one exact message")
    live.add_argument("--plan", required=True)
    live.add_argument("--message", required=True)
    live.add_argument("--orca-executable", required=True)
    live.add_argument("--capture-root", required=True)
    live.add_argument("--capture-authorized", action="store_true")
    live.add_argument("--send-authorized", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = _read_json_object(args.plan, "plan")
        if args.command == "send":
            result = send_orca_message(plan, args.message, executable=args.orca_executable,
                                       capture_root=args.capture_root,
                                       capture_authorized=args.capture_authorized,
                                       send_authorized=args.send_authorized)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] == "ENQUEUED" else 2
        authority = _read_json_object(args.authority, "authority")
        result = preflight_dispatch_message(plan, authority, args.message,
                                            max_age_seconds=args.max_age_seconds)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "STOP", "issues": [str(exc)], "sent": False},
                         ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
