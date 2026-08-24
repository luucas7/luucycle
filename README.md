# luucycle

Orchestrator agent skill: decomposes a request into tasks, routes each task to the right skill, and dispatches workers on the best model from the roster. Builds on the [skills CLI](https://github.com/vercel-labs/skills) ecosystem (OpenCode, Claude Code, Codex, Cursor, ...).

## What it does

luucycle sits **on top of** the skills already installed in your repo - it never reimplements their work. Bare `/luucycle` audits the core setup and the dependencies relevant to your intended route, then recommends what to do without dispatching anything. Implementation starts only with the explicit `/luucycle implement <ref|request>` command, then follows the same process every time:

1. **Decompose** the request into tasks.
2. **Route** each task to the skill that owns that kind of work (spec → `to-spec`, code → `implement`, UI → `impeccable`, ... see `ROUTING.md`).
3. **Assign** each task a model from the roster (`.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` at the repo root) - the worker agents you approved.
4. **Confirm** the task/skill/model plan with you before any work starts.
5. **Dispatch** one worker per task through Orca's orchestration layer.
6. **Gate** UI work through impeccable, the Gatekeeper.
7. **Report** every worker's final status and run a retrospective on the orchestration itself.

Same process on every implementation run (RULES rule 7): predictable orchestration, no improvisation.

## Requirements

- **Orca runtime** (hard requirement) - luucycle coordinates workers through Orca's orchestration layer. Install the [Orca IDE](https://www.onorca.dev), enable orchestration, then follow the installed `orchestration` skill to resolve the executable and verify `status --json`. On Linux outside an Orca-managed terminal, never run bare `orca` (GNOME screen reader conflict).
- **The skills it orchestrates**: the [matt-pocock engineering set](https://github.com/mattpocock/skills) (grilling, spec, tickets, implement, ...), [impeccable](https://github.com/pbakaus/impeccable) (UI gate), and Orca's `orchestration` + `orca-cli` skills. The `init` branch installs all of this for you.
- **A configured issue tracker for feature alignment or tracker-backed work** - `/setup-matt-pocock-skills` records where issues live in `docs/agents/issue-tracker.md`.

Run `/luucycle doctor` for the complete non-mutating readiness report. Bare `/luucycle` runs only the checks relevant to its recommendation.

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
| `/luucycle` | Audit setup, then recommend a copyable next command; never dispatch | `/luucycle` |
| `/luucycle ask-lucas` | Explicitly open the same audit-backed advisory router | `/luucycle ask-lucas` |
| `/luucycle doctor` | Check Orca, skills, tracker/design setup, roster, roles, and every accessible CLI without changing state | `/luucycle doctor` |
| `/luucycle implement <ref|request>` | Decompose → route → assign a model → plan approval → dispatch → UI gate → retrospective | `/luucycle implement #42` |
| `/luucycle start` | Kick off a fresh feature: verify prerequisites, then script `/grill-with-docs` → `/to-spec` → `/to-tickets` in one session, and hand over to `implement` | `/luucycle start` |
| `/luucycle init` | Install the skill library (mattpocock, impeccable, orca skills), run `/impeccable init`, bootstrap the roster | `/luucycle init` |
| `/luucycle add-cli` | Grow the roster with a new CLI or model: discover, propose, confirm, append to `.agents/luucycle/ROSTER.md` + map into `.agents/luucycle/ROLES.md` (repo root) | `/luucycle add-cli` |

Invocations such as `/luucycle build the onboarding flow` do not implement. Ask Lucas recommends the explicit equivalent: `/luucycle implement "build the onboarding flow"`.

## The flow at a glance

The `start` branch is the entry point for new work that still needs alignment. It lines up the alignment skills, then the explicit `implement` branch takes over:

```
/luucycle start                 new feature kick-off
   └─ /grill-with-docs          align the design, build shared vocabulary (same session)
      └─ /to-spec               spec → tracker; becomes the parent issue (same session)
         └─ /to-tickets         tracer-bullet tickets with blocking edges (same session)
            └─ /luucycle implement <ref>  new session - dispatch, gate, retrospective
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
- `ASK-LUCAS.md` - safe default that audits readiness and recommends the next command without dispatching
- `DOCTOR.md` - non-mutating installation and roster health check
- `DOCTOR-REPORT.md` - full report format loaded only by explicit Doctor
- `IMPLEMENT.md` - explicit implementation orchestration flow
- `START.md` - new-feature kick-off branch (grill → spec → tickets → `implement`)
- `INIT.md` - bootstrap branch
- `ADD-CLI.md` - roster growth branch
- `ROUTING.md` - which skill owns which kind of work
- `ROSTER-FORMAT.md` - canonical roster snapshots, roles table, and warnings skeleton
- `scripts/check_roster.py` - deterministic roster/snapshot/role validation used by Doctor
- `agents/openai.yaml` - Codex UI metadata and explicit-only invocation policy
- `.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` / `.agents/luucycle/WARNINGS.md` - **user data** at the repo root, never inside the skill (`npx skills update` wipes `.agents/skills/luucycle/`); seeded by `add-cli`
- `RULES.md` - shared authorization and execution guardrails
