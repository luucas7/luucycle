# luucycle implement

## Steps

1. **Check task readiness.** Run Doctor's Task scope in [implicit mode](DOCTOR.md#output). Continue on `READY`; continue on `DEGRADED` only when every gap is unrelated to the request; stop on `BLOCKED` or `UNKNOWN` with the smallest repair command.

2. **Decompose and assign.** Break the request into tasks and route each through [ROUTING.md](ROUTING.md). Read `.agents/luucycle/ROLES.md`; for each task, choose the narrowest matching `When` criterion and record the role and any ambiguity rationale internally. Select the first accessible current roster snapshot for that role and at most one eligible fallback. Confirm every selected worker can access the routed skill.
   - **Bounded fallback:** a fallback is eligible only under RULES rule 3; otherwise leave it blank.

3. **Confirm the plan.** Present exactly one user-facing table:

   | Task | Assigned model |
   | --- | --- |
   | ... | ... |

   Wait for explicit approval before dispatch. Keep the internal assignment record for worker contracts, fallback guardrails, and the final receipt.

4. **Dispatch with a skill contract.** Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Read `.agents/luucycle/WARNINGS.md`. Every worker request includes the task, routed skill and how to load it, required context, completion criterion, and role output format. Require the receipt to name the loaded skill; pause the task when it cannot.

5. **Gatekeeper (UI Gate).** RULES rule 5: impeccable approval is the completion condition for an interface-touching task.
   - **One gate per final state.** Review only the fully merged diff. After `CHANGES REQUIRED`, dispatch one fix worker and re-gate the updated diff. Allow at most two fix/re-gate cycles; then pause and ask the user how to proceed. Confirm every verdict references code that still exists.
   - **One fresh terminal per gate pass.** Re-using a gate worker's terminal replays its previous conversation and can re-emit the old verdict. Create a new terminal for every re-gate.

6. **Handle a missing, stalled, or dead worker.** Diagnose it with the loaded orchestration guide. Re-dispatch once to the approved fallback when RULES rule 3 permits it; otherwise pause the task with the evidence.
   - **Diagnose before waiting.** Use the guide's worker-state and terminal-state commands to verify heartbeat and execution state before a long wait. Treat a dispatch as dead only when the guide's evidence satisfies its dead-worker condition.
   - **Preserve live reports.** Wait for a live worker's completion report and release it through the guide's lifecycle. Reset/re-dispatch only a worker confirmed dead.

## Completion criterion

Complete only when every task is finished or explicitly paused, every finished UI task passed the Gatekeeper, the final receipt lists each primary and fallback worker ID, status, routed skill, and fallback occurrence, and the Retrospective is delivered.

Conclude with a **Retrospective** identifying orchestration friction, inefficiencies, missing tools, and concrete improvements to `/luucycle`.
