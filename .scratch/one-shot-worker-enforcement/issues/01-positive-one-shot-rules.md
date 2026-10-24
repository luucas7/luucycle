# 01 — Positive one-shot dispatch rules and completion flow

**What to build:** Establish the one-shot dispatch paradigm across all orchestration guardrails and execution flow documentation. Remove negative prohibition phrasing regarding conversational follow-ups and replace it with positive behavioral instructions anchored by the leading words `one-shot dispatch` and `terminal sealing`. Define an explicit completion criterion: upon receipt of a terminal worker status (`DONE`, `BLOCKED`, `FAILED`), the coordinator immediately releases the worker terminal and advances the execution plan.

**Blocked by:** None — can start immediately

**Status:** done

- [x] Shared guardrails define workers as one-shot dispatches and specify immediate terminal disposal upon receiving a terminal status receipt.
- [x] Standalone negative prohibitions regarding follow-up prompts are replaced with positive state transition guidance.
- [x] Implementation execution instructions explicitly direct the coordinator to release the worker terminal and advance the plan upon receipt of a compact return.
- [x] UI gatekeeper instructions state that fix passes must be dispatched to fresh terminals rather than recycling completed workers.
- [x] Relative links and context pointers in the updated documentation remain valid and consistent.
