#!/usr/bin/env python3
"""Validate luucycle roster snapshots and role references without mutation."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path


FIELDS = (
    "Agent ID",
    "CLI",
    "Command",
    "Invocation",
    "Model",
    "Model Flag",
    "Bypass Flag",
    "Permission Profile",
    "Cost",
    "Accessible",
    "Strength",
    "Supersedes",
    "Verified",
)
REQUIRED_ROLES = ("verifier", "builder", "architect", "researcher", "scaffolder")
ROLES_HEADER = "| Role | When | Context to inject | Output format | Eligible agents (first = best) |"
HEADING = re.compile(r"^### (?P<agent>.+) @ (?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$")
FIELD = re.compile(r"^- (?P<name>[A-Za-z ]+): (?P<value>.+)$")


def clean(value: str) -> str:
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == "`" else value


def parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_roster(text: str) -> tuple[list[dict[str, str]], list[str]]:
    snapshots: list[dict[str, str]] = []
    errors: list[str] = []
    current: dict[str, str] | None = None

    for line_number, line in enumerate(text.splitlines(), 1):
        heading = HEADING.match(line)
        if heading:
            current = {
                "_heading": line[4:],
                "_heading_agent": heading.group("agent"),
                "_timestamp": heading.group("timestamp"),
                "_line": str(line_number),
                "_field_order": "",
            }
            snapshots.append(current)
            continue
        if line.startswith("### "):
            errors.append(f"line {line_number}: malformed snapshot heading")
            current = None
            continue
        field = FIELD.match(line)
        if field and current is not None:
            name = field.group("name")
            if name not in FIELDS:
                errors.append(f"{current['_heading']}: unknown field {name}")
            elif name in current:
                errors.append(f"{current['_heading']}: duplicate field {name}")
            else:
                current[name] = clean(field.group("value"))
                current["_field_order"] = "\0".join(filter(None, (current["_field_order"], name)))

    if not snapshots:
        return [], ["ROSTER.md contains no snapshots"]

    headings: dict[str, dict[str, str]] = {}
    for snapshot in snapshots:
        label = snapshot["_heading"]
        if label in headings:
            errors.append(f"{label}: duplicate snapshot heading")
        else:
            headings[label] = snapshot
        for name in FIELDS:
            if not snapshot.get(name):
                errors.append(f"{label}: missing {name}")
        if tuple(snapshot["_field_order"].split("\0")) != FIELDS:
            errors.append(f"{label}: fields must appear once in canonical order")
        if snapshot.get("Agent ID") != snapshot["_heading_agent"]:
            errors.append(f"{label}: heading and Agent ID differ")
        if parse_timestamp(snapshot["_timestamp"]) is None:
            errors.append(f"{label}: invalid timestamp")
        if snapshot.get("Cost") not in {"low", "medium", "high"}:
            errors.append(f"{label}: Cost must be low, medium, or high")
        if snapshot.get("Accessible") not in {"true", "false"}:
            errors.append(f"{label}: Accessible must be true or false")
        supersedes = snapshot.get("Supersedes")
        if supersedes and supersedes != "none" and supersedes not in headings:
            errors.append(f"{label}: Supersedes target does not exist: {supersedes}")

    by_agent: dict[str, list[dict[str, str]]] = {}
    for snapshot in snapshots:
        by_agent.setdefault(snapshot["_heading_agent"], []).append(snapshot)
    for agent_id, agent_snapshots in by_agent.items():
        valid = [item for item in agent_snapshots if parse_timestamp(item["_timestamp"]) is not None]
        valid.sort(key=lambda item: item["_timestamp"])
        for index, snapshot in enumerate(valid):
            supersedes = snapshot.get("Supersedes")
            if index == 0:
                if supersedes and supersedes != "none":
                    errors.append(f"{snapshot['_heading']}: first snapshot for {agent_id} must Supersede none")
                continue
            previous = valid[index - 1]
            if snapshot["_timestamp"] == previous["_timestamp"]:
                errors.append(f"{snapshot['_heading']}: duplicate timestamp for Agent ID {agent_id}")
            if supersedes != previous["_heading"]:
                errors.append(
                    f"{snapshot['_heading']}: Supersedes must reference the immediately prior snapshot "
                    f"{previous['_heading']}"
                )

    return snapshots, errors


def current_snapshots(snapshots: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for snapshot in snapshots:
        agent_id = snapshot.get("Agent ID", snapshot["_heading_agent"])
        previous = result.get(agent_id)
        stamp = parse_timestamp(snapshot["_timestamp"])
        if stamp is None:
            continue
        if previous is None:
            result[agent_id] = snapshot
            continue
        previous_stamp = parse_timestamp(previous["_timestamp"])
        if previous_stamp is None:
            result[agent_id] = snapshot
            continue
        if stamp > previous_stamp:
            result[agent_id] = snapshot
    return result


def parse_roles(text: str) -> tuple[dict[str, list[str]], list[str]]:
    roles: dict[str, list[str]] = {}
    errors: list[str] = []
    header_found = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if line == ROLES_HEADER:
            header_found = True
            continue
        if line.startswith("| Role |"):
            errors.append(f"ROLES.md line {line_number}: non-canonical table header")
            continue
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 5:
            errors.append(f"ROLES.md line {line_number}: expected 5 table columns")
            continue
        role = clean(cells[0])
        if role in roles:
            errors.append(f"ROLES.md line {line_number}: duplicate role {role}")
            continue
        if any(not cell for cell in cells[1:4]):
            errors.append(f"ROLES.md line {line_number}: When, Context, and Output must be populated")
        roles[role] = [clean(item) for item in re.split(r"\s*<br>\s*", cells[4]) if item.strip()]
    if not header_found:
        errors.append("ROLES.md is missing the canonical table header")
    return roles, errors


def validate(repo_root: Path) -> dict[str, object]:
    base = repo_root / ".agents" / "luucycle"
    paths = {name: base / name for name in ("ROSTER.md", "ROLES.md", "WARNINGS.md")}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        return {"status": "FAIL", "errors": [f"missing file: {path}" for path in missing], "warnings": []}

    roster_text = paths["ROSTER.md"].read_text()
    roles_text = paths["ROLES.md"].read_text()
    warnings_text = paths["WARNINGS.md"].read_text()
    errors: list[str] = []
    if not roster_text.startswith("# luucycle Roster\n") or "\n## Agents\n" not in roster_text:
        errors.append("ROSTER.md is missing its canonical document header")
    if not roles_text.startswith("# luucycle Roles\n"):
        errors.append("ROLES.md is missing its canonical document header")
    if not warnings_text.startswith("# luucycle WARNINGS\n"):
        errors.append("WARNINGS.md is missing its canonical document header")

    snapshots, roster_errors = parse_roster(roster_text)
    errors.extend(roster_errors)
    current = current_snapshots(snapshots) if snapshots else {}
    roles, role_errors = parse_roles(roles_text)
    errors.extend(role_errors)
    warnings: list[str] = []

    missing_roles = [role for role in REQUIRED_ROLES if role not in roles]
    unknown_roles = [role for role in roles if role not in REQUIRED_ROLES]
    errors.extend(f"missing canonical role: {role}" for role in missing_roles)
    errors.extend(f"unknown role: {role}" for role in unknown_roles)
    canonical_order = tuple(role for role in roles if role in REQUIRED_ROLES)
    if not missing_roles and canonical_order != REQUIRED_ROLES:
        errors.append("canonical roles must appear in ROSTER-FORMAT.md order")

    for role, agent_ids in roles.items():
        for agent_id in agent_ids:
            if agent_id not in current:
                errors.append(f"role {role}: unknown Agent ID {agent_id}")
        if not any(current.get(agent_id, {}).get("Accessible") == "true" for agent_id in agent_ids):
            warnings.append(f"role {role}: no accessible eligible agent")

    assigned = {agent_id for agent_ids in roles.values() for agent_id in agent_ids}
    for agent_id, snapshot in current.items():
        if snapshot.get("Accessible") == "true" and agent_id not in assigned:
            errors.append(f"accessible Agent ID is not assigned to a role: {agent_id}")

    accessible = sorted(agent_id for agent_id, item in current.items() if item.get("Accessible") == "true")
    if not accessible:
        errors.append("zero accessible agents")

    agents = []
    for agent_id, snapshot in sorted(current.items()):
        agents.append(
            {
                "agent_id": agent_id,
                "cli": snapshot.get("CLI", ""),
                "model": snapshot.get("Model", ""),
                "cost": snapshot.get("Cost", ""),
                "accessible": snapshot.get("Accessible", ""),
                "roles": [role for role, agent_ids in roles.items() if agent_id in agent_ids],
                "verified": snapshot.get("Verified", ""),
            }
        )

    return {
        "status": "FAIL" if errors else "WARN" if warnings else "PASS",
        "agents": agents,
        "current_agents": sorted(current),
        "accessible_agents": accessible,
        "roles": roles,
        "errors": errors,
        "warnings": warnings,
    }


def self_test() -> None:
    roster = """### codex:gpt-test @ 2026-08-22T12:00:00Z

- Agent ID: `codex:gpt-test`
- CLI: `Codex`
- Command: `codex`
- Invocation: `exec`
- Model: `gpt-test`
- Model Flag: `--model {model}`
- Bypass Flag: `none - sandboxed`
- Permission Profile: `workspace write`
- Cost: `medium`
- Accessible: `true`
- Strength: `implementation`
- Supersedes: `none`
- Verified: `2026-08-22; local help`
"""
    snapshots, errors = parse_roster(roster)
    assert not errors, errors
    assert current_snapshots(snapshots)["codex:gpt-test"]["Model"] == "gpt-test"
    roles, errors = parse_roles(
        f"{ROLES_HEADER}\n| --- | --- | --- | --- | --- |\n"
        "| `builder` | build | context | output | `codex:gpt-test` |"
    )
    assert not errors, errors
    assert roles == {"builder": ["codex:gpt-test"]}, roles

    duplicate_field = roster.replace("- Cost: `medium`", "- Cost: `medium`\n- Cost: `high`")
    _, errors = parse_roster(duplicate_field)
    assert any("duplicate field Cost" in error for error in errors), errors

    updated = roster + roster.replace(
        "2026-08-22T12:00:00Z", "2026-08-23T12:00:00Z"
    ).replace("- Model: `gpt-test`", "- Model: `gpt-test-v2`").replace(
        "- Supersedes: `none`", "- Supersedes: `codex:gpt-test @ 2026-08-22T12:00:00Z`"
    )
    _, errors = parse_roster(updated)
    assert not errors, errors
    _, errors = parse_roster(updated.replace(
        "- Supersedes: `codex:gpt-test @ 2026-08-22T12:00:00Z`", "- Supersedes: `none`"
    ))
    assert any("immediately prior snapshot" in error for error in errors), errors

    all_role_rows = "\n".join(
        f"| `{role}` | work | context | output | `codex:gpt-test` |" for role in REQUIRED_ROLES
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        roster_dir = root / ".agents" / "luucycle"
        roster_dir.mkdir(parents=True)
        (roster_dir / "ROSTER.md").write_text(f"# luucycle Roster\n\n## Agents\n\n{roster}")
        (roster_dir / "WARNINGS.md").write_text("# luucycle WARNINGS\n")
        (roster_dir / "ROLES.md").write_text(
            f"# luucycle Roles\n\n{ROLES_HEADER}\n| --- | --- | --- | --- | --- |\n{all_role_rows}\n"
        )
        result = validate(root)
        assert result["status"] == "PASS", result
        assert result["agents"] == [
            {
                "agent_id": "codex:gpt-test",
                "cli": "Codex",
                "model": "gpt-test",
                "cost": "medium",
                "accessible": "true",
                "roles": list(REQUIRED_ROLES),
                "verified": "2026-08-22; local help",
            }
        ], result

        (roster_dir / "ROLES.md").write_text(
            f"# luucycle Roles\n\n{ROLES_HEADER}\n| --- | --- | --- | --- | --- |\n"
            "| `builder` | work | context | output | `codex:gpt-test` |\n"
        )
        result = validate(root)
        assert result["status"] == "FAIL", result
        assert "missing canonical role: verifier" in result["errors"], result
    print("check_roster self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    result = validate(Path(args.repo_root).resolve())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["status"])
        for kind in ("errors", "warnings"):
            for message in result[kind]:
                print(f"{kind[:-1].upper()}: {message}")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
