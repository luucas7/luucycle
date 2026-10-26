# luucycle doctor

Non-mutating health check for the current luucycle installation and roster. `scripts/doctor.py` is the source of truth for diagnostic mechanics; this branch decides which scope to run and how to report it.

Doctor is read-only: inspect files, run free diagnostic commands, and report evidence plus repair commands. Installation, updates, service startup, configuration or roster edits, worker dispatch, and model prompts belong to an explicitly authorized mutating branch.

## Scope

The free launch preflight checks alias/model forwarding without launching or billing a model.

- **Core:** Orca runtime, the `orchestration` skill, roster validity, and at least one enabled role-mapped CLI. Free Orca launch coverage is advisory here; Task blocks each Agent ID explicitly selected without its own proven alias/model preflight.
- **Task:** Core plus the routed skills passed with `--required-skill NAME`; project setup checks follow from those skills. Selected stable roster IDs passed with `--selected-agent ID` must each pass their own CLI and Orca alias/model preflight.
- **Complete:** Core plus every skill named in `ROUTING.md`, branch-only setup skills, project setup, and every enabled role-mapped CLI. Missing optional coverage is a warning, not a blocker for unrelated tasks.

[Help](HELP.md) uses Core or Task. `/luucycle implement <ref|request>` uses Task. Explicit `/luucycle doctor` uses Complete.

## Script Calls

Resolve `<skill-root>` as the directory containing this file and `<repo-root>` as the current repository root. Diagnostic calls must include `repo_root`, `--scope`, and `--json`; `--self-test` is the only no-repo mode.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/doctor.py" "<repo-root>" --scope core --json
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/doctor.py" "<repo-root>" --scope task --required-skill <skill> --selected-agent '<roster-agent-id>' --json
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/doctor.py" "<repo-root>" --scope complete --json
```

For Task scope, repeat `--required-skill` for every routed skill selected from [ROUTING.md](ROUTING.md). Include `impeccable` when the task touches UI.

Before dispatch, repeat `--selected-agent` for that task's actual primary and
fallback roster IDs, omitting an absent fallback. This is not Orca's `--agent`
alias: the separate explicit `Orca Agent` field owns that value. A missing or
unproven selected alias blocks this task; unrelated healthy roster entries remain
usable. See [ROSTER-FORMAT.md](ROSTER-FORMAT.md#free-per-agent-launch-preflight)
for model-forwarding limits. A help-only PASS is not a successful launch or proof
of credentials, credits, execution-host enablement or model availability; compare
the actual requested/effective launch receipt after an authorized dispatch.

The JSON contract is stable:

- top-level keys: `status`, `scope`, `repo_root`, `skill_root`, `required_skill`, `selected_agent`, `check`, `error`, `warning`;
- `status`: `READY`, `DEGRADED`, `BLOCKED`, or `UNKNOWN`;
- each `check` record has `check`, `status`, `required`, `summary`, `evidence`, `error`, and `warning`;
- exit code is `1` for `BLOCKED`, `2` for `UNKNOWN`, and `0` otherwise.

## Output

- **Implicit Core/Task (Help or `/luucycle implement`):** keep evidence internal. Help uses it in the recommendation; implementation continues silently on `READY` and otherwise reports only readiness-affecting gaps.
- **Explicit `/luucycle doctor`:** after the checks, read [DOCTOR-REPORT.md](DOCTOR-REPORT.md) and produce the full report.

For the requested scope, use `READY` when every required check passes, `DEGRADED` for optional or unrelated gaps, `BLOCKED` for a failed required check, and `UNKNOWN` when a required check cannot be resolved.

Report script errors and warnings without reinterpreting them. Doctor is read-only: the script may inspect files, resolve commands, run Orca status/guide checks, run roster validation, and run free CLI help only. It never installs, updates, starts services, edits files, dispatches workers, or calls a model.

## Completion criterion

Every scoped check has evidence or an explicit `UNKNOWN`, the requested readiness state is computed, and no state was changed. Explicit Doctor also satisfies `DOCTOR-REPORT.md`'s completion criterion.
