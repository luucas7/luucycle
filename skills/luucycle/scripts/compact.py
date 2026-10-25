#!/usr/bin/env python3
"""Project a versioned luucycle return before it reaches the coordinator.

Read-only, standard library only. This is not an Orca wire-format adapter or an
authorization engine. See COMPACT.md for producer and consumer obligations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any


SCHEMA = "luucycle.return.v1"
ENVELOPE_KEYS = {"schema", "kind", "complete", "expected_count", "items", "errors"}
ITEM_KEYS = {"id", "status", "decision", "ids", "evidence", "changes", "blockers", "controls", "detail"}
STATUSES = {"PENDING", "RUNNING", "DONE", "BLOCKED", "FAILED", "UNKNOWN", "PAUSED", "SEALED"}
STOP_STATUSES = {"BLOCKED", "FAILED", "UNKNOWN", "PAUSED"}
TERMINAL_STATUSES = {"DONE", "BLOCKED", "FAILED", "SEALED"}
KINDS = {"tasks", "workers", "orca", "relay"}


class ContractError(ValueError):
    pass


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ContractError("non-finite JSON number")


def finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ContractError("non-finite JSON number")
    if Decimal(value) != Decimal(str(result)):
        raise ContractError("JSON number would lose precision; inspect the source")
    return result


def decode(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                             parse_constant=reject_constant, parse_float=finite_float)
    except ContractError:
        raise
    except (UnicodeError, ValueError) as exc:
        raise ContractError("invalid UTF-8 JSON; inspect the source") from exc
    if not isinstance(payload, dict) or set(payload) != ENVELOPE_KEYS:
        raise ContractError("envelope keys do not match luucycle.return.v1")
    if payload["schema"] != SCHEMA or not isinstance(payload["kind"], str) or payload["kind"] not in KINDS:
        raise ContractError("unsupported schema or kind")
    if type(payload["complete"]) is not bool:
        raise ContractError("complete must be an explicit boolean")
    if type(payload["expected_count"]) is not int or payload["expected_count"] < 0:
        raise ContractError("expected_count must be a nonnegative integer")
    if not isinstance(payload["items"], list) or not isinstance(payload["errors"], list):
        raise ContractError("items and errors must be arrays")
    seen = set()
    for index, item in enumerate(payload["items"]):
        label = f"items[{index}]"
        if not isinstance(item, dict) or set(item) != ITEM_KEYS:
            raise ContractError(f"{label}: missing or unknown fields; inspect this item")
        if not isinstance(item["id"], str) or not item["id"].strip():
            raise ContractError(f"{label}: missing exact ID")
        if item["id"] in seen:
            raise ContractError(f"{label}: duplicate ID; lookup is ambiguous")
        seen.add(item["id"])
        if not isinstance(item["status"], str) or item["status"] not in STATUSES:
            raise ContractError(f"{label}: unknown status")
        if item["decision"] is not None and not isinstance(item["decision"], dict):
            raise ContractError(f"{label}: decision must be an object or null")
        if not isinstance(item["ids"], dict) or not item["ids"] or any(
            not isinstance(value, str) or not value.strip() for value in item["ids"].values()
        ):
            raise ContractError(f"{label}: ids must contain exact, namespaced string IDs")
        for key in ("evidence", "changes", "blockers"):
            if not isinstance(item[key], list):
                raise ContractError(f"{label}: {key} must be an array")
        if not isinstance(item["controls"], dict) or not isinstance(item["detail"], dict):
            raise ContractError(f"{label}: controls and detail must be objects")
        if "sealed" in item["controls"] and type(item["controls"]["sealed"]) is not bool:
            raise ContractError(f"{label}: sealed must be an explicit boolean")
        if payload["kind"] == "relay" and not {"approvals", "verified_state", "incidents"} <= item["controls"].keys():
            raise ContractError(f"{label}: relay lacks approvals, verified_state or incidents")
    if payload["kind"] == "relay" and (payload["expected_count"] != 1 or len(payload["items"]) != 1):
        raise ContractError("relay must contain exactly one checkpoint")
    try:
        encode(payload)
    except (UnicodeError, ValueError) as exc:
        raise ContractError("JSON value cannot be returned losslessly; inspect the source") from exc
    return payload


def source_ref(raw: bytes, source: str) -> dict[str, Any]:
    return {"ref": source, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def assessment_issues(payload: dict[str, Any]) -> list[Any]:
    issues = []
    if not payload["complete"]:
        issues.append("incomplete_result")
    if payload["expected_count"] != len(payload["items"]):
        issues.append("count_mismatch")
    if payload["errors"]:
        issues.append("unresolved_errors")
    for item in payload["items"]:
        if item["status"] in STOP_STATUSES or item["blockers"]:
            issues.append({"id": item["id"], "reason": "verify_item"})
    return issues


def project(raw: bytes, source: str) -> dict[str, Any]:
    artifact = source_ref(raw, source)
    try:
        payload = decode(raw)
    except (ContractError, TypeError, RecursionError) as exc:
        # Never echo the raw document or a parser excerpt into the model context.
        return {"schema": SCHEMA, "status": "STOP", "source": artifact,
                "issues": [str(exc)], "next": "verify_source"}
    items = [{key: value for key, value in item.items() if key != "detail"}
             for item in payload["items"]]
    issues = assessment_issues(payload)
    return {"schema": SCHEMA, "kind": payload["kind"],
            "status": "STOP" if issues else "REVIEW", "source": artifact,
            "complete": payload["complete"], "expected_count": payload["expected_count"],
            "actual_count": len(items), "counts": dict(sorted(Counter(item["status"] for item in items).items())),
            "errors": payload["errors"], "issues": issues, "items": items,
            "next": "verify_source_or_item" if issues else "review_controls"}


def check_input(
    raw: bytes | dict[str, Any],
    source: str = "<memory>",
    worker_id: str = "",
    sha256: str | None = None,
) -> dict[str, Any]:
    if isinstance(raw, dict):
        raw_bytes = encode(raw)
        artifact_source = source if source != "<memory>" else "memory:payload"
    else:
        raw_bytes = raw
        artifact_source = source
    artifact = source_ref(raw_bytes, artifact_source)
    try:
        if sha256 and hashlib.sha256(raw_bytes).hexdigest() != sha256:
            raise ContractError("source changed; re-project and re-verify before deciding")
        payload = decode(raw_bytes)
        if not payload["complete"]:
            raise ContractError("source collection is incomplete; re-project and verify before input")
        if payload["expected_count"] != len(payload["items"]):
            raise ContractError("source collection count mismatch; input is rejected")
        if payload["errors"]:
            raise ContractError("source collection has unresolved errors; input is rejected")
        matches = [item for item in payload["items"] if item["id"] == worker_id]
        if not matches:
            matches = [item for item in payload["items"] if item.get("ids", {}).get("worker") == worker_id]
        if len(matches) != 1:
            raise ContractError("exact ID not found; no prefix or substitute lookup")
        item = matches[0]
        is_sealed = (item["status"] in TERMINAL_STATUSES or
                     item.get("controls", {}).get("sealed") is True)
        if is_sealed:
            diagnostic = "worker is sealed; post-completion input is rejected"
            return {
                "schema": SCHEMA,
                "status": "STOP",
                "diagnostic": diagnostic,
                "issues": [diagnostic],
                "source": artifact,
                "id": item["id"],
                "worker_status": item["status"],
                "sealed": True,
            }
        if item["status"] != "RUNNING":
            diagnostic = f"worker is not RUNNING ({item['status']}); input is rejected"
            return {
                "schema": SCHEMA,
                "status": "STOP",
                "diagnostic": diagnostic,
                "issues": [diagnostic],
                "source": artifact,
                "id": item["id"],
                "worker_status": item["status"],
                "sealed": False,
            }
        return {
            "schema": SCHEMA,
            "status": "OK",
            "source": artifact,
            "id": item["id"],
            "worker_status": item["status"],
            "sealed": False,
        }
    except (ContractError, TypeError, RecursionError) as exc:
        return {
            "schema": SCHEMA,
            "status": "STOP",
            "issues": [str(exc)],
            "next": "verify_source",
        }


def read_source(path: str, reference: str | None) -> tuple[bytes, str]:
    if path == "-":
        if not reference:
            raise ContractError("stdin requires --source-ref for an existing retrievable record")
        return sys.stdin.buffer.read(), reference
    if reference:
        raise ContractError("--source-ref is only for stdin")
    location = Path(path).resolve(strict=True)
    if not location.is_file():
        raise ContractError("source must designate a regular file, not a directory or special file")
    return location.read_bytes(), str(location)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("project", "get", "check-input"):
        aliases = ["check_input"] if command == "check-input" else []
        sub = subparsers.add_parser(command, aliases=aliases)
        sub.add_argument("source", help="JSON file, or - for a read-only pipe")
        sub.add_argument("--source-ref", help="exact existing record reference for stdin")
        if command in ("get", "check-input"):
            sub.add_argument("--id", required=True, help="exact record ID; no prefix matching")
        if command == "get":
            sub.add_argument("--sha256", required=True, help="source digest from the projection")
        elif command == "check-input":
            sub.add_argument("--sha256", default=None, help="source digest from the projection")
    args = parser.parse_args(argv)
    try:
        raw, reference = read_source(args.source, args.source_ref)
        if args.command == "project":
            result = project(raw, reference)
        elif args.command in ("check-input", "check_input"):
            result = check_input(raw, reference, args.id, args.sha256)
        else:
            if hashlib.sha256(raw).hexdigest() != args.sha256:
                raise ContractError("source changed; re-project and re-verify before deciding")
            payload = decode(raw)
            matches = [item for item in payload["items"] if item["id"] == args.id]
            if len(matches) != 1:
                raise ContractError("exact ID not found; no prefix or substitute lookup")
            # Inspection returns data without clearing the collection's stop.
            issues = assessment_issues(payload)
            result = {"schema": SCHEMA, "status": "STOP" if issues else "INSPECT", "mode": "INSPECT",
                      "issues": issues, "source": source_ref(raw, reference),
                      "complete": payload["complete"], "expected_count": payload["expected_count"],
                      "actual_count": len(payload["items"]), "errors": payload["errors"],
                      "item": matches[0]}
    except (OSError, ContractError, TypeError, RecursionError) as exc:
        result = {"schema": SCHEMA, "status": "STOP", "issues": [str(exc)], "next": "verify_source"}
    sys.stdout.buffer.write(encode(result))
    return 2 if result["status"] == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
