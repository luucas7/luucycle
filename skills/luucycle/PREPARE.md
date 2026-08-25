# luucycle prepare

Branch of luucycle for **aligning application and product work**. Invoking `/luucycle prepare` starts `grill-with-docs` in the current conversation. The alignment result decides whether work stops, is ready for direct implementation, or needs a spec and tickets. Implementation always starts in a fresh conversation.

## Steps

1. **Verify alignment readiness.** Run the scoped audit in `DOCTOR.md` and require **Feature alignment** to be `READY`. Stop on `BLOCKED` or `UNKNOWN`; get explicit acceptance before continuing from `DEGRADED`. Report implementation readiness separately so the user knows whether the later handoff is ready, but do not block alignment on an Orca or roster gap.

2. **Start alignment.** Load and run the installed `grill-with-docs` skill immediately in this conversation, using the application or product topic already present in the conversation. `/luucycle prepare` is the authorization to start this interactive alignment; do not ask the user to invoke `/grill-with-docs` separately. If no topic is available, let `grill-with-docs` elicit it.

3. **Choose the delivery path with the user.** Once `grill-with-docs` reports alignment and every design, decision, or vocabulary artifact it names exists, classify the agreed result:

   | Result | Next action |
   | --- | --- |
   | No application change is warranted | Summarize the decision and stop |
   | A bounded change is ready to build without durable specification work | Give `/luucycle implement <agreed request>` for a fresh conversation |
   | The work needs a durable specification or decomposition | Continue with `to-spec`, then `to-tickets` in this conversation |

   Confirm the selected path with the user before creating specification or ticket artifacts. Alignment does not authorize implementation.

4. **Create planning artifacts when selected.** Detect the tracker from `docs/agents/issue-tracker.md`, then load and run `to-spec` followed by `to-tickets` in this conversation. Inspect each reported result before advancing:
   - `to-spec` completes when the parent spec exists in the configured tracker; record its concrete reference;
   - `to-tickets` completes when the child tickets exist and link back to that parent.

   The parent reference is a GitHub issue number for the GitHub template, `.scratch/<feature-slug>/spec.md` for the local-markdown template, or the configured tracker's native identifier. Stop at the first incomplete stage with the missing artifact or repair command.

5. **Hand off.** For either implementation path, give the exact `/luucycle implement <request|parent ref>` command to run in a fresh conversation. For the no-change path, provide no implementation command.

**Completion criterion:** alignment readiness is settled, `grill-with-docs` has completed with its named artifacts present, the user has confirmed one of the three delivery paths, and any selected spec/ticket artifacts or fresh-conversation implementation handoff have been verified and provided.
