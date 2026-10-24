# 02 — Behavioral invariant assertions for zero post-settlement prompts and terminal disposal

**What to build:** Implement a rules verification engine evaluating captured coordinator traces against strict behavioral invariants: zero post-settlement prompts, immediate terminal release upon task completion, and strict adherence to compact projections over raw detail payloads.

**Blocked by:** 01 — Offline behavioral trace collector and mock event runner

**Status:** done

- [x] Invariant check verifies that exactly zero input or prompt actions target a worker once its terminal status (`DONE`, `BLOCKED`, `FAILED`) is emitted.
- [x] Invariant check asserts that a terminal release action occurs immediately upon task settlement before advancing to subsequent dispatches.
- [x] Invariant check verifies that coordinator reads utilize compact projections and do not inspect raw detail payloads in normal operations.
- [x] Invariant failures produce actionable diagnostic reports highlighting the offending action, line, and timestamp.
- [x] Harness reports summary metrics (turn counts, payload bytes) comparing scenario executions.
