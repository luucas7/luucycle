# luucycle prepare

Branch of luucycle for **preparing fresh work**. The user invokes `grill-with-docs`, `to-spec`, and `to-tickets` in one conversation; implementation starts in a fresh conversation.

## Steps

1. **Verify alignment readiness.** Run the scoped audit in `DOCTOR.md` and require **Feature alignment** to be `READY`. Stop on `BLOCKED` or `UNKNOWN`; get explicit acceptance before continuing from `DEGRADED`. Report implementation readiness separately so the user knows whether the later handoff is ready, but do not block alignment on an Orca or roster gap.

2. **Detect the tracker.** Read `docs/agents/issue-tracker.md` and classify it - the handoff reference in step 5 depends on it:
   - **GitHub** (template uses the `gh` CLI) → the parent ref is an issue number.
   - **Local markdown** (template uses `.scratch/`) → the parent ref is the spec file path, `.scratch/<feature-slug>/spec.md`.
   - **Other** (GitLab, Linear, freeform prose) → the ref is whatever the recorded workflow produces; ask the user for the concrete form if it is not obvious.

3. **Present the plan.** Show the sequence and wait for explicit approval:

   | Step | Command | Produces |
   | --- | --- | --- |
   | 1 | `/grill-with-docs` | aligned design and shared vocabulary |
   | 2 | `/to-spec` | tracker-published parent spec |
   | 3 | `/to-tickets` | linked tracer-bullet tickets |
   | 4 | `/luucycle implement <parent ref>` | orchestrated implementation |

4. **Run the alignment stages.** Present one command at a time and wait for the user to invoke it in the current conversation. On each return, inspect the reported result and its project or tracker artifacts before presenting the next command:
   - `/grill-with-docs` completes when it reports alignment and every design, decision, or vocabulary artifact it names exists;
   - `/to-spec` completes when the parent spec exists in the configured tracker; record its concrete reference;
   - `/to-tickets` completes when the child tickets exist and link back to that parent.

   Stop at the first incomplete stage with the missing artifact or repair command. Do not advance on a completion claim without its expected artifact.

5. **Hand off.** Give the user the recorded parent reference and the exact `/luucycle implement <parent ref>` command to run in a new conversation.

**Completion criterion:** alignment readiness is settled, the tracker is detected, the plan is approved, all three stage artifacts are verified in order, and the fresh-conversation handoff contains the recorded parent reference.
