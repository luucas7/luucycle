# Spec: Behavioral Trace & Replay Harness

## Problem Statement

Proving that an orchestration coordinator adheres to skill rules (such as zero post-completion prompts, immediate terminal release, and compact projection usage) currently relies on manual observation or live, multi-model agent executions. These live tests are costly, slow, non-deterministic, and prone to network variability.

Without an automated, deterministic behavioral testing seam, developers cannot verify whether prompt modifications or document refactorings genuinely improve coordinator behavior or introduce regressions.

## Solution

A deterministic behavioral replay harness that simulates worker lifecycle events, feeds synthetic returns to the coordinator or agent test harness, and captures all emitted actions and tool invocations into an execution trace.

The harness evaluates strict invariants against the resulting trace (such as asserting zero post-settlement prompts, immediate terminal release, and strict compact read usage) entirely offline, running in milliseconds using the standard library.

## User Stories

1. As a skill author, I want a deterministic replay harness that simulates worker lifecycle events, so that I can verify coordinator adherence to orchestration rules locally and cheaply.
2. As a skill author, I want the harness to assert that zero tool calls or stdin writes are directed at a worker after its `DONE` receipt, so that accidental re-prompting is caught automatically during continuous integration.
3. As a developer, I want the replay harness to verify that the coordinator releases worker terminals immediately upon task settlement, so that resource leaks are prevented.
4. As an engineer evaluating skill changes, I want the harness to calculate token consumption and turn count comparisons across versions, so that I have quantitative proof of performance improvements.
5. As a test runner, I want the harness to execute entirely with standard library dependencies and offline synthetic fixtures, so that tests run deterministically in milliseconds without external API keys.
6. As a developer debugging a regression, I want failed invariants to report the exact offending action, timestamp, target ID, and context excerpt, so that root-cause analysis is immediate.

## Implementation Decisions

- **Architectural Placement & Seam**:
  - Implement a dedicated behavioral test harness module located alongside existing test fixtures.
  - The seam is the execution trace interface: the harness intercepts action dispatches and event loops between the coordinator and mock worker environments.

- **Trace Event Collector**:
  - Captures an ordered, immutable log of orchestration events:
    - Task dispatch commands (task ID, worker ID, terminal ID, payload hash).
    - Worker lifecycle notifications (`RUNNING`, `SETTLED`, receipt delivery).
    - Interactive input transmissions and prompt attempts.
    - Terminal lifecycle transitions (`ALLOCATE`, `RELEASE`, `DESTROY`).
    - Data reads (compact projection vs. raw detail lookups).

- **Synthetic Event Feeder**:
  - Replays standardized scenario sequences against the coordinator:
    - Normal single-worker success.
    - Verbose worker returning extra narrative detail.
    - Worker reporting non-blocking warnings.
    - Worker failure requiring fallback dispatch.
    - UI gate rejection triggering a fresh worker pass.

- **Invariant Verification Engine**:
  - Evaluates traces against strict boolean assertions:
    - `Invariant: Zero Post-Settlement Prompts`: No action of type `input` or `prompt` references a worker ID whose status has transitioned to `SETTLED`.
    - `Invariant: Immediate Terminal Release`: A `release` action for the worker's terminal occurs prior to subsequent task dispatch or phase conclusion.
    - `Invariant: Projection Boundary Respect`: Coordinator queries utilize projected receipts without fetching raw source artifacts unless an explicit error condition demands inspection.

- **Performance & Diagnostic Output**:
  - Compares turn counts and estimated payload token sizes across scenario executions.
  - Produces formatted diagnostic reports on failure highlighting the exact violating step in the execution trace.

## Testing Decisions

- **Good Test Definition**:
  - Tests verify that the harness correctly identifies intentional rule violations in synthetic traces and passes valid execution traces cleanly.
  - Tests must never rely on network calls, active model API keys, or platform-specific terminal emulators.

- **Modules Tested**:
  - Behavioral replay harness core.
  - Trace collector and event logger.
  - Invariant assertion rules engine.

- **Prior Art**:
  - Existing synthetic return fixtures and payload reduction benchmark tests in the test suite.

## Out of Scope

- Hosting live multi-model execution infrastructure within standard unit test discovery.
- Testing non-standard third-party shell plugins outside the defined orchestration contract.

## Further Notes

- Runs under `python3 -B -m unittest` with sub-second execution speed, making it suitable for pre-commit hooks and CI pipelines.
