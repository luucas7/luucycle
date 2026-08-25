# luucycle roster format

Read this file when creating or validating `.agents/luucycle/`. Agent IDs are stable references shared by the roster and roles files.

## ROSTER.md

Create `.agents/luucycle/ROSTER.md` with this header:

```md
# luucycle Roster

Current worker facts. Each Agent ID appears once.

## Agents
```

Add or update agents in this exact form:

```md
### <agent-id>

- CLI: `<product name>`
- Command: `<executable>`
- Invocation: `<non-model subcommand and argument template>`
- Model: `<exact model ID or auto-default>`
- Model Flag: `<flag template or none - reason>`
- Bypass Flag: `<flag template or none - reason>`
- Permission Profile: `<what the bypass permits>`
- Cost: `low|medium|high`
- Enabled: `true|false`
- Verified: `<YYYY-MM-DD; evidence source>`
```

The heading is the Agent ID. Use `<cli>:<model>` when possible and update the existing entry when its facts change.

## ROLES.md

Create `.agents/luucycle/ROLES.md` with this exact table. Eligible agents are ordered Agent IDs separated by `<br>`; the first enabled entry wins.

```md
# luucycle Roles

| Role | When | Context to inject | Output format | Eligible agents (first = best) |
| --- | --- | --- | --- | --- |
| `verifier` | double-checks, review passes, gate passes | diff + checklist + routed skill verdict rules | `path:line: severity: problem. fix.` | |
| `builder` | feature work, TDD, mid-complexity implementation | task + routed skill + target files + conventions | files touched, change, verification, risk | |
| `architect` | systemic refactors and deep debugging | full context + routed skill + constraints + stakes | approach, files, risks, effort | |
| `researcher` | full-codebase or primary-source research | sources + routed skill + question | synthesis with precise sources | |
| `scaffolder` | boilerplate, scripts, docs, easy tasks | raw task + routed skill | delivered files + verification | |
```

Every enabled Agent ID appears in at least one role. Every role lists at least one enabled Agent ID before it can be selected.

## Script Contracts

`scripts/roster.py` owns mechanical validation, listing, selection, planning, and applying:

```bash
python3 "<skill-root>/scripts/roster.py" check --json "<repo-root>"
python3 "<skill-root>/scripts/roster.py" list --json "<repo-root>"
python3 "<skill-root>/scripts/roster.py" select --json [--max-cost low|medium|high] [--avoid <agent-id>]... [--avoid-cli <cli>]... <role> "<repo-root>"
python3 "<skill-root>/scripts/roster.py" plan --json <proposal.json> "<repo-root>"
python3 "<skill-root>/scripts/roster.py" apply --json <plan.json> "<repo-root>"
```

`check` returns `status`, `agents`, `enabled_agents`, `roles`, `errors`, and `warnings` when files exist; missing files return `status`, `errors`, and `warnings`.

`list` returns `status`, `agents`, `errors`, and `warnings`. Each agent has `agent_id`, `cli`, `model`, `cost`, `enabled`, `roles`, and `verified`.

`select` returns `status`, `role`, `max_cost`, `primary`, `fallback`, `contracts`, `skipped`, `errors`, and `warnings`. The primary is the first eligible agent not named by `--avoid` and not running a CLI named by `--avoid-cli`; `--avoid` excludes one Agent ID from selection for this role and `--avoid-cli` excludes every agent running a given CLI product (repeat either flag to exclude several). The fallback is the first eligible agent after the primary with the same permission profile, a different CLI product, and no `--avoid` naming. Each contract has `agent_id`, `cli`, `command`, `invocation`, `model`, `model_flag`, `resolved_model_flag`, `bypass_flag`, `resolved_bypass_flag`, `permission_profile`, `cost`, `enabled`, `verified`, and `command_preview`. `skipped` records the reason for each eligible agent passed over (`avoided`, `cli_avoided`, `same_cli_as_primary`, `permission_profile_mismatch`, `already_assigned`) alongside the existing `unknown`, `disabled`, and `cost>...` entries. `warnings` additionally reports a single-CLI role, a missing different-CLI fallback, and forced primary reuse, each naming the smallest repair command (`/luucycle roster add`).

`plan` accepts:

```json
{"version":1,"roster":[{"agent_id":"<id>","cli":"<product>","command":"<executable>","invocation":"<args>","model":"<model>","model_flag":"<template or none - reason>","bypass_flag":"<template or none - reason>","permission_profile":"<profile>","cost":"low|medium|high","enabled":"true|false","verified":"<YYYY-MM-DD; evidence>"}],"roles":{"builder":["<agent-id>"]}}
```

`plan` returns `status`, `plan_version`, `repo_root`, `proposal`, `base_hashes`, `expected_hashes`, `previews`, `changes`, `validation`, `errors`, and `warnings`. `apply` accepts that full plan, verifies the base hashes, writes only `ROSTER.md` and `ROLES.md`, and returns `status`, `written`, `expected_hashes`, `validation`, `errors`, and `warnings`.

## WARNINGS.md

Create `.agents/luucycle/WARNINGS.md` with:

```md
# luucycle WARNINGS

Observed CLI/model failure modes. Each entry records symptom, cause, and the behavior that avoids it, or points to the owning IMPLEMENT.md step.

_None yet._
```
