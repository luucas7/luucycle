# Ask Lucas

Safe, advisory entry point for luucycle. Run this branch for bare `/luucycle`, explicit `/luucycle ask-lucas`, or any invocation that does not match a supported subcommand.

Understand the intended route, audit the setup relevant to that route, then recommend the exact command. This branch remains advisory.

## Health check

Use the scoped audit in [DOCTOR.md](DOCTOR.md): check only the dependencies that can affect the recommendation. With no stated intent, run the core checks only. Reserve the complete skill inventory and all-CLI flag scan for explicit `/luucycle doctor`.

If a problem blocks the user's intended route, recommend its repair command first. Still state which command will continue the intended work afterwards. Do not perform the repair automatically.

## Command map

| Situation | Recommend |
| --- | --- |
| User only wants to check setup or roster health | Report the Doctor result already produced; mention `/luucycle doctor` as the standalone re-check command |
| User wants to see the recorded agents, models, or role assignments | `/luucycle roster list` |
| `/luucycle implement` has no argument | Ask for the spec, tracker reference, or direct implementation request |
| Existing spec, ticket, issue, or direct request is ready to build | `/luucycle implement <ref|request>` |
| New feature still needs alignment and tickets | `/luucycle prepare` |
| Fresh environment, new machine, or missing required skills | `/luucycle init` |
| New CLI/model or an empty roster | `/luucycle roster add` |
| User is unsure which skill owns the work | Read `ROUTING.md`, explain the match, then recommend the relevant luucycle command |
| Failed implementation run | Inspect `.agents/luucycle/WARNINGS.md`, explain the likely recovery, and recommend retrying with `/luucycle implement <ref|request>` when appropriate |

If the intended route is still ambiguous after reading the request, ask one concise question. Otherwise give the recommendation directly, including a copyable command populated with the user's reference or request when available.

## Boundary

`ask-lucas` ends after guidance. Rule 1 owns the implementation authorization boundary.

All branches still obey `RULES.md`.
