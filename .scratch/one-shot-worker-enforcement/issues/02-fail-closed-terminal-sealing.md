# 02 — Deterministic terminal sealing and fail-closed post-settlement rejection

**What to build:** Implement mechanical session sealing and validation in the orchestration contract. When a worker returns a terminal status (`DONE`, `BLOCKED`, `FAILED`), its record transitions to a sealed state. Any subsequent attempt to transmit input, send a prompt, or dispatch commands to a sealed worker session is rejected fail-closed with an explicit error.

**Blocked by:** 01 — Positive one-shot dispatch rules and completion flow

**Status:** done

- [x] Worker lifecycle states formally include the `SEALED` state following `SETTLED` (`DONE`, `BLOCKED`, `FAILED`).
- [x] Compact return and projection handlers preserve the sealed status flag across all records.
- [x] Any programmatic or tool-level attempt to send input or dispatches to a sealed session fails closed with a non-zero exit code and diagnostic message.
- [x] Checkpoint relays preserve sealed statuses, preventing resumed sessions from re-probing settled workers.
- [x] Existing return schema, diagnostic self-tests, and unit tests continue to pass without regression.
