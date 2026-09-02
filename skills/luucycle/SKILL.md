---
name: luucycle
description: Route luucycle setup, readiness, feature-alignment, roster, and multi-agent implementation commands.
---

# luucycle

Route explicit luucycle commands to the matching branch. Treat `/luucycle` and `$luucycle` as equivalent; examples below use `/luucycle`. Branch files own command-specific script calls and contracts.

## Command routing

| Invocation | Branch | File |
| --- | --- | --- |
| `/luucycle` | Show the available commands and recommend initialization | — |
| `/luucycle ask-lucas` or `/luucycle help` | Answer questions about luucycle itself and recommend its exact next command | [ASK-LUCAS.md](ASK-LUCAS.md) |
| `/luucycle doctor` | Run the complete non-mutating readiness audit | [DOCTOR.md](DOCTOR.md) |
| `/luucycle implement <ref\|request>` | Decompose, route, confirm, and dispatch implementation | [IMPLEMENT.md](IMPLEMENT.md) |
| `/luucycle implement` without an argument | Ask for the missing reference or request | — |
| `/luucycle prepare` | Start app or product alignment with `grill-with-docs`, then choose the delivery path | [PREPARE.md](PREPARE.md) |
| `/luucycle init` | Install the skill library and bootstrap the roster | [INIT.md](INIT.md) |
| `/luucycle roster list` | Show agents, models, enabled state, and roles | [ROSTER-LIST.md](ROSTER-LIST.md) |
| `/luucycle roster add [cli]` | Discover installed worker CLIs, or inspect one named CLI, then add models to the roster | [ROSTER-ADD.md](ROSTER-ADD.md) |
| anything else | Explain the valid commands and recommend one | [ASK-LUCAS.md](ASK-LUCAS.md) |

For bare `/luucycle`, return a user-facing table derived from the supported command rows above. Use only `Command` and `Description` columns; omit internal file links, `anything else`, and `implement` without an argument. Finish by recommending the copyable `/luucycle init` command in the user's language. Do not run checks or load another branch.

For `/luucycle implement` without an argument, ask one concise question for the spec, tracker reference, or direct implementation request. Do not run checks or load another branch.

For every routed invocation, read [RULES.md](RULES.md), then read and execute exactly the selected branch. `RULES.md` owns the authorization boundary.
