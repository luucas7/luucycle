# luucycle

Orchestrator agent skill: decomposes a request into tasks, routes each task to the right skill, and dispatches workers on the best model from the roster. Builds on the [skills CLI](https://github.com/vercel-labs/skills) ecosystem (OpenCode, Claude Code, Codex, Cursor, ...).

## What it does

luucycle sits **on top of** the skills already installed in your repo - it never reimplements their work. Its job is to run the process in the right order, every time:

1. **Decompose** the request into tasks.
2. **Route** each task to the skill that owns that kind of work (spec → `to-spec`, code → `implement`, UI → `impeccable`, ... see `ROUTING.md`).
3. **Assign** each task a model from the roster (`.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` at the repo root) - the worker agents you approved.
4. **Confirm** the task/skill/model plan with you before any work starts.
5. **Dispatch** one worker per task through Orca's orchestration layer.
6. **Gate** UI work through impeccable, the Gatekeeper.
7. **Report** every worker's final status and run a retrospective on the orchestration itself.

Same process on every run (RULES rule 6): predictable orchestration, no improvisation.

## Requirements

- **Orca runtime** (hard requirement) - luucycle coordinates workers through Orca's orchestration layer. Install the [Orca IDE](https://www.onorca.dev). Enable the orchestration feature in Settings, then verify with `orca status --json` - it must show a running runtime. On Linux, the binary is `orca-ide`, never bare `orca` (GNOME screen reader conflict).
- **The skills it orchestrates**: the [matt-pocock engineering set](https://github.com/mattpocock/skills) (grilling, spec, tickets, implement, ...), [impeccable](https://github.com/pbakaus/impeccable) (UI gate), and Orca's `orchestration` + `orca-cli` skills. The `init` branch installs all of this for you.
- **A configured issue tracker** - `/setup-matt-pocock-skills` records where issues live (GitHub, local markdown under `.scratch/`, ...) in `docs/agents/issue-tracker.md`. Skills like `to-spec` and `to-tickets` read it.

## Install

```bash
npx skills add luucas7/luucycle
```

Make sure to initialize the skill environnement : `/luucycle init`.

## Commands (branches)

luucycle has one main flow and several branches - alternate paths for specific situations. Say the trigger word, and the agent follows the matching file.

| Trigger | What it does | Example |
| --- | --- | --- |
| *(a normal request)* | Decompose → route → assign a model → plan approval → dispatch → UI gate → retrospective | `/luucycle` + any plain request, e.g. "build the onboarding flow" |
| `/luucycle start` - "begin" / "démarrer" / new feature | Kick off a fresh feature: verify prerequisites (Orca, skills, tracker), then script `/grill-with-docs` → `/to-spec` → `/to-tickets` in one session, and hand over to the main flow with `/luucycle <parent ref>` | `/luucycle start` |
| `/luucycle init` - "bootstrap" / fresh environment | Install the skill library (mattpocock, impeccable, orca skills), run `/impeccable init`, bootstrap the roster | `/luucycle init` |
| `/luucycle add-cli` - "add X" | Grow the roster with a new CLI or model: discover, propose, confirm, append to `.agents/luucycle/ROSTER.md` + map into `.agents/luucycle/ROLES.md` (repo root) | `/luucycle add-cli` |
| `/luucycle ask-lucas` - lost | Which branch or flow fits your situation | `/luucycle ask-lucas` |

## The flow at a glance

The `start` branch is the entry point for new work. It lines up the alignment skills, then the main flow takes over for the implementation:

```
/luucycle start                 new feature kick-off
   └─ /grill-with-docs          align the design, build shared vocabulary (same session)
      └─ /to-spec               spec → tracker; becomes the parent issue (same session)
         └─ /to-tickets         tracer-bullet tickets with blocking edges (same session)
            └─ /luucycle <ref>  new session - main flow: dispatch, gate, retrospective
```

The reference passed to `/luucycle` depends on the configured tracker: a GitHub issue number (`#42`), a local spec path (`.scratch/<feature-slug>/spec.md`), or the tracker's native identifier.

## Development

Repo-first workflow: this repository is the source of truth.

1. Clone `luucas7/luucycle`, edit the skill under `skills/luucycle/`.
2. Commit and push.
3. Consumers refresh their installed copy: `npx skills update luucycle`.

Installed copies must come from `npx skills add luucas7/luucycle` (symlink installs update automatically; copy installs need the `update` command).

## Structure

- `SKILL.md` - the orchestration flow + branch map
- `START.md` - new-feature kick-off branch (grill → spec → tickets → main flow)
- `INIT.md` - bootstrap branch
- `ADD-CLI.md` - roster growth branch
- `ASK-LUCAS.md` - router branch
- `ROUTING.md` - which skill owns which kind of work
- `.agents/luucycle/ROSTER.md` / `.agents/luucycle/ROLES.md` - **user data** at the repo root, never inside the skill (`npx skills update` wipes `.agents/skills/luucycle/`); seeded by `add-cli`
- `RULES.md` - absolute behavioural rules
- `WARNINGS.md` - CLI failure modes observed on real runs