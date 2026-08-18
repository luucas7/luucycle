# luucycle start

Branch of luucycle for **kicking off a fresh piece of work**. Runs instead of the normal orchestration flow whenever the user wants to start something new ("start", "begin", "démarrer", "nouvelle feature"). It does not dispatch workers: it verifies the environment, then scripts the user's path through the matt-pocock alignment flow so the main flow can orchestrate the implementation afterwards.

## Why this branch exists

The alignment skills (`grill-with-docs`, `to-spec`, `to-tickets`) are **user-invoked** - only the user can type them, the model cannot. And they must all run in the **same conversation**: `to-spec` synthesizes what was already discussed ("no interview"), `to-tickets` works from the conversation context - a fresh session would have nothing to work from. `start` is the bridge: it lines up the prerequisites, then walks the user through the sequence and hands over to the main flow.

## Steps

1. **Verify the prerequisites.** Stop and route on any gap:
   - **Orca runtime up** - `orca status --json` must show a running runtime (binary `orca-ide` on Linux). If not, ask the user to start Orca before continuing - the final dispatch depends on it.
   - **Engineering skills installed** - the agent's available skills show `grill-with-docs`, `to-spec`, `to-tickets`, `implement`. If any is missing, run the `init` branch (`INIT.md`) and stop.
   - **Tracker configured** - `docs/agents/issue-tracker.md` exists (written by `/setup-matt-pocock-skills`). If missing, tell the user to run `/setup-matt-pocock-skills` first and come back; never guess the tracker.

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
   | 4 | `/luucycle <parent ref>` | **new session** | the main flow decomposes, routes, and dispatches the implementation |

   Emphasize: steps 1–3 must stay in the same conversation - `to-spec` and `to-tickets` read the conversation context, so a fresh session loses the design. Step 4 is deliberately a new session: the implementation needs a fresh context window.

4. **Send them off with the reference.** Tell the user to note the parent reference produced by `to-spec` / printed by `to-tickets` - an issue number on GitHub, the spec path on local markdown, the tracker's native identifier otherwise - and to come back with `/luucycle <parent ref>` in a new session.

**Completion criterion:** every prerequisite is verified or explicitly deferred by the user, the tracker type is detected, the plan is presented and approved, and the user leaves with a concrete parent reference and the exact `/luucycle <ref>` command for the new session. The main flow (`SKILL.md`) takes over from there - this branch never dispatches.
