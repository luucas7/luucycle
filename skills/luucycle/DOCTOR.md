# luucycle doctor

Non-mutating health check for the current luucycle installation and roster. Explicit `/luucycle doctor` runs every check; Ask Lucas and implementation use the scoped variants described below.

Doctor is read-only: inspect files, run free diagnostic commands, and report evidence plus repair commands. Installation, updates, service startup, configuration or roster edits, worker dispatch, and model prompts belong to an explicitly authorized mutating branch.

## Scope

- **Core:** resolved Orca binary/runtime, `orchestration`, roster files, and at least one accessible role-mapped worker.
- **Task:** Core plus only the routed skills, roles, project setup, and CLIs needed by the stated request.
- **Complete:** every routed/alignment skill, every role, project setup, and every accessible CLI. Missing optional coverage is a warning, not a blocker for unrelated tasks.

Ask Lucas uses Core or Task. `/luucycle implement <ref|request>` uses Task. Explicit `/luucycle doctor` uses Complete.

## Output

- **Implicit Core/Task (Ask Lucas or `/luucycle implement`):** keep evidence internal. Ask Lucas uses it in the recommendation; implementation continues silently on `READY` and otherwise reports only readiness-affecting gaps.
- **Explicit `/luucycle doctor`:** after the checks, read [DOCTOR-REPORT.md](DOCTOR-REPORT.md) and produce the full report.

For the requested scope, use `READY` when every required check passes, `DEGRADED` for optional or unrelated gaps, `BLOCKED` for a failed required check, and `UNKNOWN` when a required check cannot be resolved.

## Checks

1. **Orca runtime.** Read the installed `orchestration` skill, resolve its executable once, and reuse it. When that skill is missing, use the safe bootstrap order from `INIT.md`; on Linux outside a managed terminal, never run bare `orca`. Verify the selected executable resolves, `status --json` reports runtime state, and `skills get orchestration` returns the version-matched guide.

2. **Skill library.** Inspect the agent's exposed skill catalog and installed local/global skill directories. Use an already-installed `skills` executable when available; do not invoke `npx`, download packages, or update caches during diagnostics. Task scope verifies only required capabilities. Complete scope inventories `ROUTING.md`, `PREPARE.md`, `ROSTER-ADD.md`, `ROSTER-LIST.md`, and `INIT.md`; missing unused capabilities are `WARN`. An either/or entry passes when one alternative is available.

3. **Project setup.** Check `docs/agents/issue-tracker.md` only for feature alignment or tracker-backed work. Check impeccable's documented design-context paths only for UI work. Complete scope reports both.

4. **Roster files.** Resolve `<skill-root>` as the directory containing this `DOCTOR.md`, then run `python3 "<skill-root>/scripts/check_roster.py" "<repo-root>" --json`. The script validates `.agents/luucycle/` against [ROSTER-FORMAT.md](ROSTER-FORMAT.md), selects the latest snapshot per Agent ID, and checks canonical role coverage. Report its exact errors and warnings without reinterpreting them.

5. **Accessible CLIs.** Task scope checks only eligible agents for the requested roles. Complete scope checks every `Accessible: true` current snapshot:
   - resolve its declared command with `command -v`;
   - run the relevant free help commands;
   - verify the declared Model Flag and Bypass Flag appear in that CLI's help, unless the roster explicitly records `none` with a reason;
   - never run a model prompt to test a flag. A missing binary or contradicted flag is `FAIL` for a selected worker and `WARN` when unrelated to the current task.

## Completion criterion

Every scoped check has evidence or an explicit `UNKNOWN`, the requested readiness state is computed, and no state was changed. Explicit Doctor also satisfies `DOCTOR-REPORT.md`'s completion criterion.
