# luucycle

Several AI providers offer free plans. Why let them go unused?

luucycle is an orchestrator agent skill: it splits your request into tasks, routes each to an installed skill, and assigns workers from your approved roster across models and CLI products. Use the free plans you have alongside paid options, within each provider's terms and quotas. Availability and cost vary; luucycle does not provide unlimited free usage or bypass limits.

## How it works

**Decompose → route → assign → approve → dispatch → verify.** You review each task's skill, primary worker, and fallback before work starts. [Orca](https://www.onorca.dev) coordinates the workers; [impeccable](https://github.com/pbakaus/impeccable) gates UI work. Every implementation run ends with worker results and a retrospective.

## Install

```bash
npx skills add luucas7/luucycle
```

Then run `/luucycle init`. It guides installation of the required skills, project setup, and roster bootstrap with your approval. **A running Orca runtime is required** for worker orchestration. Feature alignment and tracker-backed work also need a configured issue tracker.

## Commands

| Command | What it does |
| --- | --- |
| `/luucycle` | Show commands and recommend initialization |
| `/luucycle help` | Answer questions about luucycle itself (`ask-lucas` remains an alias) |
| `/luucycle init` | Set up skills and the worker roster |
| `/luucycle doctor` | Check readiness without changing state or calling models |
| `/luucycle cook` | Align an app or product topic, then choose no change, bounded implementation, or spec and tickets |
| `/luucycle implement <ref\|request>` | Plan implementation, wait for approval, then dispatch workers |
| `/luucycle roster list` | Show recorded workers and role assignments without probing |
| `/luucycle roster add [cli]` | Discover worker CLIs and propose additions for approval |
| `/luucycle roster edit [agent\|cli]` | Reassess existing workers, costs, quotas, and role fits; approve before saving |

Start product questions with `/luucycle cook`; use `/luucycle help` for the workflow. Implementation requires an explicit command (or the confirmed bounded-change path from `cook`) and approval of its phase plan. In Codex, `$luucycle` is the native skill trigger.

See [HELP.md](skills/luucycle/HELP.md) for guidance and [RULES.md](skills/luucycle/RULES.md) for authorization boundaries.