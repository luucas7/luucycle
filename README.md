# luucycle

Orchestrator agent skill: decomposes a request into tasks, routes each task to the right skill, and dispatches workers on the best model from the roster. Builds on the [skills CLI](https://github.com/vercel-labs/skills) ecosystem (OpenCode, Claude Code, Codex, Cursor, ...).

## Requirements

- **Orca runtime** (hard requirement) — luucycle coordinates workers through Orca's orchestration layer. Install the [Orca IDE](https://www.onorca.dev) (or run headless with `orca serve`), and **enable the orchestration feature in Settings**. Verify with `orca status --json` — it must show a running runtime. On Linux, the binary is `orca-ide`, never bare `orca` (GNOME screen reader conflict).
- The skills it orchestrates: the [matt-pocock engineering set](https://github.com/mattpocock/skills), [impeccable](https://github.com/pbakaus/impeccable) (UI gate), and Orca's `orchestration` + `orca-cli` skills. The `init` branch installs all of this for you.

## Install

```bash
npx skills add luucas7/luucycle
```

Works on any agent from the skills CLI. Use without installing: `npx skills use luucas7/luucycle --skill luucycle`.

## Commands (branches)

| Trigger | Branch | What it does |
| --- | --- | --- |
| *(a normal request)* | **main flow** (`SKILL.md`) | Decompose → route to a skill → assign a model from the roster → plan approval → dispatch → UI gate → retrospective |
| `init` / "bootstrap" / fresh environment | **`init`** (`INIT.md`) | Install the skill library (mattpocock, impeccable, orca skills), run `/impeccable init`, bootstrap the roster |
| `add-cli` / "add X" | **`add-cli`** (`ADD-CLI.md`) | Grow the roster with a new CLI or model: discover, propose, confirm, append to `ROSTER.md` + map into `ROLES.md` |
| `ask-lucas` / lost | **`ask-lucas`** (`ASK-LUCAS.md`) | Which branch or flow fits your situation |

## Development

Repo-first workflow: this repository is the source of truth.

1. Clone `luucas7/luucycle`, edit the skill under `skills/luucycle/`.
2. Commit and push.
3. Consumers refresh their installed copy: `npx skills update luucycle`.

Installed copies must come from `npx skills add luucas7/luucycle` (symlink installs update automatically; copy installs need the `update` command).

## Structure

- `SKILL.md` — the orchestration flow + branch map
- `ROUTING.md` — which skill owns which kind of work
- `ROSTER.md` — available worker agents (facts only: command, flags, cost) — empty by default, filled by `add-cli`
- `ROLES.md` — role → agent mapping (verifier, builder, architect, researcher, scaffolder)
- `RULES.md` — absolute behavioural rules
- `WARNINGS.md` — CLI failure modes observed on real runs
- `INIT.md` — bootstrap branch
- `ADD-CLI.md` — roster growth branch
- `ASK-LUCAS.md` — router branch