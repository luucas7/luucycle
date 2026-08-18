# luucycle

Orchestrator agent skill: decomposes a request into tasks, routes each task to the right skill, and dispatches workers on the best model from the roster.

## Install

```bash
npx skills add luucas7/luucycle
```

Works on any agent from the [skills CLI](https://github.com/vercel-labs/skills) (OpenCode, Claude Code, Codex, Cursor, ...). Use without installing: `npx skills use luucas7/luucycle --skill luucycle`.

## Structure

- `SKILL.md` — orchestration flow (decompose → route → dispatch → gate → retrospective)
- `ROUTING.md` — which skill owns which kind of work
- `ROSTER.md` — available worker agents (facts only: command, flags, cost)
- `ROLES.md` — role → agent mapping (verifier, builder, architect, researcher, scaffolder)
- `RULES.md` — absolute behavioural rules
- `WARNINGS.md` — CLI failure modes observed on real runs
- `ADD-CLI.md` — branch: grow the roster with a new CLI
- `INIT.md` — branch: bootstrap the skill library in a fresh environment
