# luucycle rules

Hard guardrails for every luucycle branch. User instructions and higher-priority policies remain authoritative.

1. **Implementation is explicit.** `/luucycle implement <ref|request>` authorizes coordination and planning, not unapproved execution. The only in-conversation transition is the bounded-change path in `COOK.md`, after `grill-with-docs` and the user's explicit confirmation to implement now. Bare `/luucycle` shows help; `/luucycle ask-lucas`, its `/luucycle help` alias, and unsupported invocations route to `ASK-LUCAS.md`. Ask Lucas answers only about luucycle itself; application and product questions route to `/luucycle cook`. Never infer implementation authorization from the request's wording.

2. **Approve each selected phase.** An implementation run may contain an Audit phase, an Execution phase, or both in that order. Use Audit when the user requests a perimeter check or when existing or partial work makes the requested scope uncertain; otherwise propose Execution directly. Before dispatching a selected phase, present its exact worker plan and wait for explicit approval. An approved Audit authorizes only read-only investigation; it may inspect code and diffs, run non-persistent tests, and collect evidence, but it does not edit files, create artifacts, or change external state. After Audit, conclude with evidence when no execution is needed; otherwise present a new Execution plan and wait for its approval. An approved Execution plan authorizes its complete listed work.

3. **Bounded, approved fallback.** Each approved phase plan names every task's primary worker and at most one enabled fallback on a different CLI product within the approved cost tier. Dispatch that fallback once when the primary reports `BLOCKED` with its unavailable capability, or when coordinator evidence confirms that the primary could not start, stalled, died, or is unavailable. Roster selection does not predict or compare permissions. When the approved fallback cannot complete the task, pause it with both diagnostics and request approval. Report every fallback in the final receipt.

4. **Route through skills.** Decompose the request and hand each task to the skill that owns that kind of work - orchestration for coordination, the matt-pocock engineering skills for spec/tickets/implement/review, impeccable for UI. Reuse what a routed skill already defines; do not improvise a parallel flow.

5. **Gate all UI through impeccable.** Any change that touches the interface passes through impeccable before it is considered complete.

6. **One source of truth.** The roster owns agent facts, the roles file owns role eligibility, `doctor.py` owns diagnostic mechanics, `roster.py` owns roster mechanics, and this file owns shared guardrails. Branch files own only their branch-specific decisions.

7. **Same phase process every implementation run.** Predictability is the goal: follow the selected Audit and/or Execution path in `IMPLEMENT.md` in order for every explicit implementation request.

8. **One roster entry per agent.** Correct or refresh an agent by updating its existing entry. The exact schema lives in [ROSTER-FORMAT.md](ROSTER-FORMAT.md).

9. **Workers receive their routed skill.** Every dispatch names the routed skill and tells the worker how to load it. A worker that cannot access the skill is not ready for that task.

10. **Empty roster is blocking.** With zero `Enabled: true` agents, stop the implementation run, signal the empty roster, and propose `/luucycle roster add`. Never dispatch, never improvise entries.

11. **Roles file owns role → agent mapping.** `.agents/luucycle/ROSTER.md` (repo root) is the only authority on agent facts; `.agents/luucycle/ROLES.md` (repo root) is the only authority on which roles each agent serves. The `roster add` branch updates both in the same pass - a change to one without the other is a violation.

12. **Close only what was authorized.** Commit only when the user explicitly asks for a commit. Close only issues the user explicitly names or has already authorized for closure. Include the results in any authorized closing comment.

13. **Read-only branches do not mutate.** `/luucycle doctor`, `/luucycle roster list`, and the health check inside Ask Lucas may inspect files and run free diagnostic commands only. They never install, update, start services, edit configuration or roster state, dispatch workers, or call a model. They report evidence and the smallest explicit repair command.

14. **Billed probes need fresh consent.** Roster discovery uses free help, catalog, config, or first-party documentation first. A model probe that may bill the user runs only after separate approval immediately before that call.

15. **Vary workers and CLIs across the phase plan.** Every task gets a distinct primary agent when the roster allows, the fallback always runs on a different CLI product than the primary, and any selection warning that signals a roster limit (single-CLI, no different-CLI fallback, forced reuse) is surfaced in the confirmation table with a proposal for `/luucycle roster add`.
