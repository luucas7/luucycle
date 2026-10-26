---
name: luucycle
description: >-
  Run when a prompt starts with `/luucycle` or the user invokes `$luucycle`. Route its
  setup, readiness, feature-alignment, roster, and multi-agent implementation commands.
---

# luucycle

Treat a prompt beginning with `/luucycle` as an explicit request to run this skill, including in Codex where the native skill trigger is `$luucycle`. Route it to the matching branch before considering the rest of the prompt as a direct coding request. Branch files own command-specific script calls and contracts.

For every routed invocation, read [RULES.md](RULES.md) first, then read and execute exactly the selected branch. For `implement`, the request text is the task brief; it never approves the phase plan. Return the plan and wait for the user's explicit approval before dispatching a worker or changing project files.

## Command routing

| Invocation | Branch | File |
| --- | --- | --- |
| `/luucycle` | Show the available commands and recommend initialization | — |
| `/luucycle help` (alias: `/luucycle ask-lucas`) | Answer questions about luucycle itself and recommend its exact next command | [HELP.md](HELP.md) |
| `/luucycle doctor` | Run the complete non-mutating readiness audit | [DOCTOR.md](DOCTOR.md) |
| `/luucycle implement <ref\|request>` | Decompose, route, confirm, and dispatch implementation | [IMPLEMENT.md](IMPLEMENT.md) |
| `/luucycle implement` without an argument | Ask for the missing reference or request | — |
| `/luucycle cook` | Start app or product alignment with `grill-with-docs`, then choose the delivery path | [COOK.md](COOK.md) |
| `/luucycle init` | Install the skill library and bootstrap the roster | [INIT.md](INIT.md) |
| `/luucycle roster list` | Show agents, models, enabled state, and roles | [ROSTER-LIST.md](ROSTER-LIST.md) |
| `/luucycle roster add [cli]` | Discover installed worker CLIs, or inspect one named CLI, then add models to the roster | [ROSTER-ADD.md](ROSTER-ADD.md) |
| `/luucycle roster edit [agent\|cli]` | Reassess existing agents, evidence, costs, quotas, and role fits; approve the exact plan before writing | [ROSTER-EDIT.md](ROSTER-EDIT.md) |
| anything else | Explain the valid commands and recommend one | [HELP.md](HELP.md) |

For bare `/luucycle`, return a user-facing table derived from the supported command rows above. Use only `Command` and `Description` columns; omit internal file links, `anything else`, and `implement` without an argument. Finish by recommending the copyable `/luucycle init` command in the user's language. Do not run checks or load another branch.

For `/luucycle implement` without an argument, ask one concise question for the spec, tracker reference, or direct implementation request. Do not run checks or load another branch.

For every routed invocation, read [RULES.md](RULES.md), then read and execute exactly the selected branch. `RULES.md` owns the authorization boundary.
