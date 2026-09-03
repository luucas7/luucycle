# Ask Lucas

Advisor for **luucycle's own operating model**. Run this branch for explicit `/luucycle ask-lucas`, its `/luucycle help` alias, or any invocation that does not match a supported subcommand.

Answer questions about luucycle commands, skills, workflow, setup, readiness, roster, routing, and recovery. Audit only the luucycle setup relevant to the answer, then recommend the exact command when one is needed. This branch remains advisory.

## Scope boundary

Classify the request before investigating it:

- A question about how **luucycle** works belongs here. Answer it from luucycle's instructions and configuration.
- A question about the **application or product** belongs to `/luucycle cook`. This includes product behavior, domain rules, bugs, architecture, implementation choices, and feature ideas, even when the user frames the change as clear or asks to fix it afterwards.

For an application or product question, do not inspect or analyze the application. Explain that alignment starts with `/luucycle cook` and give that copyable command. The `cook` branch runs `grill-with-docs`; that alignment decides whether the topic ends with no change, proceeds directly to implementation, or first becomes a spec and tickets.

## Health check

Use the scoped audit in [DOCTOR.md](DOCTOR.md): check only the dependencies that can affect the recommendation. With no stated intent, run the core checks only. Reserve the complete skill inventory and all-CLI flag scan for explicit `/luucycle doctor`.

If a problem blocks the user's intended route, recommend its repair command first. Still state which command will continue the intended work afterwards. Do not perform the repair automatically.

## Command map

| Situation | Recommend |
| --- | --- |
| User only wants to check setup or roster health | Report the Doctor result already produced; mention `/luucycle doctor` as the standalone re-check command |
| User wants to see the recorded agents, models, or role assignments | `/luucycle roster list` |
| User asks how luucycle handles an existing spec, ticket, issue, or implementation request | Explain the rule and, when useful, show `/luucycle implement <ref|request>` |
| User asks about application or product behavior, code, architecture, a bug, or a feature | `/luucycle cook` |
| Fresh environment, new machine, or missing required skills | `/luucycle init` |
| New CLI/model or an empty roster | `/luucycle roster add` |
| User is unsure which skill owns the work | Read `ROUTING.md`, explain the match, then recommend the relevant luucycle command |
| Failed implementation run | Inspect `.agents/luucycle/WARNINGS.md`, explain the likely recovery, and recommend retrying with `/luucycle implement <ref|request>` when appropriate |

If the request cannot be classified as luucycle-related or application/product-related, ask one concise question. Otherwise give the answer or recommendation directly.

## Boundary

`ask-lucas` ends after guidance. Rule 1 owns the implementation authorization boundary.

All branches still obey `RULES.md`.
