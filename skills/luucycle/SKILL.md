---
name: luucycle
description: Route luucycle setup, readiness, feature-alignment, roster, and multi-agent implementation commands.
---

# luucycle

Route explicit luucycle commands to the matching branch. Treat `/luucycle` and `$luucycle` as equivalent; examples below use `/luucycle`. A bare invocation selects the advisory Ask Lucas branch.

## Command routing

| Invocation | Branch | File |
| --- | --- | --- |
| `/luucycle` or `/luucycle ask-lucas` | Audit the relevant setup and recommend the exact next command | [ASK-LUCAS.md](ASK-LUCAS.md) |
| `/luucycle doctor` | Run the complete non-mutating readiness audit | [DOCTOR.md](DOCTOR.md) |
| `/luucycle implement <ref\|request>` | Decompose, route, confirm, and dispatch implementation | [IMPLEMENT.md](IMPLEMENT.md) |
| `/luucycle implement` without an argument | Ask for the missing reference or request | [ASK-LUCAS.md](ASK-LUCAS.md) |
| `/luucycle start` | Kick off alignment, then hand over to `implement` | [START.md](START.md) |
| `/luucycle init` | Install the skill library and bootstrap the roster | [INIT.md](INIT.md) |
| `/luucycle add-cli` | Add a CLI/model to the roster | [ADD-CLI.md](ADD-CLI.md) |
| anything else | Explain the valid commands and recommend one | [ASK-LUCAS.md](ASK-LUCAS.md) |

Read [RULES.md](RULES.md), then read and execute exactly the branch selected above. `RULES.md` owns the authorization boundary.
