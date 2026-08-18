# luucycle WARNINGS

CLI- and model-specific failure modes observed on real runs (share-card feature, 2026-08-17). Read before long waits or dispatch. Each entry: symptom → cause → behaviour that avoids it. Where the response is already a SKILL.md step rule, the entry points to that step instead of restating it — the steps are the single source of truth for behaviour.

## orca-ide (Orca orchestration CLI)

### Delivery replays until acked
- **Symptom:** `check --wait` returns the same message (same `deliveryId`) over and over, 15 min each.
- **Cause:** a bound Run replays the same Delivery batch until `check --ack <delivery_id>`. Peeking with `check` (without `--ack`) does not consume.
- **Behaviour:** after processing a batch, ack it immediately: `orca-ide orchestration check --ack <delivery_id>`.

### Stalled worker looks "ready" forever
- **Symptom:** task stays `dispatched`; `check --wait` times out with zero messages; worker never reports.
- **Cause:** a worker whose agent terminal died (e.g. parent pane torn down) stays `stage: input_accepted` with no heartbeat. `worker-start` refuses a still-`dispatched` task, so the reset must precede re-dispatch.
- **Behaviour:** SKILL.md step 7 — diagnose before waiting; abandon only a confirmed-dead worker.

### Never abandon a worker that is still working
- **Symptom:** `worker_done` arrives rejected: "Dispatch capability is revoked" — the verdict exists but the report is lost from the message flow.
- **Cause:** `worker-abandon` on a live worker revokes its capability; its final report can no longer be delivered. A dead worker's terminal shows `exited`.
- **Behaviour:** SKILL.md step 7 — release, never abandon; wait for the live worker's report.

### `worker-release` after an auto-completed dispatch is a no-op
- **Symptom:** `worker-release --dispatch <id>` returns `dispatch_not_found` although `dispatch-show` proves the dispatch exists — observed 3/3 dispatches on 2026-08-18.
- **Cause:** a valid `worker_done` already auto-completed the dispatch and revoked its capability; release has nothing left to settle. The low-level terminal (agy-style, not Orca-owned) stays open at its prompt.
- **Behaviour:** treat `dispatch_not_found` on release as "already released". Confirm the worker is idle (`terminal read` shows the prompt), then close its terminal yourself: `terminal close --terminal <handle>`. Close only an idle, reported, acked worker — never before its report is delivered.

## agy (Gemini)

### Not an Orca-known TUI agent
- **Symptom:** `worker-start --agent agy` fails: "A configured --agent is required".
- **Cause:** Orca only knows claude/codex/cline/copilot/opencode-style agents; agy is a plain CLI.
- **Behaviour:** launch it low-level: `terminal create --worktree active --command "agy --dangerously-skip-permissions"`, wait for `tui-idle`, then `orchestration dispatch --task <id> --to <handle> --inject`.

### Reused terminal replays the previous verdict
- **Symptom:** a re-gate returns an identical verdict with dead line numbers (code that no longer exists).
- **Cause:** agy keeps the conversation context; re-injecting into the same terminal re-runs the old reasoning.
- **Behaviour:** SKILL.md step 6 — one fresh terminal per gate pass; never re-dispatch a gate into the terminal that produced the previous verdict.

## cline

### Slow or silent workers
- **Symptom:** gates take very long (10-30 min); sometimes the terminal shows an exited state after long idle.
- **Cause:** cline is dependable but slow on read-only reviews with sub-agent assessments.
- **Behaviour:** prefer faster models (agy, deepseek-flash) for review/gate passes; keep cline for implementation. Check `worker-read` tail for signs of life before abandoning.

## freebuff (Codebuff-based interactive TUI)

### Not an Orca-known TUI agent
- **Symptom:** `worker-start --agent freebuff` fails: "A configured --agent is required".
- **Cause:** Orca only knows claude/codex/cline/copilot/opencode-style agents; freebuff is a plain interactive TUI.
- **Behaviour:** launch it low-level: `terminal create --worktree active --command "freebuff"`, wait for `tui-idle`, then `orchestration dispatch --task <id> --to <handle> --inject`.

### No model or bypass flags — interactive picker
- **Symptom:** `freebuff --model=...` or a bypass flag errors; `--help` only exposes `login`, `--continue`, `--cwd`.
- **Cause:** model and permission handling happen in-session, not via CLI flags. Verified in the binary (2026-08-17): `FREEBUFF_MODE` is hardcoded `"true"` — the codebuff flags `--agent`/`--lite`/`--max`/`--plan` exist in the bundle but are never registered; no env var selects a model.
- **Behaviour:** start with a bare `freebuff` and pick the model in the startup picker (default DeepSeek V4 Pro 08/13; DeepSeek V4 Flash 07/31 fallback after premium sessions). Never promise a specific model for a freebuff worker — treat it as "pick the cheapest available".
