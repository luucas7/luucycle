#!/usr/bin/env python3
"""Read-only luucycle diagnostics with compact, deterministic JSON output."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any


CHECK_KEYS = ("check", "status", "required", "summary", "evidence", "error", "warning")
CHECK_STATUSES = {"PASS", "WARN", "FAIL", "UNKNOWN"}
SCOPES = ("core", "task", "complete")
EXTRA_COMPLETE_SKILLS = ("grill-with-docs", "setup-matt-pocock-skills", "orca-cli")
FEATURE_SETUP_SKILLS = {"grill-with-docs", "setup-matt-pocock-skills", "to-spec", "to-tickets"}
UI_SETUP_SKILLS = {"impeccable"}
ROSTER_FIELD = re.compile(r"^- (?P<name>[A-Za-z ]+): (?P<value>.+)$")
ROSTER_HEADING = re.compile(r"^### (?P<agent>.+)$")
FRONTMATTER_NAME = re.compile(r"^name:\s*(?P<name>.+?)\s*$", re.MULTILINE)
ROUTING_ROW = re.compile(r"^\|\s*(?P<intent>[^|]+)\|\s*(?P<skill>[^|]+)\|")
OPTION = re.compile(r"(?<![A-Za-z0-9_-])(--[A-Za-z0-9][A-Za-z0-9_-]*|-[A-Za-z])")


def trim_text(value: str, limit: int = 1200) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def clean(value: str) -> str:
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == "`" else value


def make_check(
    name: str,
    status: str,
    *,
    required: bool,
    summary: str = "",
    evidence: list[str] | None = None,
    error: list[str] | None = None,
    warning: list[str] | None = None,
) -> dict[str, Any]:
    if status not in CHECK_STATUSES:
        raise ValueError(f"invalid check status: {status}")
    record = {
        "check": name,
        "status": status,
        "required": required,
        "summary": summary,
        "evidence": sorted(evidence or []),
        "error": sorted(error or []),
        "warning": sorted(warning or []),
    }
    return {key: record[key] for key in CHECK_KEYS}


def run_bounded(argv: list[str], env: dict[str, str], timeout: float = 8.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return {
            "argv": argv,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
            "error": "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
            "error": f"timed out after {timeout:g}s",
        }
    except OSError as exc:
        return {
            "argv": argv,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": str(exc),
        }


def command_display(argv: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def resolve_command(command: str, env: dict[str, str]) -> tuple[list[str], str | None, str | None]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return [], None, f"cannot parse command: {exc}"
    if not argv:
        return [], None, "empty command"

    executable = argv[0]
    if "/" in executable:
        path = Path(executable).expanduser()
        resolved = str(path if path.is_absolute() else path.resolve())
        if not Path(resolved).is_file():
            return argv, None, f"executable not found: {executable}"
        if not os.access(resolved, os.X_OK):
            return argv, None, f"executable is not executable: {executable}"
        return [resolved, *argv[1:]], resolved, None

    resolved = shutil.which(executable, path=env.get("PATH"))
    if resolved is None:
        return argv, None, f"executable not found on PATH: {executable}"
    return [resolved, *argv[1:]], resolved, None


def is_orca_managed_terminal(env: dict[str, str]) -> bool:
    markers = (
        "ORCA_TERMINAL_HANDLE",
        "ORCA_APP_VERSION",
        "ORCA_PANE_KEY",
        "ORCA_WORKTREE_ID",
        "ORCA_AGENT_HOOK_ENDPOINT",
    )
    return any(env.get(marker) for marker in markers)


def select_orca_command(env: dict[str, str]) -> tuple[str, str]:
    if env.get("ORCA_CLI_COMMAND"):
        return env["ORCA_CLI_COMMAND"], "ORCA_CLI_COMMAND"
    if env.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev", "ORCA_DEV_REPO_ROOT"
    if platform.system() == "Linux" and not is_orca_managed_terminal(env):
        return "orca-ide", "linux outside Orca-managed terminal"
    return "orca", "default Orca-managed or non-Linux command"


def runtime_state(payload: Any) -> tuple[bool | None, str]:
    if isinstance(payload, dict):
        if payload.get("ok") is False:
            return False, "ok=false"
        runtime = payload.get("runtime")
        if isinstance(runtime, dict):
            state = runtime.get("state") or runtime.get("status")
            reachable = runtime.get("reachable")
            if state in {"ready", "running"} and reachable is not False:
                return True, f"runtime.{state}"
            if isinstance(state, str):
                return False, f"runtime.{state}"
        result = payload.get("result")
        if result is not payload:
            nested, evidence = runtime_state(result)
            if nested is not None:
                return nested, evidence
        app = payload.get("app")
        if isinstance(app, dict) and app.get("running") is True:
            return True, "app.running=true"
        for key in ("state", "status"):
            value = payload.get(key)
            if value in {"ready", "running"}:
                return True, f"{key}={value}"
            if isinstance(value, str) and value:
                return False, f"{key}={value}"
        for value in payload.values():
            nested, evidence = runtime_state(value)
            if nested is not None:
                return nested, evidence
    elif isinstance(payload, list):
        for value in payload:
            nested, evidence = runtime_state(value)
            if nested is not None:
                return nested, evidence
    return None, "runtime state not found"


def check_orca(env: dict[str, str]) -> tuple[list[dict[str, Any]], list[str] | None]:
    checks: list[dict[str, Any]] = []
    command, reason = select_orca_command(env)
    argv, resolved, error = resolve_command(command, env)
    evidence = [f"selection={command}", f"reason={reason}"]
    if resolved:
        evidence.append(f"resolved={resolved}")
    if error:
        checks.append(
            make_check(
                "orca.executable",
                "FAIL",
                required=True,
                summary="Orca executable could not be resolved",
                evidence=evidence,
                error=[error],
            )
        )
        checks.append(
            make_check(
                "orca.status",
                "UNKNOWN",
                required=True,
                summary="Skipped because Orca executable is unavailable",
                evidence=evidence,
                error=["skipped: executable resolution failed"],
            )
        )
        checks.append(
            make_check(
                "orca.guide",
                "UNKNOWN",
                required=True,
                summary="Skipped because Orca executable is unavailable",
                evidence=evidence,
                error=["skipped: executable resolution failed"],
            )
        )
        return checks, None

    checks.append(
        make_check(
            "orca.executable",
            "PASS",
            required=True,
            summary="Orca executable resolved",
            evidence=evidence,
        )
    )

    status = run_bounded([*argv, "status", "--json"], env)
    status_evidence = [f"command={command_display([*argv, 'status', '--json'])}"]
    if status["timed_out"]:
        checks.append(
            make_check(
                "orca.status",
                "UNKNOWN",
                required=True,
                summary="Orca status timed out",
                evidence=status_evidence,
                error=[status["error"]],
            )
        )
    elif status["error"]:
        checks.append(
            make_check(
                "orca.status",
                "UNKNOWN",
                required=True,
                summary="Orca status could not run",
                evidence=status_evidence,
                error=[status["error"]],
            )
        )
    elif status["returncode"] != 0:
        checks.append(
            make_check(
                "orca.status",
                "FAIL",
                required=True,
                summary="Orca status returned nonzero",
                evidence=[*status_evidence, f"exit={status['returncode']}"],
                error=[trim_text(status["stderr"] or status["stdout"])],
            )
        )
    else:
        try:
            payload = json.loads(status["stdout"])
            running, state_evidence = runtime_state(payload)
            if running is True:
                checks.append(
                    make_check(
                        "orca.status",
                        "PASS",
                        required=True,
                        summary="Orca runtime is reachable",
                        evidence=[*status_evidence, state_evidence],
                    )
                )
            elif running is False:
                checks.append(
                    make_check(
                        "orca.status",
                        "FAIL",
                        required=True,
                        summary="Orca runtime is not ready",
                        evidence=[*status_evidence, state_evidence],
                        error=["runtime is not ready"],
                    )
                )
            else:
                checks.append(
                    make_check(
                        "orca.status",
                        "UNKNOWN",
                        required=True,
                        summary="Orca status JSON did not expose runtime state",
                        evidence=status_evidence,
                        error=[state_evidence],
                    )
                )
        except json.JSONDecodeError as exc:
            checks.append(
                make_check(
                    "orca.status",
                    "UNKNOWN",
                    required=True,
                    summary="Orca status did not return parseable JSON",
                    evidence=status_evidence,
                    error=[f"json parse error: {exc}"],
                )
            )

    guide = run_bounded([*argv, "skills", "get", "orchestration"], env)
    guide_evidence = [f"command={command_display([*argv, 'skills', 'get', 'orchestration'])}"]
    guide_text = f"{guide['stdout']}\n{guide['stderr']}"
    if guide["timed_out"]:
        checks.append(
            make_check(
                "orca.guide",
                "UNKNOWN",
                required=True,
                summary="Version-matched orchestration guide timed out",
                evidence=guide_evidence,
                error=[guide["error"]],
            )
        )
    elif guide["error"]:
        checks.append(
            make_check(
                "orca.guide",
                "UNKNOWN",
                required=True,
                summary="Version-matched orchestration guide could not run",
                evidence=guide_evidence,
                error=[guide["error"]],
            )
        )
    elif guide["returncode"] == 0 and "orchestration" in guide_text.lower():
        checks.append(
            make_check(
                "orca.guide",
                "PASS",
                required=True,
                summary="Version-matched orchestration guide is available",
                evidence=[*guide_evidence, f"bytes={len(guide_text)}"],
            )
        )
    else:
        status = "UNKNOWN" if "unknown command" in guide_text.lower() else "FAIL"
        checks.append(
            make_check(
                "orca.guide",
                status,
                required=True,
                summary="Version-matched orchestration guide is unavailable",
                evidence=[*guide_evidence, f"exit={guide['returncode']}"],
                error=[trim_text(guide_text)],
            )
        )
    return checks, argv


def skill_roots(repo_root: Path, env: dict[str, str]) -> list[Path]:
    home = Path(env.get("HOME", str(Path.home()))).expanduser()
    codex_home = Path(env.get("CODEX_HOME", str(home / ".codex"))).expanduser()
    candidates = [
        repo_root / "skills",
        repo_root / ".codex" / "skills",
        repo_root / ".agents" / "skills",
        codex_home / "skills",
        home / ".codex" / "skills",
        home / ".agents" / "skills",
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            roots.append(candidate)
            seen.add(key)
    return roots


def parse_skill_name(skill_md: Path) -> str | None:
    try:
        text = skill_md.read_text(errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    frontmatter = text[3:end] if end != -1 else text[:4096]
    match = FRONTMATTER_NAME.search(frontmatter)
    if not match:
        return None
    return clean(match.group("name").strip().strip("\"'"))


def discover_skills(repo_root: Path, env: dict[str, str]) -> tuple[dict[str, list[str]], list[str]]:
    discovered: dict[str, list[str]] = {}
    searched: list[str] = []
    for root in skill_roots(repo_root, env):
        searched.append(str(root))
        if not root.is_dir():
            continue
        candidates = list(root.glob("*/SKILL.md")) + list(root.glob(".*/*/SKILL.md"))
        for skill_md in sorted(set(candidates)):
            folder_name = skill_md.parent.name
            names = {folder_name}
            parsed = parse_skill_name(skill_md)
            if parsed:
                names.add(parsed)
            for name in names:
                discovered.setdefault(name, []).append(str(skill_md))
    for paths in discovered.values():
        paths.sort()
    return discovered, searched


def extract_skill_groups_from_routing(skill_root: Path) -> list[tuple[str, ...]]:
    routing = skill_root / "ROUTING.md"
    groups: list[tuple[str, ...]] = []
    if not routing.is_file():
        return groups
    for line in routing.read_text(errors="replace").splitlines():
        match = ROUTING_ROW.match(line)
        if not match:
            continue
        cell = match.group("skill")
        names = re.findall(r"`([^`]+)`", cell)
        if names:
            groups.append(tuple(names))
    return groups


def normalize_skill_groups(names: list[str]) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    for name in names:
        parts = [part.strip() for part in re.split(r"\s*/\s*", name) if part.strip()]
        if parts:
            groups.append(tuple(parts))
    return groups


def dedupe_groups(groups: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    result: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        normalized = tuple(dict.fromkeys(group))
        key = tuple(sorted(normalized))
        if key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def group_label(group: tuple[str, ...]) -> str:
    return "/".join(group)


def check_skills(
    repo_root: Path,
    skill_root: Path,
    scope: str,
    required_skill: list[str],
    env: dict[str, str],
) -> tuple[list[dict[str, Any]], set[str]]:
    discovered, searched = discover_skills(repo_root, env)
    required_groups = [("orchestration",)]
    optional_groups: list[tuple[str, ...]] = []

    if scope == "task":
        required_groups.extend(normalize_skill_groups(required_skill))
    elif scope == "complete":
        complete_groups = extract_skill_groups_from_routing(skill_root)
        complete_groups.extend((skill,) for skill in EXTRA_COMPLETE_SKILLS)
        for group in complete_groups:
            if "orchestration" in group:
                continue
            optional_groups.append(group)

    required_groups = dedupe_groups(required_groups)
    optional_groups = dedupe_groups(optional_groups)
    selected = {name for group in required_groups + optional_groups for name in group}

    checks = [
        make_check(
            "skills.search_paths",
            "PASS",
            required=False,
            summary="Skill search paths inspected without invoking installers",
            evidence=searched,
        )
    ]

    for required, groups in ((True, required_groups), (False, optional_groups)):
        for group in groups:
            found = {name: discovered[name] for name in group if name in discovered}
            label = group_label(group)
            if found:
                checks.append(
                    make_check(
                        f"skill.{label}",
                        "PASS",
                        required=required,
                        summary="Required skill is installed" if required else "Optional scoped skill is installed",
                        evidence=[f"{name}={paths[0]}" for name, paths in sorted(found.items())],
                    )
                )
            else:
                status = "FAIL" if required else "WARN"
                checks.append(
                    make_check(
                        f"skill.{label}",
                        status,
                        required=required,
                        summary="Required skill is missing" if required else "Optional scoped skill is missing",
                        evidence=[f"searched={len(searched)} paths"],
                        error=[f"missing skill: {label}"] if required else [],
                        warning=[f"missing optional skill: {label}"] if not required else [],
                    )
                )
    return checks, selected


def discover_impeccable_context_paths(repo_root: Path, discovered: dict[str, list[str]]) -> list[Path]:
    candidates = [
        repo_root / "docs" / "agents" / "design-context.md",
        repo_root / "docs" / "agents" / "ui-design-context.md",
        repo_root / "docs" / "agents" / "impeccable.md",
        repo_root / ".agents" / "impeccable" / "design-context.md",
        repo_root / ".impeccable" / "design-context.md",
    ]
    for skill_path in discovered.get("impeccable", []):
        skill_md = Path(skill_path)
        try:
            text = skill_md.read_text(errors="replace")
        except OSError:
            continue
        for token in re.findall(r"`([^`]*(?:design|context|agents)[^`]*)`", text, flags=re.IGNORECASE):
            if "/" not in token or token.startswith("/"):
                continue
            if any(ch in token for ch in "*?{}$"):
                continue
            candidates.append(repo_root / token)
    result: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def check_project_setup(
    repo_root: Path,
    scope: str,
    selected_skills: set[str],
    env: dict[str, str],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    need_feature = scope == "complete" or bool(selected_skills & FEATURE_SETUP_SKILLS)
    need_ui = scope == "complete" or bool(selected_skills & UI_SETUP_SKILLS)
    if not need_feature and not need_ui:
        return checks

    if need_feature:
        path = repo_root / "docs" / "agents" / "issue-tracker.md"
        required = scope != "complete"
        if path.is_file():
            checks.append(
                make_check(
                    "project.issue_tracker",
                    "PASS",
                    required=required,
                    summary="Feature-alignment issue tracker artifact exists",
                    evidence=[str(path)],
                )
            )
        else:
            checks.append(
                make_check(
                    "project.issue_tracker",
                    "FAIL" if required else "WARN",
                    required=required,
                    summary="Feature-alignment issue tracker artifact is missing",
                    evidence=[str(path)],
                    error=[f"missing file: {path}"] if required else [],
                    warning=[f"missing optional file: {path}"] if not required else [],
                )
            )

    if need_ui:
        discovered, _searched = discover_skills(repo_root, env)
        candidates = discover_impeccable_context_paths(repo_root, discovered)
        existing = [path for path in candidates if path.exists()]
        required = scope != "complete"
        if existing:
            checks.append(
                make_check(
                    "project.impeccable_context",
                    "PASS",
                    required=required,
                    summary="Impeccable design-context artifact exists",
                    evidence=[str(path) for path in existing],
                )
            )
        else:
            status = "FAIL" if required else "WARN"
            checks.append(
                make_check(
                    "project.impeccable_context",
                    status,
                    required=required,
                    summary="Impeccable design-context artifact is missing",
                    evidence=[f"candidate={path}" for path in candidates],
                    error=["missing impeccable design-context artifact"] if required else [],
                    warning=["missing optional impeccable design-context artifact"] if not required else [],
                )
            )
    return checks


def parse_roster_entries(repo_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    roster_path = repo_root / ".agents" / "luucycle" / "ROSTER.md"
    if not roster_path.is_file():
        return [], [f"missing file: {roster_path}"]
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    errors: list[str] = []
    for line_number, line in enumerate(roster_path.read_text(errors="replace").splitlines(), 1):
        heading = ROSTER_HEADING.match(line)
        if heading:
            current = {"agent_id": heading.group("agent")}
            entries.append(current)
            continue
        field = ROSTER_FIELD.match(line)
        if field and current is not None:
            current[field.group("name")] = clean(field.group("value"))
        elif line.startswith("- ") and current is not None:
            errors.append(f"line {line_number}: malformed roster field")
    return entries, errors


def check_roster(repo_root: Path, skill_root: Path, env: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    script = skill_root / "scripts" / "check_roster.py"
    if not script.is_file():
        return None, make_check(
            "roster.validation",
            "FAIL",
            required=True,
            summary="Roster validator script is missing",
            evidence=[str(script)],
            error=[f"missing file: {script}"],
        )
    command = [sys.executable or "python3", "-B", str(script), str(repo_root), "--json"]
    result = run_bounded(command, env, timeout=8.0)
    evidence = [f"command={command_display(command)}"]
    if result["timed_out"]:
        return None, make_check(
            "roster.validation",
            "UNKNOWN",
            required=True,
            summary="Roster validation timed out",
            evidence=evidence,
            error=[result["error"]],
        )
    if result["error"]:
        return None, make_check(
            "roster.validation",
            "UNKNOWN",
            required=True,
            summary="Roster validation could not run",
            evidence=evidence,
            error=[result["error"]],
        )
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return None, make_check(
            "roster.validation",
            "UNKNOWN",
            required=True,
            summary="Roster validation did not return parseable JSON",
            evidence=[*evidence, f"exit={result['returncode']}"],
            error=[f"json parse error: {exc}", trim_text(result["stderr"] or result["stdout"])],
        )

    roster_status = payload.get("status")
    if roster_status == "PASS":
        check_status = "PASS"
    elif roster_status == "WARN":
        check_status = "WARN"
    else:
        check_status = "FAIL"
    errors = [str(item) for item in payload.get("errors", [])]
    warnings = [str(item) for item in payload.get("warnings", [])]
    enabled_count = len(payload.get("enabled_agents", []) or [])
    agent_count = len(payload.get("agents", []) or [])
    return payload, make_check(
        "roster.validation",
        check_status,
        required=True,
        summary="Roster validator completed",
        evidence=[*evidence, f"status={roster_status}", f"agents={agent_count}", f"enabled_agents={enabled_count}"],
        error=errors,
        warning=warnings,
    )


def invocation_help_tokens(invocation: str) -> list[str]:
    if not invocation or invocation.lower().startswith("none"):
        return []
    try:
        tokens = shlex.split(invocation)
    except ValueError:
        return []
    result: list[str] = []
    for token in tokens:
        if "{" in token or "}" in token or token.startswith("<"):
            break
        if token.startswith("-"):
            break
        result.append(token)
    return result[:2]


def option_from_template(template: str) -> tuple[str | None, str]:
    value = template.strip()
    if not value:
        return None, "empty"
    if value.lower().startswith("none"):
        reason = value[4:].strip()
        if reason.startswith("-") and reason[1:].strip():
            return None, "none"
        return None, "none_without_reason"
    match = OPTION.search(value)
    if not match:
        return None, "unparsed"
    return match.group(1), "flag"


def help_commands(base_argv: list[str], invocation: str) -> list[list[str]]:
    commands = [[*base_argv, "--help"]]
    tokens = invocation_help_tokens(invocation)
    if tokens:
        commands.append([*base_argv, *tokens, "--help"])
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for command in commands:
        key = tuple(command)
        if key not in seen:
            deduped.append(command)
            seen.add(key)
    return deduped


def check_cli_entry(entry: dict[str, str], env: dict[str, str]) -> dict[str, Any]:
    agent_id = entry.get("agent_id", "<unknown>")
    command = entry.get("Command", "")
    argv, resolved, resolve_error = resolve_command(command, env)
    evidence = [f"agent={agent_id}", f"command={command or '<empty>'}"]
    errors: list[str] = []
    warnings: list[str] = []
    if resolve_error:
        return make_check(
            f"cli.{agent_id}",
            "FAIL",
            required=False,
            summary="Enabled CLI command could not be resolved",
            evidence=evidence,
            error=[resolve_error],
        )
    if resolved:
        evidence.append(f"resolved={resolved}")

    first = Path(argv[0]).name if argv else ""
    if first == "npx":
        return make_check(
            f"cli.{agent_id}",
            "FAIL",
            required=False,
            summary="Enabled CLI uses npx, which doctor never invokes",
            evidence=evidence,
            error=["npx command skipped by read-only diagnostic policy"],
        )

    combined_help = ""
    help_evidence: list[str] = []
    for command_argv in help_commands(argv, entry.get("Invocation", "")):
        result = run_bounded(command_argv, env, timeout=6.0)
        display = command_display(command_argv)
        if result["timed_out"]:
            errors.append(f"help timed out: {display}")
            continue
        if result["error"]:
            errors.append(f"help failed to start: {display}: {result['error']}")
            continue
        output = f"{result['stdout']}\n{result['stderr']}"
        combined_help += "\n" + output
        help_evidence.append(f"help={display} exit={result['returncode']} bytes={len(output)}")
        if result["returncode"] != 0 and not output.strip():
            warnings.append(f"help returned nonzero without output: {display}")
    evidence.extend(help_evidence)
    if not combined_help.strip():
        errors.append("no help output captured")

    for field in ("Model Flag", "Bypass Flag"):
        option, kind = option_from_template(entry.get(field, ""))
        if kind == "none":
            evidence.append(f"{field}=none")
            continue
        if kind == "none_without_reason":
            errors.append(f"{field} records none without a reason")
            continue
        if option is None:
            errors.append(f"{field} could not be parsed: {entry.get(field, '')}")
            continue
        if option in combined_help:
            evidence.append(f"{field}={option}:present")
        else:
            errors.append(f"{field} not present in help: {option}")

    return make_check(
        f"cli.{agent_id}",
        "FAIL" if errors else "WARN" if warnings else "PASS",
        required=False,
        summary="Enabled CLI help and declared flags checked",
        evidence=evidence,
        error=errors,
        warning=warnings,
    )


def check_enabled_clis(repo_root: Path, roster_payload: dict[str, Any] | None, env: dict[str, str]) -> list[dict[str, Any]]:
    entries, parse_errors = parse_roster_entries(repo_root)
    enabled_ids = {
        str(item.get("agent_id"))
        for item in (roster_payload or {}).get("agents", [])
        if item.get("enabled") == "true" and item.get("roles")
    }
    enabled_entries = [entry for entry in entries if entry.get("Enabled") == "true"]
    if enabled_ids:
        enabled_entries = [entry for entry in enabled_entries if entry.get("agent_id") in enabled_ids]

    cli_checks = [check_cli_entry(entry, env) for entry in sorted(enabled_entries, key=lambda item: item.get("agent_id", ""))]
    pass_count = sum(1 for check in cli_checks if check["status"] == "PASS")
    evidence = [f"enabled_role_mapped_agents={len(enabled_entries)}", f"passing_cli_checks={pass_count}"]
    errors = parse_errors[:]
    warnings: list[str] = []
    for check in cli_checks:
        if check["status"] != "PASS":
            warnings.append(f"{check['check']} status={check['status']}")
    if not enabled_entries:
        errors.append("no enabled role-mapped agents found")
    if pass_count == 0:
        errors.append("no enabled role-mapped agent has a passing CLI help check")

    aggregate = make_check(
        "cli.enabled_available",
        "FAIL" if errors else "WARN" if warnings else "PASS",
        required=True,
        summary="At least one enabled role-mapped worker CLI is usable",
        evidence=evidence,
        error=errors,
        warning=warnings,
    )
    return [aggregate, *cli_checks]


def check_cli_diversity(roster_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    agents = (roster_payload or {}).get("agents", [])
    enabled = [item for item in agents if str(item.get("enabled")) == "true" and item.get("roles")]
    if not enabled:
        return None
    clis = sorted({str(item.get("cli", "") or "unknown") for item in enabled})
    evidence = [f"distinct_clis={len(clis)}", f"clis={','.join(clis)}"]
    if len(clis) >= 2:
        return make_check(
            "roster.cli_diversity",
            "PASS",
            required=False,
            summary="Enabled role-mapped workers span multiple CLI products",
            evidence=evidence,
        )
    return make_check(
        "roster.cli_diversity",
        "WARN",
        required=False,
        summary="All enabled role-mapped workers run the same CLI product",
        evidence=evidence,
        warning=[
            f"single-CLI roster ({clis[0]}): a credit or availability outage on that product "
            "strands every task; run /luucycle roster add to enable a second CLI"
        ],
    )


def overall_status(checks: list[dict[str, Any]]) -> str:
    required = [check for check in checks if check["required"]]
    if any(check["status"] == "FAIL" for check in required):
        return "BLOCKED"
    if any(check["status"] == "UNKNOWN" for check in required):
        return "UNKNOWN"
    if any(check["status"] in {"WARN", "FAIL", "UNKNOWN"} for check in checks):
        return "DEGRADED"
    return "READY"


def run_diagnostic(
    repo_root: Path,
    scope: str,
    required_skill: list[str],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    repo_root = repo_root.resolve()
    skill_root = Path(__file__).resolve().parents[1]
    checks: list[dict[str, Any]] = []

    orca_checks, _orca_argv = check_orca(env)
    checks.extend(orca_checks)
    skill_checks, selected_skills = check_skills(repo_root, skill_root, scope, required_skill, env)
    checks.extend(skill_checks)
    checks.extend(check_project_setup(repo_root, scope, selected_skills, env))
    roster_payload, roster_check = check_roster(repo_root, skill_root, env)
    checks.append(roster_check)
    checks.extend(check_enabled_clis(repo_root, roster_payload, env))
    diversity_check = check_cli_diversity(roster_payload)
    if diversity_check is not None:
        checks.append(diversity_check)

    status = overall_status(checks)
    errors = sorted({message for check in checks for message in check["error"]})
    warnings = sorted({message for check in checks for message in check["warning"]})
    return {
        "status": status,
        "scope": scope,
        "repo_root": str(repo_root),
        "skill_root": str(skill_root),
        "required_skill": sorted(required_skill),
        "check": sorted(checks, key=lambda item: item["check"]),
        "error": errors,
        "warning": warnings,
    }


def write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def write_skill(path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\n# {name}\n")


def write_roster(repo_root: Path, command: str, *, model_flag: str = "--model {model}", second_cli: str | None = None) -> None:
    roster_dir = repo_root / ".agents" / "luucycle"
    roster_dir.mkdir(parents=True, exist_ok=True)
    entries = [("fake:gpt-test", "Fake")]
    if second_cli:
        entries.append(("fake2:gpt-test", second_cli))
    roster = "# luucycle Roster\n\n## Agents\n\n"
    roster += "\n\n".join(
        f"""### {agent_id}

- CLI: `{cli}`
- Command: `{command}`
- Invocation: `exec`
- Model: `gpt-test`
- Model Flag: `{model_flag}`
- Bypass Flag: `--bypass`
- Permission Profile: `test bypass`
- Cost: `low`
- Enabled: `true`
- Verified: `2026-08-25; self-test`"""
        for agent_id, cli in entries
    )
    roster += "\n"
    eligible_cell = "<br>".join(f"`{agent_id}`" for agent_id, _ in entries)
    roles = "\n".join(
        f"| `{role}` | work | context | output | {eligible_cell} |"
        for role in ("verifier", "builder", "architect", "researcher", "scaffolder")
    )
    (roster_dir / "ROSTER.md").write_text(roster)
    (roster_dir / "ROLES.md").write_text(
        "# luucycle Roles\n\n"
        "| Role | When | Context to inject | Output format | Eligible agents (first = best) |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"{roles}\n"
    )
    (roster_dir / "WARNINGS.md").write_text("# luucycle WARNINGS\n")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bin_dir = root / "bin"
        repo = root / "repo"
        bin_dir.mkdir()
        repo.mkdir()
        write_skill(repo / "skills" / "orchestration", "orchestration")

        fake_orca = bin_dir / "fake-orca"
        write_executable(
            fake_orca,
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import sys
                if sys.argv[1:] == ["status", "--json"]:
                    print(json.dumps({"ok": True, "result": {"runtime": {"state": "ready", "reachable": True}}}))
                elif sys.argv[1:] == ["skills", "get", "orchestration"]:
                    print("# Orca orchestration guide")
                else:
                    print("unexpected", sys.argv[1:], file=sys.stderr)
                    raise SystemExit(2)
                """
            ),
        )
        fake_cli = bin_dir / "fake-worker"
        write_executable(
            fake_cli,
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import sys
                if sys.argv[-1:] == ["--help"]:
                    print("Usage: fake-worker exec --model MODEL --bypass")
                else:
                    print("help only", file=sys.stderr)
                    raise SystemExit(2)
                """
            ),
        )
        sleeper = bin_dir / "sleep-worker"
        write_executable(
            sleeper,
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import time
                time.sleep(5)
                """
            ),
        )

        write_roster(repo, "fake-worker")
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["ORCA_CLI_COMMAND"] = str(fake_orca)
        env["HOME"] = str(root / "home")
        env.pop("CODEX_HOME", None)

        result = run_diagnostic(repo, "core", [], env)
        assert result["status"] == "DEGRADED", json.dumps(result, indent=2)
        assert all(all(key in record for key in CHECK_KEYS) for record in result["check"])
        assert any(record["check"] == "orca.guide" and record["status"] == "PASS" for record in result["check"])
        assert any(record["check"] == "cli.fake:gpt-test" and record["status"] == "PASS" for record in result["check"])
        assert any(record["check"] == "roster.cli_diversity" and record["status"] == "WARN" for record in result["check"])
        assert any("single-CLI roster" in message for message in result["warning"]), result["warning"]

        missing = run_diagnostic(repo, "task", ["missing-skill"], env)
        assert missing["status"] == "BLOCKED", json.dumps(missing, indent=2)
        assert any(record["check"] == "skill.missing-skill" and record["status"] == "FAIL" for record in missing["check"])

        complete = run_diagnostic(repo, "complete", [], env)
        assert complete["status"] == "DEGRADED", json.dumps(complete, indent=2)
        assert any(record["check"].startswith("skill.") and record["status"] == "WARN" for record in complete["check"])

        timed = run_bounded([str(sleeper)], env, timeout=0.1)
        assert timed["timed_out"] is True, timed
        assert option_from_template("none - documented") == (None, "none")
        assert option_from_template("none") == (None, "none_without_reason")

        write_roster(repo, "fake-worker", second_cli="Fake Two")
        two_cli = run_diagnostic(repo, "core", [], env)
        assert two_cli["status"] == "READY", json.dumps(two_cli, indent=2)
        assert any(record["check"] == "roster.cli_diversity" and record["status"] == "PASS" for record in two_cli["check"])

        write_roster(repo, "fake-worker", model_flag="--absent {model}")
        bad_flag = run_diagnostic(repo, "core", [], env)
        assert bad_flag["status"] == "BLOCKED", json.dumps(bad_flag, indent=2)
        assert any("--absent" in message for record in bad_flag["check"] for message in record["error"])
    print("doctor self-test: PASS")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only luucycle diagnostics.")
    parser.add_argument("repo_root", nargs="?", help="Repository root to inspect.")
    parser.add_argument("--scope", choices=SCOPES, help="Diagnostic scope.")
    parser.add_argument("--required-skill", action="append", default=[], metavar="NAME")
    parser.add_argument("--json", action="store_true", help="Emit stable JSON diagnostics.")
    parser.add_argument("--self-test", action="store_true", help="Run tempfile-based self-tests.")
    args = parser.parse_args(argv)
    if args.self_test:
        return args
    if not args.repo_root:
        parser.error("repo_root is required unless --self-test is used")
    if not args.scope:
        parser.error("--scope is required unless --self-test is used")
    if not args.json:
        parser.error("--json is required for diagnostics")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        self_test()
        return 0
    result = run_diagnostic(Path(args.repo_root), args.scope, args.required_skill)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["status"] == "BLOCKED":
        return 1
    if result["status"] == "UNKNOWN":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
