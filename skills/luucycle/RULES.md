# luucycle rules

Hard guardrails for every luucycle branch. User instructions and higher-priority policies remain authoritative.

1. **Implementation is explicit.** Only `/luucycle implement <ref|request>` authorizes implementation planning or worker dispatch. Bare `/luucycle`, `/luucycle ask-lucas`, and any invocation without the `implement` subcommand route to `ASK-LUCAS.md` and remain advisory. Never infer authorization from the request's wording.

2. **Confirm before dispatch.** Wait for explicit approval of the plan defined in `IMPLEMENT.md` step 4 before spawning any worker.

3. **Bounded, approved fallback.** The approved plan names each task's primary worker and at most one fallback. Use that fallback only when it is accessible, has the same permission profile, and does not exceed the approved cost tier. Otherwise pause the task and request approval. Report every fallback in the final receipt.

4. **Route through skills.** Decompose the request and hand each task to the skill that owns that kind of work - orchestration for coordination, the matt-pocock engineering skills for spec/tickets/implement/review, impeccable for UI. Reuse what a routed skill already defines; do not improvise a parallel flow.

5. **Gate all UI through impeccable.** Any change that touches the interface passes through impeccable before it is considered complete.

6. **One source of truth.** The roster owns agent facts, the roles file owns role eligibility, and this file owns shared guardrails. Branch files own only their branch-specific steps.

7. **Same process every implementation run.** Predictability is the goal: follow the `IMPLEMENT.md` steps in order for every explicit implementation request, whatever the task.

8. **Roster history is append-only.** Correct or refresh an agent by appending a timestamped snapshot that identifies the snapshot it supersedes. Existing snapshots remain unchanged. The exact schema lives in [ROSTER-FORMAT.md](ROSTER-FORMAT.md).

9. **Workers receive their routed skill.** Every dispatch names the routed skill and tells the worker how to load it. A worker that cannot access the skill is not ready for that task.

10. **Empty roster is blocking.** With zero `Accessible: true` agents, stop the implementation run, signal the empty roster, and propose `/luucycle add-cli`. Never dispatch, never improvise entries.

11. **Roles file owns role → agent mapping.** `.agents/luucycle/ROSTER.md` (repo root) is the only authority on agent facts; `.agents/luucycle/ROLES.md` (repo root) is the only authority on which roles each agent serves. The `add-cli` branch updates both in the same pass - a change to one without the other is a violation.

12. **Close only what was authorized.** Commit only when the user explicitly asks for a commit. Close only issues the user explicitly names or has already authorized for closure. Include the results in any authorized closing comment.

13. **Diagnostics do not mutate.** `/luucycle doctor` and the health check inside Ask Lucas may inspect files and run free diagnostic commands only. They never install, update, start services, edit configuration or roster state, dispatch workers, or call a model. They report evidence and the smallest explicit repair command.
