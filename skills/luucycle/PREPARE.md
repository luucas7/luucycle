# luucycle prepare

Branch of luucycle for **aligning application and product work**. Invoking `/luucycle prepare` starts `grill-with-docs` in the current conversation. The normal result is durable planning through `to-spec` and `to-tickets`; a clearly bounded change may instead proceed directly to implementation in this conversation after explicit user confirmation.

## Steps

1. **Verify alignment readiness.** Run the scoped audit in `DOCTOR.md` and require **Feature alignment** to be `READY`. Stop on `BLOCKED` or `UNKNOWN`; get explicit acceptance before continuing from `DEGRADED`. Report implementation readiness separately so the user knows whether the later handoff is ready, but do not block alignment on an Orca or roster gap.

2. **Start alignment.** Load and run the installed `grill-with-docs` skill immediately in this conversation, using the application or product topic already present in the conversation. `/luucycle prepare` is the authorization to start this interactive alignment; do not ask the user to invoke `/grill-with-docs` separately. If no topic is available, let `grill-with-docs` elicit it.

3. **Choose the delivery path with the user.** Once `grill-with-docs` reports alignment and every design, decision, or vocabulary artifact it names exists, classify the agreed result. Prefer durable planning unless the agreed change is clearly bounded:

   | Result | Next action |
   | --- | --- |
   | No application change is warranted | Summarize the decision and stop |
   | A clearly bounded change needs no durable specification work | Ask for explicit confirmation to implement now; on confirmation, continue with `IMPLEMENT.md` in this conversation |
   | The work needs a durable specification or decomposition | Continue with `to-spec`, then `to-tickets` in this conversation |

   Confirm the selected path with the user before creating specification or ticket artifacts. For the direct path, the confirmation must explicitly authorize implementation now; that confirmation is the only exception to RULES rule 1.

4. **Create planning artifacts when selected.** Detect the tracker from `docs/agents/issue-tracker.md`, then load and run `to-spec` followed by `to-tickets` in this conversation. Inspect each reported result before advancing:
   - `to-spec` completes when the parent spec exists in the configured tracker; record its concrete reference;
   - `to-tickets` completes when the child tickets exist and link back to that parent.

   The parent reference is a GitHub issue number for the GitHub template, `.scratch/<feature-slug>/spec.md` for the local-markdown template, or the configured tracker's native identifier. Stop at the first incomplete stage with the missing artifact or repair command.

5. **Hand off planned work.** After `to-spec` and `to-tickets`, give the exact `/luucycle implement <parent ref>` command for a fresh conversation. For the direct path, implementation already continues in the current conversation. For the no-change path, provide no implementation command.

**Completion criterion:** alignment readiness is settled, `grill-with-docs` has completed with its named artifacts present, the user has confirmed one of the three delivery paths, and either direct implementation has been explicitly authorized in the current conversation or the selected spec/ticket artifacts and fresh-conversation handoff have been verified and provided.
