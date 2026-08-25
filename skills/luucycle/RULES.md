# luucycle rules

Hard guardrails for every luucycle branch. User instructions and higher-priority policies remain authoritative.

1. **Implementation is explicit.** Only `/luucycle implement <ref|request>` authorizes implementation planning or worker dispatch. Bare `/luucycle` shows help; `/luucycle ask-lucas` and unsupported invocations route to `ASK-LUCAS.md`. Ask Lucas answers only about luucycle itself; application and product questions route to `/luucycle prepare`. Never infer implementation authorization from the request's wording.

2. **Confirm before dispatch.** Wait for explicit approval in `IMPLEMENT.md`'s confirmation step before spawning any worker.

3. **Bounded, approved fallback.** The approved plan names each task's primary worker and at most one fallback. Use that fallback only when it is enabled, has the same permission profile, and does not exceed the approved cost tier. Otherwise pause the task and request approval. Report every fallback in the final receipt.

4. **Route through skills.** Decompose the request and hand each task to the skill that owns that kind of work - orchestration for coordination, the matt-pocock engineering skills for spec/tickets/implement/review, impeccable for UI. Reuse what a routed skill already defines; do not improvise a parallel flow.

5. **Gate all UI through impeccable.** Any change that touches the interface passes through impeccable before it is considered complete.

6. **One source of truth.** The roster owns agent facts, the roles file owns role eligibility, `doctor.py` owns diagnostic mechanics, `roster.py` owns roster mechanics, and this file owns shared guardrails. Branch files own only their branch-specific decisions.

7. **Same process every implementation run.** Predictability is the goal: follow the `IMPLEMENT.md` steps in order for every explicit implementation request, whatever the task.

8. **One roster entry per agent.** Correct or refresh an agent by updating its existing entry. The exact schema lives in [ROSTER-FORMAT.md](ROSTER-FORMAT.md).

9. **Workers receive their routed skill.** Every dispatch names the routed skill and tells the worker how to load it. A worker that cannot access the skill is not ready for that task.

10. **Empty roster is blocking.** With zero `Enabled: true` agents, stop the implementation run, signal the empty roster, and propose `/luucycle roster add`. Never dispatch, never improvise entries.

11. **Roles file owns role → agent mapping.** `.agents/luucycle/ROSTER.md` (repo root) is the only authority on agent facts; `.agents/luucycle/ROLES.md` (repo root) is the only authority on which roles each agent serves. The `roster add` branch updates both in the same pass - a change to one without the other is a violation.

12. **Close only what was authorized.** Commit only when the user explicitly asks for a commit. Close only issues the user explicitly names or has already authorized for closure. Include the results in any authorized closing comment.

13. **Read-only branches do not mutate.** `/luucycle doctor`, `/luucycle roster list`, and the health check inside Ask Lucas may inspect files and run free diagnostic commands only. They never install, update, start services, edit configuration or roster state, dispatch workers, or call a model. They report evidence and the smallest explicit repair command.

14. **Billed probes need fresh consent.** Roster discovery uses free help, catalog, config, or first-party documentation first. A model probe that may bill the user runs only after separate approval immediately before that call.
