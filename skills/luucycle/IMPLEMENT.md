# luucycle implement

## Steps

1. **Decompose and route.** Break the request into tasks and route each through [ROUTING.md](ROUTING.md). Record the routed skill for every task and whether any task touches UI.

2. **Check task readiness.** Run Doctor's Task scope in [implicit mode](DOCTOR.md#output), repeating `--required-skill` for every routed skill. Continue on `READY`; continue on `DEGRADED` only when every gap is unrelated to the request; stop on `BLOCKED` or `UNKNOWN` with the smallest repair command.

3. **Assign workers.** Read `.agents/luucycle/ROLES.md`; for each task, choose the narrowest matching `When` criterion and record the role and any ambiguity rationale internally. Then run:

   ```bash
   python3 "<skill-root>/scripts/roster.py" select --json <role> "<repo-root>"
   ```

   Add `--max-cost low|medium|high` only when the user gave a cost ceiling. Use the returned `primary`, `fallback`, and `contracts` fields as the assignment source of truth. If selection returns `FAIL`, stop with its errors and recommend `/luucycle roster add`.

4. **Confirm the plan.** Present exactly one user-facing table:

   | Task | Routed skill | Primary agent | Fallback agent |
   | --- | --- | --- | --- |
   | ... | ... | ... | none |

   Show the stable roster Agent ID in both assignment columns and `none` when no fallback is returned. Wait for explicit approval of this exact assignment before dispatch. Keep the role, ambiguity rationale, and script contracts for worker prompts and the final receipt.

5. **Dispatch with a skill contract.** Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Read `.agents/luucycle/WARNINGS.md`. Every worker request includes the task, routed skill and how to load it, required context, completion criterion, role output format, and the approved roster contract. Require the receipt to name the loaded skill; pause the task when it cannot.

6. **Gatekeeper (UI Gate).** RULES rule 5: impeccable approval is the completion condition for an interface-touching task.
   - **One gate per final state.** Review only the fully merged diff. After `CHANGES REQUIRED`, dispatch one fix worker and re-gate the updated diff. Allow at most two fix/re-gate cycles; then pause and ask the user how to proceed. Confirm every verdict references code that still exists.
   - **One fresh terminal per gate pass.** Re-using a gate worker's terminal replays its previous conversation and can re-emit the old verdict. Create a new terminal for every re-gate.

7. **Handle a missing, stalled, or dead worker.** Diagnose it with the loaded orchestration guide. Re-dispatch once to the approved fallback when RULES rule 3 permits it; otherwise pause the task with the evidence.
   - **Diagnose before waiting.** Use the guide's worker-state and terminal-state commands to verify heartbeat and execution state before a long wait. Treat a dispatch as dead only when the guide's evidence satisfies its dead-worker condition.
   - **Preserve live reports.** Wait for a live worker's completion report and release it through the guide's lifecycle. Reset/re-dispatch only a worker confirmed dead.

## Completion criterion

Complete only when every task is finished or explicitly paused, every finished UI task passed the Gatekeeper, the final receipt lists each primary and fallback worker ID, status, routed skill, and fallback occurrence, and the Retrospective is delivered.

Conclude with a **Retrospective** identifying orchestration friction, inefficiencies, missing tools, and concrete improvements to `/luucycle`.
