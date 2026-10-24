# Spec: One-Shot Worker Enforcement & Terminal Sealing

## Problem Statement

Coordinators orchestrating multi-agent tasks frequently send follow-up prompts to workers that have already reported a final completion status (`DONE`, `BLOCKED`, or `FAILED`). This conversational recycling re-submits extensive worker transcripts, inflating both coordinator and worker token consumption, dramatically increasing billing costs, violating task boundary isolation, and risking non-deterministic hallucination or state drift.

Furthermore, prior informal attempts to prevent this behavior through prohibitive rules triggered the negation failure mode: instructing an agent not to re-prompt a completed worker keeps the forbidden concept active in its attention window, perversely increasing the probability of conversational follow-ups.

## Solution

Establish a strict "One-Shot Dispatch" architectural lifecycle across all worker orchestration documents and runtime contracts.

In all guidance consumed by the coordinator, the interaction pattern is articulated purely through positive behavioral targets and established leading words (`one-shot dispatch`, `terminal sealing`, `immediate release`). The completion of a worker task is defined by an observable completion criterion: receiving a valid compact receipt immediately triggers terminal release and DAG progression.

At the mechanical execution layer, the contract is enforced fail-closed: once a worker record reaches settled status, its session is sealed. Any subsequent dispatch or input transmission targeting that worker session is rejected deterministically with an explicit error.

## User Stories

1. As an orchestration coordinator, I want workers to operate as one-shot dispatches, so that each task is executed against a clean, isolated context without conversational drift.
2. As an orchestration coordinator, I want clear positive guidance on what action to take upon receiving a terminal status receipt, so that my attention lands directly on releasing the terminal and advancing the task DAG.
3. As a developer running orchestrations, I want finished workers to have their sessions sealed immediately, so that no subsequent tokens or billing costs are incurred through accidental follow-up prompts.
4. As an orchestration runtime, I want any post-completion prompt attempt to fail closed with a clear error, so that rule violations cannot execute silently.
5. As an orchestration coordinator resuming from a relay checkpoint, I want sealed worker states to remain terminal and immutable, so that resumed sessions do not re-probe settled workers.
6. As a developer reviewing orchestration receipts, I want every worker dispatch to record its one-shot lifecycle status, so that any necessary corrective work is explicitly captured as a new distinct task.
7. As a UI review gatekeeper, I want fix workers to be dispatched to fresh terminals rather than recycling previously completed workers, so that reviews are evaluated on isolated diffs.

## Implementation Decisions

- **Architectural Framing & Leading Words**:
  - Adopt `one-shot dispatch`, `terminal sealing`, and `immediate release` as authoritative concepts throughout orchestration documentation and guardrails.
  - Eliminate standalone prohibitive guidance regarding follow-up prompts; express the target behavior as positive state transitions and immediate terminal disposal.

- **Worker Lifecycle State Machine**:
  - Formalize worker lifecycle states:
    ```
    PENDING -> RUNNING -> SETTLED (DONE | BLOCKED | FAILED) -> SEALED
    ```
  - Transition from `SETTLED` to `SEALED` is immediate upon receipt of the compact return.
  - A `SEALED` state is irreversible for that worker session ID.

- **Fail-Closed Mechanical Boundary**:
  - The runtime interface managing dispatches and session inputs must validate target state prior to command execution.
  - If a command attempts to send input or a secondary prompt to a worker in `SETTLED` or `SEALED` state, the interface halts execution and raises a non-zero exit with a dedicated error.

- **Correction & Rework Contract**:
  - When post-completion adjustments or fixes are required (such as following UI gate review or test failures), the coordinator is required to dispatch a new, distinct task to a fresh terminal with a newly allocated worker ID.
  - No existing worker session may be reopened or recycled for fix passes.

- **Return & Relay Preservation**:
  - Compact return payloads retain the sealed state flag within their control records, guaranteeing that checkpoints and session relays preserve worker finality.

## Testing Decisions

- **Good Test Definition**:
  - Tests must evaluate external behavioral contracts and observable state transitions: command exit codes, receipt status codes, and rejection of invalid post-settlement inputs.
  - Tests must never inspect internal variable names or private helper methods.

- **Modules Tested**:
  - Orchestration return normalization and projection engine.
  - Worker lifecycle state machine and session sealing handlers.
  - Diagnostic and self-test verification routines.

- **Prior Art**:
  - Existing compact return unit tests verifying strict schema keys, unknown field rejection, and fail-closed error handling on invalid states.

## Out of Scope

- Modifying closed-source or native third-party CLI agent binaries directly.
- Interactive multi-turn conversational pair-programming modes outside bounded task orchestration.
- Modifying underlying operating system terminal pseudo-ttys beyond session lifecycle signals.

## Further Notes

- Fully aligns with `/writing-for-agents` guidelines regarding progressive disclosure, avoidance of negation traps, and robust completion criteria.
