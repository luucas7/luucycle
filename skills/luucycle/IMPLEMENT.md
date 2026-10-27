# luucycle implement

Read [COMPACT.md](COMPACT.md) before planning, dispatch, recovery, or session
resumption. Apply its return boundary to task expansion, worker receipts and Orca
reads before displaying their output to the coordinator.

## Steps

1. **Choose the phase path.** Select only the phases the request needs:
   - **Audit** when the user requests a perimeter check, or when existing or partial work makes the requested scope uncertain.
   - **Execution** directly when the requested scope is already clear.
   - **Audit then Execution** when Audit is needed and may establish work to implement.

   The coordinator may read enough local context to frame this choice and delegate well, but does not perform or claim the substantive perimeter analysis itself.

2. **Prepare and confirm the next selected phase.** Start with Audit when it is selected; after a completed Audit that establishes execution work, return to this step for Execution. For the phase being planned:

   Approval is the boundary between planning and execution. Until the user approves the exact phase table in the current conversation, do read-only preparation and present that table. Do not edit project files, dispatch workers, or run implementation work. The requested feature describes the work to plan; it is not approval to start it.

   **Choose the Execution review level before phase approval.** Choose **Focused** only for a bounded task whose scope is clear, local and reversible, with sufficient objective evidence to verify the result and none of the Extended triggers below.

   Choose **Extended** for ambiguity, multi-component changes or public contracts, security or permissions, persistent data or migrations, concurrency, or insufficient verification. User, project or routed-skill requirements for deeper review select Extended. Mandatory independent review alone does not force Extended. UI work is Extended and still requires the impeccable UI Gate. When in doubt, choose Extended. A small diff or green tests alone do not justify Focused: a small local, reversible correction with focused tests may be Focused; a small permissions change is Extended even with green tests.

   For both levels, plan two sequential tasks under RULES rule 17: one `builder` owns the requested files, including source and tests; a `verifier` task routed to `code-review` depends on the builder. For code plus unit tests, route that builder to `tdd`; otherwise follow ROUTING. The verifier reviews the complete diff read-only and examines the relevant test evidence; it runs the pertinent tests within its approved test rights and reports any untested scope. A Focused review may use a brief report. Extended adds risk-adapted analysis of counterexamples and regressions; it does not automatically add subagents. Keep both rows in the approval table. The verifier uses a fresh terminal and conversation, with its own review brief; select its agent by RULES rule 15, including the builder's Agent ID or CLI when it is the best fit.

   - Break its work into tasks and route each one through [ROUTING.md](ROUTING.md). Record every routed skill and whether any Execution task touches UI.
   - Run Doctor's Task scope in [implicit mode](DOCTOR.md#output), repeating `--required-skill` for every routed skill. Continue on `READY`; continue on `DEGRADED` only when every gap is unrelated to the phase; stop on `BLOCKED` or `UNKNOWN` with the smallest repair command.
   - Resolve `<repo-root>` as an absolute path with `git rev-parse --show-toplevel`. Read `<repo-root>/.agents/luucycle/ROLES.md`; for each task, choose the narrowest matching `When` criterion and record the role and any ambiguity rationale internally. Then run:

     ```bash
     python3 "<skill-root>/scripts/roster.py" select --json [--max-cost low|medium|high] [--avoid <agent-id>]... [--avoid-cli <cli>]... <role> "<repo-root>"
     ```

     Add `--max-cost low|medium|high` only when the user gave a cost ceiling. Use `--avoid` and `--avoid-cli` only for explicit user exclusions, applied to both assignments; leave previous task assignments out of those flags. Follow RULES rule 15 and the ranking/exclusion contract in [ROSTER-FORMAT.md](ROSTER-FORMAT.md#script-contracts). If selection returns `FAIL`, stop with its errors and identify whether the blocker is missing eligibility, disabled agents, cost, or explicit exclusions; propose a repair matching that cause. Keep returned warnings for the confirmation.

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

   Show the stable roster Agent ID in both assignment columns and `none` when no fallback is returned. Keep the role, ambiguity rationale, and script contracts for worker prompts and the final receipt. Surface selection warnings in a short note under the table so approval covers the actual constraints, including a missing eligible fallback. Apply RULES rules 3 and 15 to shared-CLI assignments and roster-expansion decisions.

   Under the same Execution table, state Focused or Extended in that short note, with the risk rationale, planned objective evidence and the independent verifier assignment. Both levels include independent review. Use the existing phase approval, without another table or gate.

   Wait for explicit approval of this exact phase plan before dispatch.

   Before dispatch, read `<repo-root>/.agents/luucycle/WARNINGS.md` in the initial base checkout. Resolve each project path against the target worktree root from Orca's full worktree ID. Inject the task-specific role, roster contract, and warnings directly into the worker request.

   **Validate the selected launch, not an ID prefix.** Repeat Doctor Task scope
   with `--selected-agent '<roster-agent-id>'` for the actual task primary and
   fallback, plus its routed `--required-skill` values. Require each selected
   entry's own CLI and explicit Orca alias/model checks to pass before dispatch.
   A broken unselected entry does not block another healthy agent. Keep the stable
   roster ID distinct from the explicit `orca_agent` launch alias; preserve the
   requested model or stop, rather than substituting a default. Free help preflight
   is not an actual launch proof: verify the native requested/effective launch
   settings afterward within the installed guide's supported contract.

   **Use only supported native evidence.** Apply [ORCA-ADAPTER.md](ORCA-ADAPTER.md)
   before projecting Orca records. Unknown operations, unverifiable sources and
   incomplete retrieval block dependent work. Use `orca_inbox.py` for an explicitly
   authorized Run's complete Delivery and current Dispatch authority.
   A complete inventory diagnostic is not acceptance of a worker report.

   **Freeze the baseline before the first builder.** Use `scripts/git_baseline.py`
   with [GIT-BASELINE.md](GIT-BASELINE.md)'s capture/check contract
   to capture HEAD, index entries, tracked and untracked inventory, and target
   presence and hashes under the approved artifact root outside the checkout.
   Keep preexisting staged, unstaged and untracked changes; a dirty tree is valid.
   Compare the final checkout to that snapshot, accounting for each authorized
   changed path and any unrelated delta. An allowed path is not proof that its
   preexisting edits survived: review those hunks against the original state.
   Stop if the baseline is incomplete; preserve the checkout rather than cleaning it.
   Audit without artifact permission uses existing records or in-memory evidence;
   report a missing durable baseline as a limit rather than creating storage.

   **Specify proof and test rights per task.** Apply COMPACT's permitted evidence
   source to read-only verifiers as well as Audit workers. Bind the routed skill
   path and digest before dispatch and validate the loaded-skill evidence on return.
   Build prompts with [WORKER-CONTRACT.md](WORKER-CONTRACT.md)'s shared builder;
   bind Task/Dispatch/terminal IDs from the actual launch receipt. Validate native
   worker_done payloads through the same contract after source retrieval. A missing
   attestation leaves acceptance incomplete while the native settlement still requires
   immediate terminal release. Send active-task status guidance through the controlled
   native send path; keep its non-atomic enforcement limit in the report. For a blocking
   question, verify its exact message from the Delivery and follow the installed guide's
   `reply` command; a status message does not answer a blocking ask.
   For Python diagnostics and tests, set `PYTHONDONTWRITEBYTECODE=1` and invoke
   `python3 -B`; test tools may still write caches, fixtures, screenshots or state.
   Inspect setup/teardown and constrain temporary storage to the authorized root;
   choose inspected non-persistent probes when the task forbids all writes.

3. **Dispatch Audit and report its outcome.** Skip this step unless the approved phase is Audit. Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Every Audit worker dispatch is a one-shot dispatch. Every request includes its mission, routed skill and how to load it, read-only boundary, required evidence, completion criterion, role output format, the approved roster contract, and the return contract from COMPACT. Require the receipt to name the loaded skill. A worker unable to proceed immediately returns `BLOCKED` with its unavailable capability, observed failure and explicit unchanged partial state in the compact receipt. Worker interaction completion criterion: receiving the compact receipt (`DONE` or `BLOCKED`) triggers terminal sealing; immediately release or terminate the worker terminal and advance the plan. Any subsequent audit task is dispatched to a fresh terminal.

   Synthesize the worker reports without substituting the coordinator's independent perimeter conclusion. Surface any disagreement or out-of-scope finding with its evidence. If Audit was the only selected phase, or it establishes that no execution is needed, conclude directly with the evidence. Otherwise return to step 2 to prepare a distinct Execution plan.

4. **Dispatch Execution with a skill contract.** Skip this step unless the approved phase is Execution. Load the `orchestration` skill and its version-matched guide once for coordination and recovery. Every Execution worker dispatch is a one-shot dispatch. Every request includes the task, routed skill and how to load it, required context, completion criterion, role output format, the approved roster contract, and the return contract from COMPACT. Require the receipt to name the loaded skill. A worker unable to proceed immediately returns `BLOCKED` with its unavailable capability, observed failure and exact partial changes in the compact receipt. Worker interaction completion criterion: receiving the compact receipt (`DONE`, `BLOCKED`, or `FAILED`) triggers terminal sealing; immediately release or terminate the worker terminal and advance the execution plan. Any rework or follow-up is a distinct task dispatched to a fresh terminal.

   If scope or risk increases during building, pause the affected work. Require the builder to report the new risk and exact partial changes; preserve them and return to step 2 for a revised plan and explicit user approval before any further dispatch. Never add a hidden reviewer or self-upgrade the approved plan; use the revised approval boundary instead. A worker's DONE status does not bypass acceptance checks; keep incomplete acceptance explicit.

5. **Gatekeeper (UI Gate).** RULES rule 5: impeccable approval is the completion condition for an interface-touching task.
   - **One gate per final state.** Review only the fully merged diff. After `CHANGES REQUIRED`, dispatch one fix worker to a fresh terminal rather than recycling completed workers, and re-gate the updated diff. Allow at most two fix/re-gate cycles; then pause and ask the user how to proceed. Confirm every verdict references code that still exists.
   - **One fresh terminal per gate pass.** Create a fresh agent terminal in the initial base worktree containing the fully merged diff for every gate and re-gate pass. Each pass starts with the current code and a fresh conversation.

6. **Handle a blocked or unavailable worker.** A primary `BLOCKED` report is sufficient when it names the unavailable capability and observed failure. Receiving the compact receipt completes the primary interaction: immediately release or terminate its terminal, sealing the session. For a worker that never reports, diagnose its terminal and lifecycle with the loaded orchestration guide. Re-dispatch once to the approved fallback in a fresh terminal under RULES rule 3, including the primary's diagnostic and exact partial state; otherwise pause the task with the evidence.
   For an unavailable verifier, use only this approved fallback path; if review remains blocked, pause with acceptance incomplete under RULES rule 17.
   - **Diagnose before waiting.** Use the guide's worker-state and terminal-state commands to verify heartbeat and execution state before a long wait. Treat a dispatch as dead only when the guide's evidence satisfies its dead-worker condition.
   - **Preserve live reports and release immediately.** Wait for a live worker's completion report. Receiving the compact receipt completes the interaction: immediately release or terminate the terminal through the guide's lifecycle, seal the session, and advance the DAG. Reset or re-dispatch only a worker confirmed dead, always creating a fresh terminal for the fallback worker.

7. **Relay when changing sessions.** Produce the short checkpoint defined in COMPACT;
   resume through its verification step before continuing an active phase.

## Completion criterion

Complete only when every selected phase is finished or explicitly paused; every finished UI task passed the Gatekeeper; the final receipt lists each primary and fallback worker ID, status, routed skill, phase, and fallback occurrence; and the Retrospective is delivered. For Audit-only runs that establish no execution is needed, conclude with the evidence instead of requesting another approval.

Keep task completion separate from acceptance: include baseline comparison,
validated evidence sources and loaded skills, exact test/linter scopes, and any
incomplete acceptance or unverified runtime fence in the final receipt.

For Execution, report the approved review level, evidence actually obtained and actual independent
review: reviewer identity, exact diff covered, test evidence examined, verdict and limits.
An absent or unresolved blocked reviewer leaves acceptance incomplete under RULES rule 17.
Report the blocker and any missing evidence without inventing a review or acceptance.

## Retrospective

Conclude with a **Retrospective** identifying orchestration friction, inefficiencies, missing tools, and concrete improvements to `/luucycle`.

For a small Focused task, one sentence on observed friction or no reusable lesson is
sufficient. Report only actual checks and review; invent neither a review nor a
WARNINGS entry.

Propose a targeted addition only when a CLI/agent lesson is well-supported and
reusable. Show the target `<repo-root>/.agents/luucycle/WARNINGS.md` and the exact
proposed text or diff, using [the WARNINGS entry format](ROSTER-FORMAT.md#warningsmd),
and explicitly ask for approval. With no useful lesson, omit the proposal and
approval question. Refusal or absent approval leaves files unchanged. Treat any
promotion as a separate decision limited to the approved diff.

In Audit, present the proposal only; never persist it as part of Audit or its
closure. Any persistence requires a separately authorized transition outside Audit
under RULES' approval boundary. Native authorization does not authorize that
transition.

Content approval is not technical write permission. Before promising a native
authorization prompt, verify that the current runtime actually offers one.
If sandbox protection blocks the target, request separate native user
authorization for the exact write command, once only. The user grants it; never
self-approve or select a persistent/session rule. If the native interface is
unavailable or authorization is denied, leave the target unchanged and report
`proposal approved but not saved`.

After a successful write, reread the target and compare it with the exact approved
diff. If the proposed text changes, obtain approval again before writing.

Keep warnings advisory under RULES and existing roster/role authority. Neither
success nor approval justifies changing user configuration (including persistent
permissions), models, or the roster, disabling the sandbox globally, moving the
source of truth, or bypassing safeguards. Human approval is consent to the diff,
not a safety guarantee or prompt-injection filter. This proposal flow adds no
automatic memory engine or security enforcement. Keep the full retrospective in
the final receipt rather than copying it into general help.

Retrospective delivery completes the run once the completion criterion above is
met. The optional promotion decision never blocks the final receipt, including
after refusal or without a reply.
