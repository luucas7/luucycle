#!/usr/bin/env python3
"""Deterministic luucycle roster validation, selection, planning, and apply."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any


FIELDS = (
    "CLI",
    "Command",
    "Invocation",
    "Model",
    "Model Flag",
    "Bypass Flag",
    "Cost",
    "Enabled",
    "Verified",
)
LEGACY_FIELDS = ("Permission Profile",)
REQUIRED_ROLES = ("verifier", "builder", "architect", "researcher", "scaffolder")
ROLES_HEADER = "| Role | When | Context to inject | Output format | Eligible agents (`agent@fit`, highest first) |"
LEGACY_ROLES_HEADERS = {"| Role | When | Context to inject | Output format | Eligible agents (first = best) |"}
ROLES_SEPARATOR = "| --- | --- | --- | --- | --- |"
HEADING = re.compile(r"^### (?P<agent>.+)$")
FIELD = re.compile(r"^- (?P<name>[A-Za-z ]+): (?P<value>.+)$")
COST_ORDER = {"low": 0, "medium": 1, "high": 2}
PLAN_VERSION = 1
WORKER_CLI_CANDIDATES = (
    "codex",
    "cline",
    "opencode",
    "agy",
    "claude",
    "gemini",
    "aider",
    "cursor-agent",
    "amp",
    "goose",
)

FIELD_TO_JSON = {
    "CLI": "cli",
    "Command": "command",
    "Invocation": "invocation",
    "Model": "model",
    "Model Flag": "model_flag",
    "Bypass Flag": "bypass_flag",
    "Cost": "cost",
    "Enabled": "enabled",
    "Verified": "verified",
}
JSON_TO_FIELD = {value: key for key, value in FIELD_TO_JSON.items()}
AGENT_PROPOSAL_KEYS = {
    "agent_id",
    "Agent ID",
    *FIELDS,
    *FIELD_TO_JSON.values(),
    *LEGACY_FIELDS,
    "permission_profile",
}


@dataclass(frozen=True)
class AgentEntry:
    agent_id: str
    fields: dict[str, str]
    line: int = 0
    field_order: tuple[str, ...] = ()

    def legacy_dict(self) -> dict[str, str]:
        result = {
            "_heading": self.agent_id,
            "_heading_agent": self.agent_id,
            "_line": str(self.line),
            "_field_order": "\0".join(self.field_order),
        }
        result.update(self.fields)
        return result

    def summary(self, roles: dict[str, list[str]], role_scores: dict[str, dict[str, Decimal]]) -> dict[str, object]:
        assigned_roles = [role for role, agent_ids in roles.items() if self.agent_id in agent_ids]
        return {
            "agent_id": self.agent_id,
            "cli": self.fields.get("CLI", ""),
            "model": self.fields.get("Model", ""),
            "cost": self.fields.get("Cost", ""),
            "enabled": self.fields.get("Enabled", ""),
            "roles": assigned_roles,
            "role_fit": {
                role: format_role_score(role_scores.get(role, {}).get(self.agent_id, Decimal("1.0")))
                for role in assigned_roles
            },
            "verified": self.fields.get("Verified", ""),
        }

    def contract(self, role_fit: Decimal | None = None) -> dict[str, object]:
        model_flag = self.fields.get("Model Flag", "")
        bypass_flag = self.fields.get("Bypass Flag", "")
        resolved_model_flag = resolve_template(model_flag, self.fields)
        resolved_bypass_flag = resolve_template(bypass_flag, self.fields)
        parts = [
            self.fields.get("Command", ""),
            self.fields.get("Invocation", ""),
            resolved_model_flag or "",
            resolved_bypass_flag or "",
        ]
        command_preview = " ".join(part for part in parts if part).strip()
        contract = {
            "agent_id": self.agent_id,
            "cli": self.fields.get("CLI", ""),
            "command": self.fields.get("Command", ""),
            "invocation": self.fields.get("Invocation", ""),
            "model": self.fields.get("Model", ""),
            "model_flag": model_flag,
            "resolved_model_flag": resolved_model_flag,
            "bypass_flag": bypass_flag,
            "resolved_bypass_flag": resolved_bypass_flag,
            "cost": self.fields.get("Cost", ""),
            "enabled": self.fields.get("Enabled", ""),
            "verified": self.fields.get("Verified", ""),
            "command_preview": command_preview,
        }
        if role_fit is not None:
            contract["role_fit"] = format_role_score(role_fit)
        return contract


@dataclass(frozen=True)
class RoleRow:
    role: str
    when: str
    context: str
    output: str
    agents: list[str]
    scores: dict[str, Decimal]
    line: int = 0


@dataclass(frozen=True)
class RosterDocument:
    entries: list[AgentEntry]
    errors: list[str]


@dataclass(frozen=True)
class RolesDocument:
    rows: list[RoleRow]
    errors: list[str]

    @property
    def roles(self) -> dict[str, list[str]]:
        return {row.role: list(row.agents) for row in self.rows}

    @property
    def role_scores(self) -> dict[str, dict[str, Decimal]]:
        return {row.role: dict(row.scores) for row in self.rows}

    @property
    def row_by_role(self) -> dict[str, RoleRow]:
        return {row.role: row for row in self.rows}


@dataclass(frozen=True)
class RosterPaths:
    base: Path
    roster: Path
    roles: Path
    warnings: Path


@dataclass(frozen=True)
class RosterState:
    paths: RosterPaths
    roster_text: str
    roles_text: str
    warnings_text: str
    missing: list[Path]


def clean(value: str) -> str:
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == "`" else value


def format_role_score(score: Decimal) -> str:
    rendered = format(score.normalize(), "f")
    return rendered if "." in rendered else f"{rendered}.0"


def parse_role_reference(value: str, label: str, errors: list[str]) -> tuple[str, Decimal | None]:
    if "@" not in value:
        return value, None
    agent_id, _, raw_score = value.rpartition("@")
    if not agent_id or not raw_score:
        errors.append(f"{label}: expected <agent-id>@<fit>")
        return agent_id or value, None
    try:
        score = Decimal(raw_score)
    except InvalidOperation:
        errors.append(f"{label}: role fit must be a decimal greater than 0 and at most 1")
        return agent_id, None
    if not score.is_finite():
        errors.append(f"{label}: role fit must be a finite decimal greater than 0 and at most 1")
        return agent_id, None
    decimal_places = max(0, -score.as_tuple().exponent)
    if score <= 0 or score > 1 or decimal_places > 2:
        errors.append(f"{label}: role fit must be a decimal greater than 0 and at most 1, with at most two places")
        return agent_id, None
    return agent_id, score


def tick(value: str) -> str:
    return f"`{value}`"


def json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def resolve_template(value: str, fields: dict[str, str]) -> str | None:
    if not value or value.lower().startswith("none"):
        return None
    return value.replace("{model}", fields.get("Model", ""))


def roster_paths(repo_root: Path) -> RosterPaths:
    base = repo_root / ".agents" / "luucycle"
    return RosterPaths(
        base=base,
        roster=base / "ROSTER.md",
        roles=base / "ROLES.md",
        warnings=base / "WARNINGS.md",
    )


def read_state(repo_root: Path) -> RosterState:
    paths = roster_paths(repo_root)
    missing = [path for path in (paths.roster, paths.roles, paths.warnings) if not path.is_file()]
    return RosterState(
        paths=paths,
        roster_text=paths.roster.read_text() if paths.roster.is_file() else "",
        roles_text=paths.roles.read_text() if paths.roles.is_file() else "",
        warnings_text=paths.warnings.read_text() if paths.warnings.is_file() else "",
        missing=missing,
    )


def parse_roster_document(text: str) -> RosterDocument:
    entries: list[AgentEntry] = []
    errors: list[str] = []
    current_agent: str | None = None
    current_fields: dict[str, str] = {}
    current_order: list[str] = []
    current_line = 0

    def finish_current() -> None:
        if current_agent is not None:
            entries.append(
                AgentEntry(
                    agent_id=current_agent,
                    fields=dict(current_fields),
                    line=current_line,
                    field_order=tuple(current_order),
                )
            )

    for line_number, line in enumerate(text.splitlines(), 1):
        heading = HEADING.match(line)
        if heading:
            finish_current()
            current_agent = heading.group("agent").strip()
            current_fields = {}
            current_order = []
            current_line = line_number
            if not current_agent:
                errors.append(f"line {line_number}: empty Agent ID heading")
            continue
        field = FIELD.match(line)
        if field and current_agent is not None:
            name = field.group("name")
            if name in LEGACY_FIELDS:
                continue
            if name not in FIELDS:
                errors.append(f"{current_agent}: unknown field {name}")
            elif name in current_fields:
                errors.append(f"{current_agent}: duplicate field {name}")
            else:
                current_fields[name] = clean(field.group("value"))
                current_order.append(name)
    finish_current()

    if not entries:
        return RosterDocument([], ["ROSTER.md contains no agents"])

    agent_ids: set[str] = set()
    for entry in entries:
        label = entry.agent_id
        if label in agent_ids:
            errors.append(f"{label}: duplicate Agent ID")
        else:
            agent_ids.add(label)
        for name in FIELDS:
            if not entry.fields.get(name):
                errors.append(f"{label}: missing {name}")
        if entry.field_order != FIELDS:
            errors.append(f"{label}: fields must appear once in canonical order")
        if entry.fields.get("Cost") not in COST_ORDER:
            errors.append(f"{label}: Cost must be low, medium, or high")
        if entry.fields.get("Enabled") not in {"true", "false"}:
            errors.append(f"{label}: Enabled must be true or false")

    return RosterDocument(entries, errors)


def parse_roster(text: str) -> tuple[list[dict[str, str]], list[str]]:
    document = parse_roster_document(text)
    return [entry.legacy_dict() for entry in document.entries], list(document.errors)


def parse_roles_document(text: str) -> RolesDocument:
    rows: list[RoleRow] = []
    errors: list[str] = []
    roles_seen: set[str] = set()
    header_found = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if line == ROLES_HEADER or line in LEGACY_ROLES_HEADERS:
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
        if role in roles_seen:
            errors.append(f"ROLES.md line {line_number}: duplicate role {role}")
            continue
        roles_seen.add(role)
        if any(not cell for cell in cells[1:4]):
            errors.append(f"ROLES.md line {line_number}: When, Context, and Output must be populated")
        agents: list[str] = []
        scores: dict[str, Decimal] = {}
        for index, item in enumerate(re.split(r"\s*<br>\s*", cells[4])):
            if not item.strip():
                continue
            agent_id, score = parse_role_reference(
                clean(item),
                f"ROLES.md line {line_number} agent {index + 1}",
                errors,
            )
            if agent_id in agents:
                errors.append(f"ROLES.md line {line_number}: duplicate Agent ID {agent_id}")
                continue
            agents.append(agent_id)
            if score is not None:
                scores[agent_id] = score
        rows.append(
            RoleRow(
                role=role,
                when=cells[1],
                context=cells[2],
                output=cells[3],
                agents=agents,
                scores=scores,
                line=line_number,
            )
        )
    if not header_found:
        errors.append("ROLES.md is missing the canonical table header")
    return RolesDocument(rows, errors)


def parse_roles(text: str) -> tuple[dict[str, list[str]], list[str]]:
    document = parse_roles_document(text)
    return document.roles, list(document.errors)


def validate_texts(roster_text: str, roles_text: str, warnings_text: str) -> dict[str, object]:
    errors: list[str] = []
    if not roster_text.startswith("# luucycle Roster\n") or "\n## Agents\n" not in roster_text:
        errors.append("ROSTER.md is missing its canonical document header")
    if not roles_text.startswith("# luucycle Roles\n"):
        errors.append("ROLES.md is missing its canonical document header")
    if not warnings_text.startswith("# luucycle WARNINGS\n"):
        errors.append("WARNINGS.md is missing its canonical document header")

    roster_doc = parse_roster_document(roster_text)
    errors.extend(roster_doc.errors)
    agents_by_id = {entry.agent_id: entry for entry in roster_doc.entries}
    roles_doc = parse_roles_document(roles_text)
    errors.extend(roles_doc.errors)
    roles = roles_doc.roles
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
            if agent_id not in agents_by_id:
                errors.append(f"role {role}: unknown Agent ID {agent_id}")
        if not any(agents_by_id.get(agent_id, AgentEntry("", {})).fields.get("Enabled") == "true" for agent_id in agent_ids):
            warnings.append(f"role {role}: no enabled eligible agent")

    assigned = {agent_id for agent_ids in roles.values() for agent_id in agent_ids}
    for agent_id, entry in agents_by_id.items():
        if entry.fields.get("Enabled") == "true" and agent_id not in assigned:
            errors.append(f"enabled Agent ID is not assigned to a role: {agent_id}")

    enabled = sorted(agent_id for agent_id, item in agents_by_id.items() if item.fields.get("Enabled") == "true")
    if not enabled:
        errors.append("zero enabled agents")

    return {
        "status": "FAIL" if errors else "WARN" if warnings else "PASS",
        "agents": [
            entry.summary(roles, roles_doc.role_scores)
            for entry in sorted(agents_by_id.values(), key=lambda item: item.agent_id)
        ],
        "enabled_agents": enabled,
        "roles": roles,
        "errors": errors,
        "warnings": warnings,
    }


def validate(repo_root: Path) -> dict[str, object]:
    state = read_state(repo_root)
    if state.missing:
        return {
            "status": "FAIL",
            "errors": [f"missing file: {path}" for path in state.missing],
            "warnings": [],
        }
    return validate_texts(state.roster_text, state.roles_text, state.warnings_text)


def render_roster(entries: list[AgentEntry]) -> str:
    blocks = []
    for entry in entries:
        lines = [f"### {entry.agent_id}", ""]
        lines.extend(f"- {name}: {tick(entry.fields[name])}" for name in FIELDS)
        blocks.append("\n".join(lines))
    return "# luucycle Roster\n\nCurrent worker facts. Each Agent ID appears once.\n\n## Agents\n\n" + "\n\n".join(blocks) + "\n"


def render_roles(rows: list[RoleRow]) -> str:
    rendered_rows = []
    for row in rows:
        agent_cell = "<br>".join(
            tick(
                f"{agent_id}@{format_role_score(row.scores[agent_id])}"
                if agent_id in row.scores
                else agent_id
            )
            for agent_id in row.agents
        )
        rendered_rows.append(
            f"| {tick(row.role)} | {row.when} | {row.context} | {row.output} | {agent_cell} |"
        )
    return "# luucycle Roles\n\n" + ROLES_HEADER + "\n" + ROLES_SEPARATOR + "\n" + "\n".join(rendered_rows) + "\n"


def ensure_clean_scalar(value: object, label: str, errors: list[str]) -> str:
    if isinstance(value, bool):
        value = "true" if value else "false"
    if not isinstance(value, str):
        errors.append(f"{label}: must be a string")
        return ""
    value = value.strip()
    if not value:
        errors.append(f"{label}: must not be empty")
    if "\n" in value or "\r" in value:
        errors.append(f"{label}: must not contain newlines")
    return value


def normalize_agent_proposal(item: object, index: int, errors: list[str]) -> AgentEntry | None:
    label = f"roster[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{label}: must be an object")
        return None
    unknown = sorted(set(item) - AGENT_PROPOSAL_KEYS)
    if unknown:
        errors.append(f"{label}: unknown keys: {', '.join(unknown)}")
    agent_id_values = []
    for key in ("agent_id", "Agent ID"):
        if key in item:
            agent_id_values.append(ensure_clean_scalar(item[key], f"{label}.{key}", errors))
    if not agent_id_values:
        errors.append(f"{label}: missing agent_id")
        agent_id = ""
    elif len(set(agent_id_values)) > 1:
        errors.append(f"{label}: conflicting agent_id values")
        agent_id = agent_id_values[0]
    else:
        agent_id = agent_id_values[0]

    fields: dict[str, str] = {}
    for field_name in FIELDS:
        json_key = FIELD_TO_JSON[field_name]
        values = []
        if field_name in item:
            values.append(ensure_clean_scalar(item[field_name], f"{label}.{field_name}", errors))
        if json_key in item:
            values.append(ensure_clean_scalar(item[json_key], f"{label}.{json_key}", errors))
        if not values:
            errors.append(f"{label}: missing {json_key}")
            continue
        if len(set(values)) > 1:
            errors.append(f"{label}: conflicting values for {json_key}")
        value = values[0]
        if field_name == "Cost":
            value = value.lower()
        if field_name == "Enabled":
            value = value.lower()
        fields[field_name] = value
    if len(fields) != len(FIELDS):
        return None
    return AgentEntry(agent_id=agent_id, fields=fields, field_order=FIELDS)


def normalize_roles_proposal(value: object, errors: list[str]) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append("roles: must be an object mapping role to full eligible Agent ID list")
        return {}
    roles: dict[str, list[str]] = {}
    for role, agent_ids in value.items():
        clean_role = ensure_clean_scalar(role, f"roles.{role}", errors)
        if not isinstance(agent_ids, list):
            errors.append(f"roles.{clean_role}: must be a list")
            continue
        normalized_ids = []
        seen: set[str] = set()
        for index, reference in enumerate(agent_ids):
            label = f"roles.{clean_role}[{index}]"
            clean_reference = ensure_clean_scalar(reference, label, errors)
            clean_agent_id, score = parse_role_reference(clean_reference, label, errors)
            if clean_agent_id in seen:
                errors.append(f"roles.{clean_role}: duplicate Agent ID {clean_agent_id}")
            seen.add(clean_agent_id)
            normalized_ids.append(
                f"{clean_agent_id}@{format_role_score(score)}" if score is not None else clean_agent_id
            )
        roles[clean_role] = normalized_ids
    return roles


def load_json_file(path: str) -> Any:
    if path == "-":
        return json.load(os.fdopen(os.dup(0)))
    with Path(path).open() as handle:
        return json.load(handle)


def normalize_proposal(proposal: object) -> tuple[dict[str, object], list[AgentEntry], dict[str, list[str]], list[str]]:
    errors: list[str] = []
    if not isinstance(proposal, dict):
        return {}, [], {}, ["proposal must be a JSON object"]
    unknown = sorted(set(proposal) - {"version", "roster", "roles"})
    if unknown:
        errors.append(f"proposal: unknown keys: {', '.join(unknown)}")
    version = proposal.get("version", PLAN_VERSION)
    if version != PLAN_VERSION:
        errors.append(f"proposal.version: expected {PLAN_VERSION}")

    roster_items = proposal.get("roster", [])
    if roster_items is None:
        roster_items = []
    if not isinstance(roster_items, list):
        errors.append("roster: must be a list")
        roster_items = []
    entries = [
        entry
        for index, item in enumerate(roster_items)
        for entry in [normalize_agent_proposal(item, index, errors)]
        if entry is not None
    ]
    seen_agent_ids: set[str] = set()
    for entry in entries:
        if entry.agent_id in seen_agent_ids:
            errors.append(f"roster: duplicate proposal Agent ID {entry.agent_id}")
        seen_agent_ids.add(entry.agent_id)

    role_updates = normalize_roles_proposal(proposal.get("roles", {}), errors)
    if not entries and not role_updates:
        errors.append("proposal must include at least one roster entry or role update")
    normalized = {
        "version": PLAN_VERSION,
        "roster": [agent_to_proposal(entry) for entry in entries],
        "roles": role_updates,
    }
    return normalized, entries, role_updates, errors


def agent_to_proposal(entry: AgentEntry) -> dict[str, str]:
    result = {"agent_id": entry.agent_id}
    result.update({FIELD_TO_JSON[name]: entry.fields[name] for name in FIELDS})
    return result


def build_planned_texts(
    current_roster_text: str,
    current_roles_text: str,
    proposed_entries: list[AgentEntry],
    role_updates: dict[str, list[str]],
) -> tuple[str, str, list[str]]:
    errors: list[str] = []
    roster_doc = parse_roster_document(current_roster_text)
    roles_doc = parse_roles_document(current_roles_text)
    errors.extend(roster_doc.errors)
    errors.extend(roles_doc.errors)
    if errors:
        return "", "", errors

    by_agent_id = {entry.agent_id: entry for entry in roster_doc.entries}
    updated_entries: list[AgentEntry] = []
    proposed_by_id = {entry.agent_id: entry for entry in proposed_entries}
    for entry in roster_doc.entries:
        updated_entries.append(proposed_by_id.get(entry.agent_id, entry))
    existing = set(by_agent_id)
    for entry in proposed_entries:
        if entry.agent_id not in existing:
            updated_entries.append(entry)

    rows_by_role = roles_doc.row_by_role
    for role in role_updates:
        if role not in rows_by_role:
            errors.append(f"roles.{role}: role does not exist in ROLES.md")
    if errors:
        return "", "", errors
    updated_rows = []
    for row in roles_doc.rows:
        agents = row.agents
        scores = row.scores
        if row.role in role_updates:
            agents = []
            scores = {}
            for index, reference in enumerate(role_updates[row.role]):
                agent_id, score = parse_role_reference(
                    reference,
                    f"roles.{row.role}[{index}]",
                    errors,
                )
                agents.append(agent_id)
                if score is not None:
                    scores[agent_id] = score
        updated_rows.append(
            RoleRow(
                role=row.role,
                when=row.when,
                context=row.context,
                output=row.output,
                agents=agents,
                scores=scores,
                line=row.line,
            )
        )
    if errors:
        return "", "", errors
    return render_roster(updated_entries), render_roles(updated_rows), []


def plan_roster(repo_root: Path, proposal_path: str) -> dict[str, object]:
    state = read_state(repo_root)
    if state.missing:
        return {
            "status": "FAIL",
            "errors": [f"missing file: {path}" for path in state.missing],
            "warnings": [],
        }
    try:
        proposal = load_json_file(proposal_path)
    except (OSError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "errors": [f"could not read proposal: {error}"], "warnings": []}
    normalized, entries, role_updates, errors = normalize_proposal(proposal)
    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": []}
    roster_preview, roles_preview, build_errors = build_planned_texts(
        state.roster_text,
        state.roles_text,
        entries,
        role_updates,
    )
    if build_errors:
        return {"status": "FAIL", "errors": build_errors, "warnings": []}
    validation = validate_texts(roster_preview, roles_preview, state.warnings_text)
    if validation["status"] == "FAIL":
        return {"status": "FAIL", "errors": validation["errors"], "warnings": validation["warnings"]}
    return {
        "status": validation["status"],
        "plan_version": PLAN_VERSION,
        "repo_root": str(repo_root),
        "proposal": normalized,
        "base_hashes": {
            "ROSTER.md": sha256_text(state.roster_text),
            "ROLES.md": sha256_text(state.roles_text),
        },
        "expected_hashes": {
            "ROSTER.md": sha256_text(roster_preview),
            "ROLES.md": sha256_text(roles_preview),
        },
        "previews": {
            "ROSTER.md": roster_preview,
            "ROLES.md": roles_preview,
        },
        "changes": {
            "roster_upserts": [entry.agent_id for entry in entries],
            "roles_replaced": list(role_updates),
        },
        "validation": validation,
        "errors": [],
        "warnings": validation["warnings"],
    }


def validate_plan_document(plan: object) -> tuple[dict[str, object] | None, list[str]]:
    if not isinstance(plan, dict):
        return None, ["plan must be a JSON object"]
    errors: list[str] = []
    if plan.get("plan_version") != PLAN_VERSION:
        errors.append(f"plan_version: expected {PLAN_VERSION}")
    if plan.get("status") not in {"PASS", "WARN"}:
        errors.append("plan status must be PASS or WARN")
    for key in ("base_hashes", "expected_hashes", "previews"):
        if not isinstance(plan.get(key), dict):
            errors.append(f"{key}: must be an object")
    if errors:
        return None, errors
    previews = plan["previews"]
    expected_hashes = plan["expected_hashes"]
    for name in ("ROSTER.md", "ROLES.md"):
        if not isinstance(previews.get(name), str):
            errors.append(f"previews.{name}: must be a string")
            continue
        if expected_hashes.get(name) != sha256_text(previews[name]):
            errors.append(f"expected_hashes.{name}: does not match preview content")
    return plan if not errors else None, errors


def atomic_write_text(path: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def apply_plan(repo_root: Path, plan_path: str) -> dict[str, object]:
    state = read_state(repo_root)
    if state.missing:
        return {
            "status": "FAIL",
            "errors": [f"missing file: {path}" for path in state.missing],
            "warnings": [],
        }
    try:
        loaded_plan = load_json_file(plan_path)
    except (OSError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "errors": [f"could not read plan: {error}"], "warnings": []}
    plan, plan_errors = validate_plan_document(loaded_plan)
    if plan_errors or plan is None:
        return {"status": "FAIL", "errors": plan_errors, "warnings": []}
    current_hashes = {
        "ROSTER.md": sha256_text(state.roster_text),
        "ROLES.md": sha256_text(state.roles_text),
    }
    stale = [
        f"{name}: current hash {current_hashes[name]} does not match approved base {plan['base_hashes'].get(name)}"
        for name in ("ROSTER.md", "ROLES.md")
        if current_hashes[name] != plan["base_hashes"].get(name)
    ]
    if stale:
        return {"status": "FAIL", "errors": stale, "warnings": []}

    roster_preview = plan["previews"]["ROSTER.md"]
    roles_preview = plan["previews"]["ROLES.md"]
    validation = validate_texts(roster_preview, roles_preview, state.warnings_text)
    if validation["status"] == "FAIL":
        return {
            "status": "FAIL",
            "errors": [f"planned state invalid: {error}" for error in validation["errors"]],
            "warnings": validation["warnings"],
        }

    written = []
    if state.roster_text != roster_preview:
        atomic_write_text(state.paths.roster, roster_preview)
        written.append(str(state.paths.roster))
    if state.roles_text != roles_preview:
        atomic_write_text(state.paths.roles, roles_preview)
        written.append(str(state.paths.roles))
    return {
        "status": "PASS",
        "written": written,
        "expected_hashes": plan["expected_hashes"],
        "validation": validation,
        "errors": [],
        "warnings": validation["warnings"],
    }


def select_agents(
    repo_root: Path,
    role: str,
    max_cost: str,
    avoid: list[str] | None = None,
    avoid_cli: list[str] | None = None,
) -> dict[str, object]:
    state = read_state(repo_root)
    if state.missing:
        return {
            "status": "FAIL",
            "role": role,
            "errors": [f"missing file: {path}" for path in state.missing],
            "warnings": [],
        }
    validation = validate_texts(state.roster_text, state.roles_text, state.warnings_text)
    if validation["status"] == "FAIL":
        return {
            "status": "FAIL",
            "role": role,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }
    roster_doc = parse_roster_document(state.roster_text)
    roles_doc = parse_roles_document(state.roles_text)
    agents_by_id = {entry.agent_id: entry for entry in roster_doc.entries}
    roles = roles_doc.roles
    if role not in roles:
        return {"status": "FAIL", "role": role, "errors": [f"unknown role: {role}"], "warnings": []}

    avoid_set = set(avoid or [])
    avoid_cli_set = set(avoid_cli or [])
    warnings = list(validation["warnings"])

    max_rank = COST_ORDER[max_cost]
    role_row = roles_doc.row_by_role[role]
    eligible: list[tuple[AgentEntry, Decimal]] = []
    skipped: list[dict[str, str]] = []
    for agent_id in roles[role]:
        entry = agents_by_id.get(agent_id)
        if entry is None:
            skipped.append({"agent_id": agent_id, "reason": "unknown"})
            continue
        if entry.fields.get("Enabled") != "true":
            skipped.append({"agent_id": agent_id, "reason": "disabled"})
            continue
        cost = entry.fields.get("Cost", "")
        if COST_ORDER.get(cost, 99) > max_rank:
            skipped.append({"agent_id": agent_id, "reason": f"cost>{max_cost}"})
            continue
        eligible.append((entry, role_row.scores.get(agent_id, Decimal("1.0"))))
    eligible.sort(key=lambda candidate: candidate[1], reverse=True)
    if not eligible:
        return {
            "status": "FAIL",
            "role": role,
            "max_cost": max_cost,
            "errors": [f"role {role}: no enabled eligible agent at or below {max_cost} cost"],
            "warnings": warnings,
            "skipped": skipped,
        }

    distinct_clis = sorted({entry.fields.get("CLI", "") for entry, _ in eligible})
    if len(distinct_clis) < 2:
        warnings.append(
            f"role {role}: every eligible agent runs the same CLI ({distinct_clis[0]}) - "
            "a credit or availability outage on that product strands the whole role; "
            "consider /luucycle roster add"
        )

    primary: AgentEntry | None = None
    primary_fit: Decimal | None = None
    primary_skipped: list[dict[str, str]] = []
    for entry, role_fit in eligible:
        if entry.agent_id in avoid_set:
            primary_skipped.append({"agent_id": entry.agent_id, "reason": "avoided"})
            continue
        if entry.fields.get("CLI", "") in avoid_cli_set:
            primary_skipped.append({"agent_id": entry.agent_id, "reason": "cli_avoided"})
            continue
        primary = entry
        primary_fit = role_fit
        break
    if primary is None:
        primary, primary_fit = eligible[0]
        warnings.append(
            f"role {role}: every eligible agent is already assigned in this plan or runs an "
            f"excluded CLI; reusing {primary.agent_id} - consider /luucycle roster add"
        )

    fallback: AgentEntry | None = None
    fallback_fit: Decimal | None = None
    fallback_skipped: list[dict[str, str]] = []
    primary_cli = primary.fields.get("CLI", "")
    for entry, role_fit in eligible:
        if entry.agent_id == primary.agent_id:
            continue
        if entry.agent_id in avoid_set:
            fallback_skipped.append({"agent_id": entry.agent_id, "reason": "already_assigned"})
            continue
        if entry.fields.get("CLI", "") == primary_cli:
            fallback_skipped.append({"agent_id": entry.agent_id, "reason": "same_cli_as_primary"})
            continue
        fallback = entry
        fallback_fit = role_fit
        break
    if fallback is None:
        warnings.append(
            f"role {role}: no fallback on a different CLI than {primary.agent_id}; "
            "consider /luucycle roster add"
        )

    return {
        "status": "PASS",
        "role": role,
        "max_cost": max_cost,
        "primary": primary.agent_id,
        "fallback": fallback.agent_id if fallback else None,
        "contracts": {
            "primary": primary.contract(primary_fit),
            "fallback": fallback.contract(fallback_fit) if fallback else None,
        },
        "skipped": skipped + primary_skipped + fallback_skipped,
        "errors": [],
        "warnings": warnings,
    }


def compact_list(repo_root: Path) -> dict[str, object]:
    result = validate(repo_root)
    return {
        "status": result["status"],
        "agents": result.get("agents", []),
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
    }


def emit(result: dict[str, object], json_mode: bool) -> None:
    if json_mode:
        print(json_dumps(result))
        return
    print(result.get("status", "UNKNOWN"))
    for kind in ("errors", "warnings"):
        for message in result.get(kind, []):
            print(f"{kind[:-1].upper()}: {message}")


def exit_code(result: dict[str, object]) -> int:
    return 1 if result.get("status") == "FAIL" else 0


def sample_roster(
    agent_id: str,
    model: str,
    cost: str = "medium",
    enabled: str = "true",
    cli: str = "Codex",
) -> str:
    return f"""### {agent_id}

- CLI: `{cli}`
- Command: `codex`
- Invocation: `exec`
- Model: `{model}`
- Model Flag: `--model {{model}}`
- Bypass Flag: `none - sandboxed`
- Cost: `{cost}`
- Enabled: `{enabled}`
- Verified: `2026-08-22; local help`
"""


def write_sample_repo(root: Path) -> Path:
    roster_dir = root / ".agents" / "luucycle"
    roster_dir.mkdir(parents=True)
    roster = "\n\n".join(
        [
            sample_roster("codex:gpt-primary", "gpt-primary", "medium", "true", "Codex").strip(),
            sample_roster("codex:gpt-disabled", "gpt-disabled", "low", "false", "Codex").strip(),
            sample_roster("claude:gpt-fallback", "gpt-fallback", "medium", "true", "Claude").strip(),
            sample_roster("gemini:gpt-high", "gpt-high", "high", "true", "Gemini").strip(),
        ]
    )
    all_role_rows = "\n".join(
        f"| `{role}` | work | context | output | `claude:gpt-fallback@0.7`<br>`codex:gpt-primary@0.9`<br>`codex:gpt-disabled@0.8`<br>`gemini:gpt-high@0.6` |"
        for role in REQUIRED_ROLES
    )
    (roster_dir / "ROSTER.md").write_text("# luucycle Roster\n\nCurrent worker facts. Each Agent ID appears once.\n\n## Agents\n\n" + roster + "\n")
    (roster_dir / "WARNINGS.md").write_text("# luucycle WARNINGS\n\n_None yet._\n")
    (roster_dir / "ROLES.md").write_text(
        f"# luucycle Roles\n\n{ROLES_HEADER}\n{ROLES_SEPARATOR}\n{all_role_rows}\n"
    )
    return roster_dir


def self_test() -> None:
    roster = sample_roster("codex:gpt-test", "gpt-test")
    entries, errors = parse_roster(roster)
    assert not errors, errors
    assert entries[0]["Model"] == "gpt-test"
    roles, errors = parse_roles(
        f"{ROLES_HEADER}\n{ROLES_SEPARATOR}\n"
        "| `builder` | build | context | output | `codex:gpt-test@0.75` |"
    )
    assert not errors, errors
    assert roles == {"builder": ["codex:gpt-test"]}, roles

    duplicate_field = roster.replace("- Cost: `medium`", "- Cost: `medium`\n- Cost: `high`")
    _, errors = parse_roster(duplicate_field)
    assert any("duplicate field Cost" in error for error in errors), errors

    legacy_fields = roster.replace(
        "- CLI: `Codex`", "- Agent ID: `codex:gpt-test`\n- CLI: `Codex`"
    ).replace("- Verified:", "- Strength: `implementation`\n- Verified:")
    _, errors = parse_roster(legacy_fields)
    assert any("unknown field Agent ID" in error for error in errors), errors
    assert any("unknown field Strength" in error for error in errors), errors

    _, errors = parse_roster(roster + roster)
    assert any("duplicate Agent ID" in error for error in errors), errors

    legacy_profile = roster.replace(
        "- Cost: `medium`",
        "- Permission Profile: `workspace write with differently worded approval`\n- Cost: `medium`",
    )
    _, errors = parse_roster(legacy_profile)
    assert not errors, errors

    _, errors = parse_roles(
        f"{ROLES_HEADER}\n{ROLES_SEPARATOR}\n"
        "| `builder` | build | context | output | `codex:gpt-test@1.01` |"
    )
    assert any("role fit must be" in error for error in errors), errors

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        roster_dir = write_sample_repo(root)
        result = validate(root)
        assert result["status"] == "PASS", result
        assert result["enabled_agents"] == ["claude:gpt-fallback", "codex:gpt-primary", "gemini:gpt-high"], result

        selection = select_agents(root, "builder", "medium")
        assert selection["status"] == "PASS", selection
        assert selection["primary"] == "codex:gpt-primary", selection
        assert selection["fallback"] == "claude:gpt-fallback", selection
        assert selection["contracts"]["primary"]["role_fit"] == "0.9", selection
        assert selection["contracts"]["fallback"]["role_fit"] == "0.7", selection
        assert selection["contracts"]["primary"]["resolved_model_flag"] == "--model gpt-primary", selection
        high_selection = select_agents(root, "builder", "low")
        assert high_selection["status"] == "FAIL", high_selection

        avoided = select_agents(root, "builder", "medium", avoid=["codex:gpt-primary"])
        assert avoided["status"] == "PASS", avoided
        assert avoided["primary"] == "claude:gpt-fallback", avoided
        assert avoided["fallback"] is None, avoided
        assert any("no fallback on a different CLI" in message for message in avoided["warnings"]), avoided

        avoided_cli = select_agents(root, "builder", "medium", avoid_cli=["Codex"])
        assert avoided_cli["status"] == "PASS", avoided_cli
        assert avoided_cli["primary"] == "claude:gpt-fallback", avoided_cli

        exhausted = select_agents(root, "builder", "medium", avoid=["codex:gpt-primary", "claude:gpt-fallback"])
        assert exhausted["status"] == "PASS", exhausted
        assert exhausted["primary"] == "codex:gpt-primary", exhausted
        assert any("reusing codex:gpt-primary" in message for message in exhausted["warnings"]), exhausted

        proposal_path = root / "proposal.json"
        plan_path = root / "plan.json"
        proposal = {
            "version": PLAN_VERSION,
            "roster": [
                {
                    "agent_id": "codex:gpt-new",
                    "cli": "Codex",
                    "command": "codex",
                    "invocation": "exec",
                    "model": "gpt-new",
                    "model_flag": "--model {model}",
                    "bypass_flag": "none - sandboxed",
                    "cost": "low",
                    "enabled": "true",
                    "verified": "2026-08-23; local help",
                }
            ],
            "roles": {"builder": ["codex:gpt-new@0.95", "codex:gpt-primary@0.9", "claude:gpt-fallback@0.7"]},
        }
        proposal_path.write_text(json_dumps(proposal))
        planned = plan_roster(root, str(proposal_path))
        assert planned["status"] == "PASS", planned
        assert "codex:gpt-new" in planned["previews"]["ROSTER.md"], planned
        assert "gemini:gpt-high" in planned["previews"]["ROSTER.md"], planned
        assert any(line.startswith("| `verifier` |") for line in planned["previews"]["ROLES.md"].splitlines()), planned
        plan_path.write_text(json_dumps(planned))
        applied = apply_plan(root, str(plan_path))
        assert applied["status"] == "PASS", applied
        assert str(roster_dir / "ROSTER.md") in applied["written"], applied
        assert str(roster_dir / "ROLES.md") in applied["written"], applied
        post_selection = select_agents(root, "builder", "low")
        assert post_selection["primary"] == "codex:gpt-new", post_selection

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_sample_repo(root)
        proposal_path = root / "proposal.json"
        plan_path = root / "plan.json"
        proposal_path.write_text(
            json_dumps(
                {
                    "version": PLAN_VERSION,
                    "roles": {"builder": ["codex:gpt-primary@0.9", "claude:gpt-fallback@0.7"]},
                }
            )
        )
        planned = plan_roster(root, str(proposal_path))
        assert planned["status"] == "PASS", planned
        plan_path.write_text(json_dumps(planned))
        (root / ".agents" / "luucycle" / "ROLES.md").write_text("stale\n")
        rejected = apply_plan(root, str(plan_path))
        assert rejected["status"] == "FAIL", rejected
        assert any("does not match approved base" in error for error in rejected["errors"]), rejected

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        roster_dir = root / ".agents" / "luucycle"
        roster_dir.mkdir(parents=True)
        single_roster = "\n\n".join(
            [
                sample_roster("codex:agent-a", "agent-a", "low", "true", "Codex").strip(),
                sample_roster("codex:agent-b", "agent-b", "low", "true", "Codex").strip(),
            ]
        )
        (roster_dir / "ROSTER.md").write_text(
            "# luucycle Roster\n\nCurrent worker facts. Each Agent ID appears once.\n\n## Agents\n\n" + single_roster + "\n"
        )
        (roster_dir / "ROLES.md").write_text(
            "# luucycle Roles\n\n"
            f"{ROLES_HEADER}\n{ROLES_SEPARATOR}\n"
            + "\n".join(
                f"| `{role}` | work | context | output | `codex:agent-a@0.9`<br>`codex:agent-b@0.8` |"
                for role in REQUIRED_ROLES
            )
            + "\n"
        )
        (roster_dir / "WARNINGS.md").write_text("# luucycle WARNINGS\n\n_None yet._\n")
        single_cli = select_agents(root, "builder", "medium")
        assert single_cli["status"] == "PASS", single_cli
        assert single_cli["primary"] == "codex:agent-a", single_cli
        assert single_cli["fallback"] is None, single_cli
        assert any("same CLI" in message for message in single_cli["warnings"]), single_cli
        assert any("no fallback on a different CLI" in message for message in single_cli["warnings"]), single_cli

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        roster_dir = root / ".agents" / "luucycle"
        roster_dir.mkdir(parents=True)
        primary_block = sample_roster("codex:legacy-primary", "legacy-primary", cli="Codex").strip().replace(
            "- Cost: `medium`",
            "- Permission Profile: `workspace auto approval`\n- Cost: `medium`",
        )
        fallback_block = sample_roster("cline:legacy-fallback", "legacy-fallback", cli="Cline").strip().replace(
            "- Cost: `medium`",
            "- Permission Profile: `accept edits and commands without prompting`\n- Cost: `medium`",
        )
        (roster_dir / "ROSTER.md").write_text(
            "# luucycle Roster\n\nCurrent worker facts. Each Agent ID appears once.\n\n## Agents\n\n"
            f"{primary_block}\n\n{fallback_block}\n"
        )
        legacy_header = next(iter(LEGACY_ROLES_HEADERS))
        legacy_rows = "\n".join(
            f"| `{role}` | work | context | output | `codex:legacy-primary`<br>`cline:legacy-fallback` |"
            for role in REQUIRED_ROLES
        )
        (roster_dir / "ROLES.md").write_text(
            f"# luucycle Roles\n\n{legacy_header}\n{ROLES_SEPARATOR}\n{legacy_rows}\n"
        )
        (roster_dir / "WARNINGS.md").write_text("# luucycle WARNINGS\n\n_None yet._\n")
        legacy_selection = select_agents(root, "builder", "medium")
        assert legacy_selection["status"] == "PASS", legacy_selection
        assert legacy_selection["primary"] == "codex:legacy-primary", legacy_selection
        assert legacy_selection["fallback"] == "cline:legacy-fallback", legacy_selection
        assert "permission_profile" not in legacy_selection["contracts"]["primary"], legacy_selection

    bad_proposal, _, _, errors = normalize_proposal({"roster": [{"agent_id": "missing-fields"}]})
    assert bad_proposal["roster"] == [], bad_proposal
    assert any("missing cli" in error for error in errors), errors
    print("roster self-test: PASS")


def legacy_self_test() -> None:
    self_test()
    print("check_roster self-test: PASS")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--repo-root", dest="repo_root_option")
    parser.add_argument("--json", action="store_true")


def effective_repo_root(args: argparse.Namespace) -> Path:
    return Path(args.repo_root_option or args.repo_root).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check")
    add_common_args(check_parser)

    list_parser = subparsers.add_parser("list")
    add_common_args(list_parser)

    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("role")
    add_common_args(select_parser)
    select_parser.add_argument("--max-cost", choices=tuple(COST_ORDER), default="high")
    select_parser.add_argument("--avoid", action="append", default=[], metavar="AGENT_ID")
    select_parser.add_argument("--avoid-cli", action="append", default=[], metavar="CLI")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("proposal")
    add_common_args(plan_parser)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("plan")
    add_common_args(apply_parser)

    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.command is None:
        parser.error("a subcommand is required")

    repo_root = effective_repo_root(args)
    if args.command == "check":
        result = validate(repo_root)
    elif args.command == "list":
        result = compact_list(repo_root)
    elif args.command == "select":
        result = select_agents(repo_root, args.role, args.max_cost, args.avoid, args.avoid_cli)
    elif args.command == "plan":
        result = plan_roster(repo_root, args.proposal)
    elif args.command == "apply":
        result = apply_plan(repo_root, args.plan)
    else:
        parser.error(f"unknown subcommand: {args.command}")
    emit(result, args.json)
    return exit_code(result)


def legacy_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        legacy_self_test()
        return 0
    result = validate(Path(args.repo_root).resolve())
    emit(result, args.json)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
