# 01 — Offline behavioral trace collector and mock event runner

**What to build:** Build an offline test harness that simulates worker lifecycle events and captures all coordinator actions into a structured, chronological execution trace. The harness runs entirely using the standard library without external network calls or third-party dependencies, intercepting dispatches, inputs, terminal operations, and data queries.

**Blocked by:** 02 — Deterministic terminal sealing and fail-closed post-settlement rejection

**Status:** done

- [x] Trace collector captures timestamped action records (dispatch, prompt, input, terminal release, data read).
- [x] Mock orchestrator event runner feeds synthetic lifecycle scenarios (single-task completion, verbose receipts, non-blocking warnings, fallback transitions).
- [x] Trace records include exact target identifiers, payload hashes, and execution status codes.
- [x] Entire harness executes offline in sub-second duration through standard test discovery.
