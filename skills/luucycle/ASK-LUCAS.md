# Ask Lucas

You don't remember every branch, so ask.

A **branch** is an alternate path through luucycle. The main flow is the full orchestration run; the branches below are narrower, and each has its own file. Everything else is a routed skill.

## The map

- **"I have work to orchestrate"** → **main flow** (`SKILL.md`): read `RULES.md` → check roster/roles (`.agents/luucycle/ROSTER.md`, `.agents/luucycle/ROLES.md` — repo root) → decompose + route (`ROUTING.md`) → present the task/skill/model table → wait for approval → dispatch → UI Gate → retrospective. Every run, same order.
- **"Which skill owns this kind of work?"** → `ROUTING.md`. Route to the skill that owns the work; luucycle never reimplements a routed skill inline.
- **"Which model for which task?"** → `.agents/luucycle/ROLES.md` (repo root). Five roles (verifier, builder, architect, researcher, scaffolder), each an ordered eligible list - take the first `Accessible: true` agent.
- **"New feature / I want to start something"** → **`start` branch** (`START.md`). Verifies prerequisites (Orca, skills, tracker), scripts `/grill-with-docs` → `/to-spec` → `/to-tickets` in one session, then hands off to the main flow with `/luucycle <parent ref>`.
- **"Fresh environment / new machine / missing skills"** → **`init` branch** (`INIT.md`). Installs the skill library from the manifest (mattpocock, impeccable, orca), then bootstraps the roster.
- **"New CLI / new model"** → **`add-cli` branch** (`ADD-CLI.md`). Propose → confirm → append to `.agents/luucycle/ROSTER.md` + map into `.agents/luucycle/ROLES.md`.
- **"Roster is empty / nothing accessible"** → `add-cli`. An empty roster is blocking (RULES rule 9) - never dispatch on one.
- **"Something failed on a run"** → `.agents/luucycle/WARNINGS.md` (repo root). Known failure modes and the behaviour that avoids them - read it before the first dispatch.

## Hard rules that survive any branch

1. Present the task/skill/model table and wait for explicit approval before any dispatch (RULES rule 1).
2. Never improvise roster entries - the roster is the only authority (RULES rule 5, 7).
3. Every UI-touching task ends at the impeccable Gatekeeper (RULES rule 4).
4. Release, never abandon, a worker that is still working (SKILL.md step 7).
