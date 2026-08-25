# luucycle

Orchestrator agent skill: decomposes a request into tasks, routes each task to the right skill, and dispatches workers on the best model from the roster. Builds on the [skills CLI](https://github.com/vercel-labs/skills) ecosystem (OpenCode, Claude Code, Codex, Cursor, ...).

## What it does

luucycle sits **on top of** the skills already installed in your repo - it never reimplements their work. Bare `/luucycle` shows the available commands and recommends `/luucycle init`. Implementation starts only with the explicit `/luucycle implement <ref|request>` command, then follows the same process every time:

1. **Decompose** the request into tasks.
2. **Route** each task to the skill that owns that kind of work (spec → `to-spec`, code → `implement`, UI → `impeccable`, ... see `ROUTING.md`).
3. **Assign** each task a model from the roster (`.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` at the repo root) - the worker agents you approved.
4. **Confirm** each task's routed skill, primary agent, and fallback agent with you before any work starts.
5. **Dispatch** one worker per task through Orca's orchestration layer.
6. **Gate** UI work through impeccable, the Gatekeeper.
7. **Report** every worker's final status and run a retrospective on the orchestration itself.

Same process on every implementation run (RULES rule 7): predictable orchestration, no improvisation.

## Requirements

- **Orca runtime** (hard requirement) - luucycle coordinates workers through Orca's orchestration layer. Install the [Orca IDE](https://www.onorca.dev), enable orchestration, then follow the installed `orchestration` skill to resolve the executable and verify `status --json`. On Linux outside an Orca-managed terminal, never run bare `orca` (GNOME screen reader conflict).
- **The skills it orchestrates**: the [matt-pocock engineering set](https://github.com/mattpocock/skills) (grilling, spec, tickets, implement, ...), [impeccable](https://github.com/pbakaus/impeccable) (UI gate), and Orca's `orchestration` + `orca-cli` skills. The `init` branch installs all of this for you.
- **A configured issue tracker for feature alignment or tracker-backed work** - `/setup-matt-pocock-skills` records where issues live in `docs/agents/issue-tracker.md`.

Run `/luucycle doctor` for the complete non-mutating readiness report. Use `/luucycle ask-lucas` for questions about luucycle's commands, skills, setup, or workflow. Application and product questions start with `/luucycle prepare`.

Mechanical diagnostics and roster operations live in `skills/luucycle/scripts/doctor.py` and `skills/luucycle/scripts/roster.py`; the Markdown branches decide scope, routing, and approvals.

## Install

```bash
npx skills add luucas7/luucycle
```

Make sure to initialize the skill environnement : `/luucycle init`.

## Commands (branches)

luucycle has a safe default and explicit branches. The command itself selects the branch; request wording never silently authorizes implementation.

Examples use `/luucycle`. In Codex, `$luucycle` is equivalent (`$luucycle implement #42`, and so on).

| Command | What it does | Example |
| --- | --- | --- |
| `/luucycle` | Show the available commands and recommend initialization | `/luucycle` |
| `/luucycle ask-lucas` | Answer questions about luucycle itself and recommend a copyable luucycle command | `/luucycle ask-lucas How does implementation approval work?` |
| `/luucycle doctor` | Check Orca, skills, tracker/design setup, roster, roles, and every enabled CLI without changing state | `/luucycle doctor` |
| `/luucycle implement <ref|request>` | Decompose → route → assign a model → plan approval → dispatch → UI gate → retrospective | `/luucycle implement #42` |
| `/luucycle prepare` | Start `/grill-with-docs` for an app or product topic, then decide whether to stop, implement directly, or create a spec and tickets | `/luucycle prepare` |
| `/luucycle init` | Install the skill library (mattpocock, impeccable, orca skills), run `/impeccable init`, bootstrap the roster | `/luucycle init` |
| `/luucycle roster list` | List each agent with its CLI, model, cost, enabled state, roles, and verification date without probing it | `/luucycle roster list` |
| `/luucycle roster add [cli]` | Discover every installed worker CLI, or inspect one named CLI; propose its best models, confirm, then update the roster and roles | `/luucycle roster add` |

Invocations such as `/luucycle should ranking be calculated client-side or server-side?` do not analyze or implement the application. Ask Lucas redirects them to `/luucycle prepare`, where `grill-with-docs` aligns the decision first.

## The flow at a glance

The `prepare` branch is the entry point for application and product questions. It starts the alignment session itself; the aligned result determines the next branch:

```
/luucycle prepare
   └─ /grill-with-docs          launched immediately in the same conversation
      ├─ no change              stop with the recorded decision
      ├─ bounded change         /luucycle implement <request> in a new conversation
      └─ durable planning       /to-spec → /to-tickets in the same conversation
                                └─ /luucycle implement <parent ref> in a new conversation
```

The reference passed to `/luucycle implement` depends on the configured tracker: a GitHub issue number (`#42`), a local spec path (`.scratch/<feature-slug>/spec.md`), or the tracker's native identifier.

## Development

Repo-first workflow: this repository is the source of truth.

1. Clone `luucas7/luucycle`, edit the skill under `skills/luucycle/`.
2. Commit and push.
3. Consumers refresh their installed copy: `npx skills update luucycle`.

Installed copies must come from `npx skills add luucas7/luucycle` (symlink installs update automatically; copy installs need the `update` command).

## Structure

- `SKILL.md` - command router + implementation authorization boundary
- `ASK-LUCAS.md` - advisor for luucycle's own workflow; application and product questions redirect to `prepare`
- `DOCTOR.md` - non-mutating installation and roster health check
- `DOCTOR-REPORT.md` - full report format loaded only by explicit Doctor
- `IMPLEMENT.md` - explicit implementation orchestration flow
- `PREPARE.md` - app/product alignment branch (`grill-with-docs` → stop, direct implementation, or spec/tickets)
- `INIT.md` - bootstrap branch
- `ROSTER-LIST.md` - current roster view
- `ROSTER-ADD.md` - roster growth branch
- `ROUTING.md` - which skill owns which kind of work
- `ROSTER-FORMAT.md` - canonical roster entries, roles table, and warnings skeleton
- `scripts/doctor.py` - read-only readiness diagnostics for Doctor, Ask Lucas, init, and implement
- `scripts/roster.py` - roster validation, listing, selection, planned writes, and hash-guarded apply
- `scripts/check_roster.py` - compatibility entrypoint for roster validation
- `agents/openai.yaml` - Codex UI metadata and explicit-only invocation policy
- `.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` / `.agents/luucycle/WARNINGS.md` - **user data** at the repo root, never inside the skill (`npx skills update` wipes `.agents/skills/luucycle/`); seeded by `roster add`
- `RULES.md` - shared authorization and execution guardrails
