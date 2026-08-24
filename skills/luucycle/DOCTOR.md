# luucycle doctor

Non-mutating health check for the current luucycle installation and roster. Explicit `/luucycle doctor` runs every check; Ask Lucas and implementation use the scoped variants described below.

Doctor is read-only: inspect files, run free diagnostic commands, and report evidence plus repair commands. Installation, updates, service startup, configuration or roster edits, worker dispatch, and model prompts belong to an explicitly authorized mutating branch.

## Scope

- **Core:** resolved Orca binary/runtime, `orchestration`, roster files, and at least one accessible role-mapped worker.
- **Task:** Core plus only the routed skills, roles, project setup, and CLIs needed by the stated request.
- **Complete:** every routed/alignment skill, every role, project setup, and every accessible CLI. Missing optional coverage is a warning, not a blocker for unrelated tasks.

Ask Lucas uses Core or Task. `/luucycle implement <ref|request>` uses Task. Explicit `/luucycle doctor` uses Complete.

## Output modes

- **Explicit `/luucycle doctor`:** the only user-facing mode that prints the full report below, including the checks table and readiness statuses.
- **Implicit Task (`/luucycle implement`):** keep audit evidence and readiness internal. When the Task scope passes, emit no Doctor output and continue to planning. If any check is `FAIL`, announce only each failed check and what failed, then stop; do not print passing rows, the full checks table, or readiness tables.

## Checks

1. **Orca runtime.** Read the installed `orchestration` skill, resolve its executable once, and reuse it. When that skill is missing, use the safe bootstrap order from `INIT.md`; on Linux outside a managed terminal, never run bare `orca`. Verify the selected executable resolves, its version command succeeds, `status --json` reports runtime state, and `skills get orchestration` returns the version-matched guide.

2. **Skill library.** Inspect the agent's exposed skill catalog and installed local/global skill directories. Use an already-installed `skills` executable when available; do not invoke `npx`, download packages, or update caches during diagnostics. Task scope verifies only required capabilities. Complete scope inventories `ROUTING.md`, `START.md`, and `INIT.md`; missing unused capabilities are `WARN`. An either/or entry passes when one alternative is available.

3. **Project setup.** Check `docs/agents/issue-tracker.md` only for feature alignment or tracker-backed work. Check impeccable's documented design-context paths only for UI work. Complete scope reports both.

4. **Roster files.** Resolve `<skill-root>` as the directory containing this `DOCTOR.md`, then run `python3 "<skill-root>/scripts/check_roster.py" "<repo-root>" --json`. The script validates `.agents/luucycle/` against [ROSTER-FORMAT.md](ROSTER-FORMAT.md), selects the latest snapshot per Agent ID, and checks canonical role coverage. Report its exact errors and warnings without reinterpreting them.

5. **Accessible CLIs.** Task scope checks only eligible agents for the requested roles. Complete scope checks every `Accessible: true` current snapshot:
   - resolve its declared command with `command -v`;
   - run its free version and relevant help commands;
   - verify the declared Model Flag and Bypass Flag appear in that CLI's help, unless the roster explicitly records `none` with a reason;
   - never run a model prompt to test a flag. A missing binary or contradicted flag is `FAIL` for a selected worker and `WARN` when unrelated to the current task.

## Explicit report

For explicit `/luucycle doctor`, present one compact table:

| Component | Status | Evidence | Next action |
| --- | --- | --- | --- |

Use `PASS`, `WARN`, `FAIL`, or `UNKNOWN`. Evidence must name the observed file, binary, skill, role, or error. Do not claim a check passed when it was not run; use `UNKNOWN` and explain why.

After the table, report readiness separately:

- **Implementation:** runtime + orchestration + skills and roles required by the stated task; without a task, use the core implementation path.
- **Feature alignment:** `grill-with-docs`, `to-spec`, `to-tickets`, and a configured tracker.
- **UI work:** UI implementation readiness + impeccable + its initialized design context.

Mark each scope `READY`, `DEGRADED`, `BLOCKED`, or `UNKNOWN`. A dependency required by that scope is blocking; an unrelated missing capability only degrades Complete coverage. State which tasks remain runnable.

For each `WARN`, `FAIL`, or `UNKNOWN`, give the smallest copyable repair command:

- missing runtime or skills → `/luucycle init` (or tell the user to start Orca when it is installed but stopped);
- missing or stale roster/CLI entries → `/luucycle add-cli`;
- missing tracker configuration → `/setup-matt-pocock-skills`;
- missing impeccable design context → `/impeccable init`.

When everything is ready, say so explicitly and do not propose setup work.

## Completion criterion

Every check is represented by evidence or an explicit `UNKNOWN`; the three readiness scopes are reported with one of the defined states; every issue has a concrete next action; and no state was changed.
