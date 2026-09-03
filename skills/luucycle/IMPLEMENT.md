# luucycle implement

## Steps

1. **Choose the phase path.** Select only the phases the request needs:
   - **Audit** when the user requests a perimeter check, or when existing or partial work makes the requested scope uncertain.
   - **Execution** directly when the requested scope is already clear.
   - **Audit then Execution** when Audit is needed and may establish work to implement.

   The coordinator may read enough local context to frame this choice and delegate well, but does not perform or claim the substantive perimeter analysis itself.

2. **Prepare and confirm the next selected phase.** Start with Audit when it is selected; after a completed Audit that establishes execution work, return to this step for Execution. For the phase being planned:

   - Break its work into tasks and route each one through [ROUTING.md](ROUTING.md). Record every routed skill and whether any Execution task touches UI.
   - Run Doctor's Task scope in [implicit mode](DOCTOR.md#output), repeating `--required-skill` for every routed skill. Continue on `READY`; continue on `DEGRADED` only when every gap is unrelated to the phase; stop on `BLOCKED` or `UNKNOWN` with the smallest repair command.
   - Read `.agents/luucycle/ROLES.md`; for each task, choose the narrowest matching `When` criterion and record the role and any ambiguity rationale internally. Then run:

     ```bash
     python3 "<skill-root>/scripts/roster.py" select --json [--max-cost low|medium|high] [--avoid <agent-id>]... [--avoid-cli <cli>]... <role> "<repo-root>"
     ```

     Add `--max-cost low|medium|high` only when the user gave a cost ceiling. The selector ranks aptitude by the role's decimal fit; use cost as a ceiling rather than overriding that ranking. For every task after the first, pass `--avoid` for each Agent ID already assigned in this phase plan (primary or fallback) and `--avoid-cli` for each CLI already used as a primary, so every task gets a distinct agent when the roster allows. Each returned fallback runs on a different CLI product than the primary. If selection returns `FAIL`, stop with its errors and recommend `/luucycle roster add`. Keep every returned warning (single-CLI role, no different-CLI fallback, forced reuse) for the confirmation.

   For **Audit**, present exactly one table:

   | Audit mission | Sources or checks | Routed skill | Primary agent | Fallback agent | Required report |
   | --- | --- | --- | --- | --- | --- |
   | ... | ... | ... | ... | ... | ... |

   State that Audit is read-only: workers may inspect code, diffs, issues, and configuration, and may run only non-persistent tests or diagnostics. They do not edit files, create artifacts, publish comments, or change external state.

   Capture the current branch name as the workers' initial base branch and display `Base branch: <name>` immediately before the Execution plan table. Work from that branch. If Orca creates temporary branches or worktrees, rebase their final work onto the initial base branch before completing the task.

   For **Execution**, present exactly one table:

   | Task | Routed skill | Primary agent | Fallback agent |
   | --- | --- | --- | --- |
   | ... | ... | ... | none |

   Show the stable roster Agent ID in both assignment columns and `none` when no fallback is returned. Keep the role, ambiguity rationale, and script contracts for worker prompts and the final receipt. When selection warned about roster limits (single-CLI role, no different-CLI fallback, or a reused agent), add one short note under the table naming each limit and proposing `/luucycle roster add`, so approval covers the roster's real constraints.

   Wait for explicit approval of this exact phase plan before dispatch.

3. **Dispatch Audit and report its outcome.** Skip this step unless the approved phase is Audit. Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Read `.agents/luucycle/WARNINGS.md`. Every Audit worker request includes its mission, routed skill and how to load it, read-only boundary, required evidence, completion criterion, role output format, and the approved roster contract. Require the receipt to name the loaded skill. A worker unable to proceed returns `BLOCKED: <unavailable capability>; evidence: <observed failure>; partial state: none` instead of guessing or waiting silently.

   Synthesize the worker reports without substituting the coordinator's independent perimeter conclusion. Surface any disagreement or out-of-scope finding with its evidence. If Audit was the only selected phase, or it establishes that no execution is needed, conclude directly with the evidence. Otherwise return to step 2 to prepare a distinct Execution plan.

4. **Dispatch Execution with a skill contract.** Skip this step unless the approved phase is Execution. Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Read `.agents/luucycle/WARNINGS.md`. Every Execution worker request includes the task, routed skill and how to load it, required context, completion criterion, role output format, and the approved roster contract. Require the receipt to name the loaded skill. A worker unable to proceed returns `BLOCKED: <unavailable capability>; evidence: <observed failure>; partial state: <none or exact changes>` immediately; it does not guess or wait silently.

5. **Gatekeeper (UI Gate).** RULES rule 5: impeccable approval is the completion condition for an interface-touching task.
   - **One gate per final state.** Review only the fully merged diff. After `CHANGES REQUIRED`, dispatch one fix worker and re-gate the updated diff. Allow at most two fix/re-gate cycles; then pause and ask the user how to proceed. Confirm every verdict references code that still exists.
   - **One fresh terminal per gate pass.** Re-using a gate worker's terminal replays its previous conversation and can re-emit the old verdict. Create a new terminal for every re-gate.

6. **Handle a blocked or unavailable worker.** A primary `BLOCKED` report is sufficient when it names the unavailable capability and observed failure. For a worker that never reports, diagnose its terminal and lifecycle with the loaded orchestration guide. Re-dispatch once to the approved fallback under RULES rule 3, including the primary's diagnostic and exact partial state; otherwise pause the task with the evidence.
   - **Diagnose before waiting.** Use the guide's worker-state and terminal-state commands to verify heartbeat and execution state before a long wait. Treat a dispatch as dead only when the guide's evidence satisfies its dead-worker condition.
   - **Preserve live reports.** Wait for a live worker's completion report and release it through the guide's lifecycle. Reset/re-dispatch only a worker confirmed dead.

## Completion criterion

Complete only when every selected phase is finished or explicitly paused; every finished UI task passed the Gatekeeper; the final receipt lists each primary and fallback worker ID, status, routed skill, phase, and fallback occurrence; and the Retrospective is delivered. For Audit-only runs that establish no execution is needed, conclude with the evidence instead of requesting another approval.

Conclude with a **Retrospective** identifying orchestration friction, inefficiencies, missing tools, and concrete improvements to `/luucycle`.
