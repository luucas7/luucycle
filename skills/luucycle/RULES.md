# luucycle rules

Hard guardrails for every luucycle branch. User instructions and higher-priority policies remain authoritative.

1. **Implementation is explicit.** `/luucycle implement <ref|request>` authorizes coordination and planning, not unapproved execution. The only in-conversation transition is the bounded-change path in `COOK.md`, after `grill-with-docs` and the user's explicit confirmation to implement now. Bare `/luucycle` shows commands; `/luucycle help`, its `/luucycle ask-lucas` alias, and unsupported invocations route to [HELP.md](HELP.md). Help answers only about luucycle itself; application and product questions route to `/luucycle cook`. Never infer implementation authorization from the request's wording.

2. **Approve each selected phase.** An implementation run may contain an Audit phase, an Execution phase, or both in that order. Use Audit when the user requests a perimeter check or when existing or partial work makes the requested scope uncertain; otherwise propose Execution directly. Before dispatching a selected phase, present its exact worker plan and wait for explicit approval. An approved Audit authorizes only read-only investigation; it may inspect code and diffs, run non-persistent tests, and collect evidence, but it does not edit files, create artifacts, or change external state. After Audit, conclude with evidence when no execution is needed; otherwise present a new Execution plan and wait for its approval. An approved Execution plan authorizes its complete listed work.

3. **Bounded, approved fallback.** Each approved phase plan names every task's primary worker and at most one enabled fallback with a distinct Agent ID within the approved cost tier. The fallback may share the primary's CLI; that does not isolate product-wide availability failures. Dispatch that fallback once in a fresh terminal when the primary reports `BLOCKED` with its unavailable capability, or when coordinator evidence confirms that the primary could not start, stalled, died, or is unavailable. Roster selection does not predict or compare permissions. When the approved fallback cannot complete the task, pause it with both diagnostics and request approval. Report every fallback in the final receipt.

4. **Route through skills.** Decompose the request and hand each task to the skill that owns that kind of work - orchestration for coordination, the matt-pocock engineering skills for spec/tickets/implement/review, impeccable for UI. Reuse what a routed skill already defines; do not improvise a parallel flow.

5. **Gate all UI through impeccable.** Any change that touches the interface passes through impeccable before it is considered complete. Fix passes following gate review dispatch to a fresh terminal rather than recycling completed workers.

6. **One source of truth.** The roster owns agent facts, the roles file owns role eligibility, `doctor.py` owns diagnostic mechanics, `roster.py` owns roster mechanics, [COMPACT.md](COMPACT.md) owns implementation return/projection/relay contracts, and this file owns shared guardrails. Branch files own only their branch-specific decisions.

7. **Same phase process every implementation run.** Predictability is the goal: follow the selected Audit and/or Execution path in `IMPLEMENT.md` in order for every explicit implementation request.

8. **One roster entry per agent.** Correct or refresh an agent by updating its existing entry. The exact schema lives in [ROSTER-FORMAT.md](ROSTER-FORMAT.md).

9. **Workers receive their routed skill.** Every dispatch names the routed skill and tells the worker how to load it. A worker that cannot access the skill is not ready for that task.

10. **Empty roster is blocking.** With zero `Enabled: true` agents, stop the implementation run, signal the empty roster, and propose `/luucycle roster add`. Never dispatch, never improvise entries.

11. **Roles file owns role → agent mapping.** `.agents/luucycle/ROSTER.md` (repo root) is the only authority on agent facts; `.agents/luucycle/ROLES.md` (repo root) is the only authority on which roles each agent serves. For an existing roster, `roster add` and `roster edit` plan both together and apply only the explicitly approved previews through `roster.py`'s hash guard. Initial creation of missing `.agents/luucycle/` instead uses the three exact approved previews under [ROSTER-ADD.md](ROSTER-ADD.md). An unchanged file needs no rewrite; the resulting pair must remain valid.

12. **Close only what was authorized.** Commit only when the user explicitly asks for a commit. Close only issues the user explicitly names or has already authorized for closure. Include the results in any authorized closing comment.

13. **Read-only branches do not mutate.** `/luucycle doctor`, `/luucycle roster list`, and the health check inside Help may inspect files and run free diagnostic commands only. They never install, update, start services, edit configuration or roster state, dispatch workers, or call a model. They report evidence and the smallest explicit repair command.

14. **Billed probes need fresh consent.** Roster discovery uses free help, catalog, config, or first-party documentation first. A model probe that may bill the user runs only after separate approval immediately before that call.

15. **Choose fit within explicit user constraints.** Select by role fit within explicit user constraints, including cost and exclusions. Reuse the best-fit Agent ID and CLI across tasks without a penalty; three identical Codex tasks may use the same agent. CLI diversity is optional, never a reason by itself to require roster expansion.

16. **Workers are one-shot dispatches.** Every worker dispatch operates as a one-shot dispatch ending on a terminal status receipt (`DONE`, `BLOCKED`, `FAILED`). Receiving a terminal status receipt triggers terminal sealing: the worker session is sealed irrevocably, the coordinator records the compact receipt, immediately releases or terminates the worker terminal, and advances the execution plan. Any follow-up adjustment, rework, or corrective task is a distinct dispatch in a fresh terminal.

    Report observed behavior separately from runtime-enforced guarantees. A validated receipt or a successful `check-input` snapshot does not lock Orca's send APIs; use the verified runtime lifecycle and preserve that enforcement limit in the final receipt.

17. **Independent review for every Execution change.** Every Execution change, including small code or documentation changes, requires a `builder` followed by an independent `verifier`: distinct task roles in fresh conversations and terminals, both listed in the same approved Execution table. Reuse the best-fit Agent ID, model or CLI under rule 15; independence comes from the separate review context and authority, not CLI diversity. An absent or unresolved blocked reviewer leaves acceptance incomplete. Builder self-review, green tests or coordinator prose do not replace independent review. [IMPLEMENT.md](IMPLEMENT.md) owns review depth and evidence details. Read-only Audit, Doctor and consultation do not trigger recursive review.
