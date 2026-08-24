# luucycle implement

Implementation branch of luucycle. It decomposes a request into tasks, assigns each task a routed skill and a roster model, gets the plan approved, then dispatches workers.

The router selects this branch for `/luucycle implement <ref|request>`. The argument may be a tracker reference, a spec path, or a direct implementation request. `RULES.md` owns its authorization boundary.

## Steps

1. **Read the rules.** Open `RULES.md` first; it owns the shared luucycle guardrails.

2. **Check task readiness.** Run Doctor's Task scope in the [implicit mode defined by DOCTOR.md](DOCTOR.md#output-modes), and require **Implementation** to be `READY` for this request. Stop on `BLOCKED` or `UNKNOWN`; `DEGRADED` may continue only when every gap is unrelated to the request. Report the smallest repair command instead of repairing setup inline.

3. **Decompose and assign.** Break the request into tasks and route each through [ROUTING.md](ROUTING.md). Read `.agents/luucycle/ROLES.md`; for each task, choose the role whose `When` criterion matches the work and record that choice in the internal assignment record. When several roles match, choose the narrowest one and record the rationale there. Select the first accessible current roster snapshot for that role and at most one eligible fallback. Confirm both workers can access the routed skill.
   - **Mandatory orchestration:** use the `orchestration` skill and its version-matched guide for coordination.
   - **Bounded fallback:** a fallback is eligible only under RULES rule 3; otherwise leave it blank.

4. **Confirm the plan.** After a successful implicit Doctor, present exactly one user-facing table of tasks and assigned models:

   | Task | Assigned model |
   | --- | --- |
   | ... | ... |

   Follow this table with the required approval gate and wait for explicit approval before dispatch. Keep the internal assignment record for worker contracts, fallback guardrails, and the final exhaustive receipt.

5. **Dispatch with a skill contract.** Read the `orchestration` skill and fetch its version-matched guide before coordination. Read `.agents/luucycle/WARNINGS.md` before dispatch. Every worker request includes the exact task, routed skill identifier and accessible location/invocation, required context, completion criterion, and role output format. Require the worker receipt to name the skill it loaded; pause the task when it cannot load that skill.

6. **Gatekeeper (UI Gate).** RULES rule 5: impeccable approval is the completion condition for an interface-touching task.
   - **One gate per final state.** Review only the fully merged diff. After `CHANGES REQUIRED`, dispatch one fix worker and re-gate the updated diff. Allow at most two fix/re-gate cycles; then pause and ask the user how to proceed. Confirm every verdict references code that still exists.
   - **One fresh terminal per gate pass.** Re-using a gate worker's terminal replays its previous conversation and can re-emit the old verdict. Create a new terminal for every re-gate.

7. **Handle a missing, stalled, or dead worker.** Diagnose it using the version-matched orchestration guide. Re-dispatch once to the approved fallback when RULES rule 3 permits it; otherwise pause the task with the evidence.
   - **Diagnose before waiting.** Use the guide's worker-state and terminal-state commands to verify heartbeat and execution state before a long wait. Treat a dispatch as dead only when the guide's evidence satisfies its dead-worker condition.
   - **Preserve live reports.** Wait for a live worker's completion report and release it through the guide's lifecycle. Reset/re-dispatch only a worker confirmed dead.

## Completion criterion

Explicitly list every primary and fallback worker ID, actual final status, routed skill, and whether a fallback occurred.

Conclude the session with a **Retrospective**: critically analyze the orchestration workflow just run, identify friction points, inefficiencies, or missing tools in `/luucycle`, and suggest concrete improvements.

The branch is complete only when every task is finished or explicitly paused, every finished UI task passed the Gatekeeper, the exhaustive worker receipt is printed, and the Retrospective is delivered.
