# luucycle Routing

The skill that owns each kind of work:

This table is consulted from the explicit `/luucycle implement <ref|request>` branch. Routing a task to the `implement` skill does not itself authorize implementation; RULES rule 1 still requires the luucycle `implement` subcommand.

| Intent | Skill |
| --- | --- |
| Coordinate workers, DAGs | `orchestration` (MANDATORY) |
| UI design, fix, review | `impeccable` (Gatekeeper) |
| Request → spec | `to-spec` |
| Spec → tickets | `to-tickets` |
| Tickets / spec → code | `implement` |
| Test-first implementation | `tdd` |
| Review a diff | `code-review` |
| Locate / explore code | `wayfinder` |
| Diagnose a bug | `diagnosing-bugs` |
| Throwaway prototype | `prototype` |
| Domain model / ADR | `domain-modeling` |
| Deep module interface | `codebase-design` |
| Architecture improvements | `improve-codebase-architecture` |
| Stress-test a plan | `grilling` / `grill-me` |
| Research against sources | `research` |
| Triage an issue | `triage` |
| Hand off work | `handoff` |

Route to any other installed matt-pocock skill the way its own description dictates.
