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
- Orca Agent: `<exact Orca launch alias>`
- Command: `<executable>`
- Invocation: `<non-model subcommand and argument template>`
- Model: `<exact model ID or auto-default>`
- Model Flag: `<flag template or none - reason>`
- Bypass Flag: `<flag template or none - reason>`
- Cost: `low|medium|high`
- Enabled: `true|false`
- Verified: `<YYYY-MM-DD; evidence source>`
```

The heading is the stable Agent ID used by role references, selection, task records,
and reports. Use `<cli>:<model>` when possible and update the existing entry when
its facts change. It is an identifier, not an Orca launch argument.

`Orca Agent` is optional for legacy readability. When present, put it immediately
after `CLI`. Record the exact alias documented by the selected executable's
version-matched guide/help. For example, Agent ID `agy:gemini-3.1-pro` may explicitly
record `Orca Agent: antigravity`. Pass `antigravity`, never the stable ID or its
`agy` prefix, as Orca's `--agent`. `CLI` is a human-facing product label and
`Command` is the worker executable; neither establishes the launch alias.
Missing, unknown, or malformed aliases remain readable but cannot pass launch
preflight. Add the field only through an approved roster update after discovery;
diagnostics never infer or repair it.

## ROLES.md

Create `.agents/luucycle/ROLES.md` with this exact table. Write every plausible assignment as `<agent-id>@<fit>`, separated by `<br>`. Fit is a decimal greater than `0` and at most `1`, with at most two decimal places; it ranks aptitude for that role and says nothing about permissions. The selector tries the highest fit first and preserves table order for ties.

```md
# luucycle Roles

| Role | When | Context to inject | Output format | Eligible agents (`agent@fit`, highest first) |
| --- | --- | --- | --- | --- |
| `verifier` | double-checks, review passes, gate passes | diff + checklist + routed skill verdict rules | `path:line: severity: problem. fix.` | |
| `builder` | feature work, TDD, mid-complexity implementation | task + routed skill + target files + conventions | files touched, change, verification, risk | |
| `architect` | systemic refactors and deep debugging | full context + routed skill + constraints + stakes | approach, files, risks, effort | |
| `researcher` | full-codebase or primary-source research | sources + routed skill + question | synthesis with precise sources | |
| `scaffolder` | boilerplate, scripts, docs, easy tasks | raw task + routed skill | delivered files + verification | |
```

Every enabled Agent ID appears in at least one role. Every role lists at least one enabled Agent ID before it can be selected. Omit an agent from a role only when it cannot plausibly perform that role; runtime inability is handled by the approved fallback rather than predicted through permission metadata.

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

`list` returns `status`, `agents`, `errors`, and `warnings`. Each agent has `agent_id`, `orca_agent`, `cli`, `model`, `cost`, `enabled`, `roles`, `role_fit`, and `verified`. `orca_agent` is JSON `null` when the optional field is absent.

`select` returns `status`, `role`, `max_cost`, `primary`, `fallback`, `contracts`, `skipped`, `errors`, and `warnings`. It ranks eligible agents by role fit, preserving table order for ties. The primary is the highest-ranked agent not named by `--avoid` and not running a CLI named by `--avoid-cli`; `--avoid` excludes one Agent ID and `--avoid-cli` excludes one CLI product from primary selection (repeat either flag to exclude several). The fallback is the highest-ranked remaining agent on a different CLI product and not named by `--avoid`. Permission metadata is neither recorded nor compared. Each contract has `agent_id`, `orca_agent`, `cli`, `command`, `invocation`, `model`, `model_flag`, `resolved_model_flag`, `bypass_flag`, `resolved_bypass_flag`, `role_fit`, `cost`, `enabled`, `verified`, and `command_preview`. `skipped` records `avoided`, `cli_avoided`, `same_cli_as_primary`, and `already_assigned` alongside `unknown`, `disabled`, and `cost>...`. `warnings` additionally reports a single-CLI role, a missing different-CLI fallback, and forced primary reuse, each naming `/luucycle roster add` as the smallest repair command.

`plan` accepts:

```json
{"version":1,"roster":[{"agent_id":"<id>","cli":"<product>","orca_agent":"<exact Orca alias>","command":"<executable>","invocation":"<args>","model":"<model>","model_flag":"<template or none - reason>","bypass_flag":"<template or none - reason>","cost":"low|medium|high","enabled":"true|false","verified":"<YYYY-MM-DD; evidence>"}],"roles":{"builder":["<agent-id>@<fit>"]}}
```

`plan` returns `status`, `plan_version`, `repo_root`, `proposal`, `base_hashes`, `expected_hashes`, `previews`, `changes`, `validation`, `errors`, and `warnings`. `apply` accepts that full plan, verifies the base hashes, writes only `ROSTER.md` and `ROLES.md`, and returns `status`, `written`, `expected_hashes`, `validation`, `errors`, and `warnings`.

Legacy rosters remain readable: an unscored role assignment behaves as fit `1.0`, and `Permission Profile` is ignored. The next approved roster render omits that legacy field; selection never uses it.

`orca_agent` is optional in proposals too; omit it for a legacy entry instead of
inventing a value. Plan/render/apply preserve an explicit alias. Selection
contracts expose both `agent_id` and `orca_agent` (or `null`) without deriving one
from the other. `select` ranks roster facts only: its `PASS` and `command_preview`
are neither Orca launch proof nor permission to skip task preflight.

### Free per-agent launch preflight

Before dispatch, validate every selected primary/fallback by **roster Agent ID**:

```bash
python3 -B "<skill-root>/scripts/doctor.py" "<repo-root>" --scope task --json --selected-agent '<primary-agent-id>' --selected-agent '<fallback-agent-id>'
```

Omit a nonexistent fallback. `--selected-agent` is repeatable and is not Orca's
`--agent`: it names exact stable roster IDs. Every selected ID must be enabled,
role-mapped, and have passing `cli.<agent-id>` and `launch.<agent-id>` checks.
Doctor rejects `enabled_available` and `selected` as Agent IDs because those
literal names belong to diagnostic aggregates; unknown IDs cannot borrow their
passing aggregate results. Preserve the source ID in the error instead of
rewriting or inferring a replacement.
An unproven selected alias/model/CLI makes `launch.selected` fail and the task
`BLOCKED`. A broken unselected entry remains an optional per-agent diagnostic;
another healthy agent can still be used. Core uses the CLI aggregate for minimum
readiness and reports free launch coverage as advisory, so legacy rosters without
aliases remain usable for diagnosis. No aggregate combines one agent's CLI with
another agent's launch preflight to claim a ready worker.

Doctor reuses its single selected Orca executable, reads `skills get orca-cli
--json`, then `orchestration worker-start --help`. Alias and model-forwarding
evidence comes from that build's help, not ID prefixes or a hardcoded alias
catalog. Unrecognized help stays fail-closed. Worker help probes use only help
arguments; diagnostics never launch a worker, open/restart Orca, or change config.

The observed help documents opaque model forwarding for Claude, Codex, Cursor,
Antigravity, and Muse, and model-only forwarding for OMP. Doctor accepts these
only while the selected help supplies that evidence. A config-only launcher such
as ZCode cannot satisfy an exact model request. OpenCode/OpenCode2 exact-model
selection stays `UNKNOWN` here: it additionally requires an existing worktree,
verified execution-host CLI, and available model; generic `--model` help proves
none of those conditions. Explicit `Model: auto-default` means use the agent's
own default and omit the native `--model` argument; never forward the literal
`auto-default` string or silently replace an exact model with a default.

These are **free preflight checks, not successful launch proofs**. A passing
record leaves execution-host enablement, credentials, credits, actual model
availability, host-version compatibility, and the resulting launch unverified.
Read the eventual authoritative Orca launch receipt before claiming a worker
started with the requested alias/model; compare `launch.requested` with
`launch.effective`, not requested arguments alone. Remote-host readiness is not established
by this local help/CLI diagnostic.

## WARNINGS.md

Create `.agents/luucycle/WARNINGS.md` with:

```md
# luucycle WARNINGS

Observed CLI/model failure modes. Each entry records symptom, cause, and the behavior that avoids it, or points to the owning IMPLEMENT.md step.

_None yet._
```
