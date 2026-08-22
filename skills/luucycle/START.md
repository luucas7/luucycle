# luucycle start

Branch of luucycle for **kicking off a fresh piece of work**. Run it only for `/luucycle start`. It verifies the environment and scripts the user's path through the matt-pocock alignment flow; worker dispatch belongs to the later explicit `implement` branch.

## Why this branch exists

The alignment skills (`grill-with-docs`, `to-spec`, `to-tickets`) are **user-invoked** - only the user can type them, the model cannot. And they must all run in the **same conversation**: `to-spec` synthesizes what was already discussed ("no interview"), `to-tickets` works from the conversation context - a fresh session would have nothing to work from. `start` is the bridge: it lines up the prerequisites, then walks the user through the sequence and hands over to the explicit implementation branch.

## Steps

1. **Verify alignment readiness.** Run the scoped audit in `DOCTOR.md` and require **Feature alignment** to be `READY`. Stop on `BLOCKED` or `UNKNOWN`; get explicit acceptance before continuing from `DEGRADED`. Report implementation readiness separately so the user knows whether the later handoff is ready, but do not block alignment on an Orca or roster gap.

2. **Detect the tracker.** Read `docs/agents/issue-tracker.md` and classify it - the handoff reference in step 4 depends on it:
   - **GitHub** (template uses the `gh` CLI) → the parent ref is an issue number.
   - **Local markdown** (template uses `.scratch/`) → the parent ref is the spec file path, `.scratch/<feature-slug>/spec.md`.
   - **Other** (GitLab, Linear, freeform prose) → the ref is whatever the recorded workflow produces; ask the user for the concrete form if it is not obvious.

3. **Present the plan.** Show the full sequence as a table and wait for the user's explicit go - nothing happens until they confirm:

   | Step | Command | Where | What it produces |
   | --- | --- | --- | --- |
   | 1 | `/grill-with-docs` | this session | aligned design + shared vocabulary (CONTEXT.md, ADRs) |
   | 2 | `/to-spec` | **same session** | the spec, published to the tracker - this becomes the parent issue |
   | 3 | `/to-tickets` | **same session** | tracer-bullet tickets with blocking edges, linked to the parent |
   | 4 | `/luucycle implement <parent ref>` | **new session** | the implementation branch decomposes, routes, and dispatches the work |

   Emphasize: steps 1–3 must stay in the same conversation - `to-spec` and `to-tickets` read the conversation context, so a fresh session loses the design. Step 4 is deliberately a new session: the implementation needs a fresh context window.

4. **Send them off with the reference.** Tell the user to note the parent reference produced by `to-spec` / printed by `to-tickets` - an issue number on GitHub, the spec path on local markdown, the tracker's native identifier otherwise - and to come back with `/luucycle implement <parent ref>` in a new session.

**Completion criterion:** every prerequisite is verified or explicitly deferred by the user, the tracker type is detected, the plan is presented and approved, and the user leaves with a concrete parent reference and the exact `/luucycle implement <ref>` command for the new session. The implementation branch (`IMPLEMENT.md`) takes over from there - this branch never dispatches.
