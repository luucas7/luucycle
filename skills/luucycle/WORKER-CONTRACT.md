# Shared worker dispatch contract

`scripts/worker_contract.py` provides the shared deterministic prompt builder,
receipt validator and guarded Dispatch message path. It complements
[`COMPACT.md`](COMPACT.md) and [`ORCA-ADAPTER.md`](ORCA-ADAPTER.md); it does not
replace their return or native evidence boundaries.

## Approved prompt input

`build_dispatch_prompt(plan)` accepts an explicit immutable-by-convention plan
with exactly these top-level fields:

| Field | Required content |
| --- | --- |
| `approval` | `true`, meaning the exact plan already received approval |
| `target` | Exact `run_id`, `task_id`, `dispatch_id`, and `terminal_id` |
| `task` | Self-contained assignment text |
| `skill` | Exact `identity`, absolute `path`, and lowercase SHA-256 |
| `permissions` | Explicit `artifact_write` and `report_write` booleans |
| `targets` | Nonempty, unique paths or scope names |
| `model` | Explicit `agent_id`, `cli`, Orca `alias`, and requested `model` |
| `evidence` | Required evidence, completion criterion, storage policy, and report path |

The builder checks that the current skill file still hashes to the approved
digest. Before `worker-start`, Orca may not have assigned a Task, Dispatch, or
terminal ID yet. In that case set those target values to `null`; the prompt
marks them as Orca-assigned and tells the worker to follow its live preamble.
After launch, call `bind_launch_ids(plan, launch)` with the exact IDs from the
verified native launch receipt. That returns the fully bound plan for receipt
validation and message preflight. The function checks shape and Run consistency,
but its caller remains responsible for the provenance of `launch`.

The builder rejects an artifact storage plan unless both artifact and report
writes are allowed and the exact report path is a listed target. The result is
stable text for equal inputs. A prompt is not approval, launch proof, or
evidence that the worker actually loaded the skill.

## Return and evidence

`validate_return(expectation, receipt, task_id=..., dispatch_id=...,
source_complete=...)` consumes the current `luucycle.task-evidence.v1` shape by
calling `orca_adapter.validate_task_evidence`. The common receipt envelope is:

```json
{
  "schema": "luucycle.worker-receipt.v1",
  "task_id": "task_0123456789ab",
  "dispatch_id": "ctx_0123456789ab",
  "worker_status": "DONE",
  "worker_done": true,
  "task_evidence": {
    "schema": "luucycle.task-evidence.v1",
    "task_id": "task_0123456789ab",
    "dispatch_id": "ctx_0123456789ab",
    "routed_skill": {"identity": "...", "path": "/absolute/SKILL.md", "sha256": "..."},
    "loaded_skill": {"identity": "...", "path": "/absolute/SKILL.md", "sha256": "..."},
    "writes": {"artifact": false, "report": false},
    "storage": {"kind": "existing_record", "ref": "orca:task:task_0123456789ab:result"}
  }
}
```

`worker_done: true` plus a terminal worker status reports settlement. It never
means acceptance: the strongest result is `EVIDENCE_REVIEW_NOT_ACCEPTED`, and
the adapter's evidence remains a consistency check on worker assertions, not
proof of facts or actual skill loading. A settled receipt with missing evidence
is still reported as settled, with acceptance `INCOMPLETE`; it is not sent back
to that worker for repair.

The native orchestration guide requires a `worker_done` body with a three-sentence
summary and explicit `succeeded` or `failed` outcome. `orca-ide orchestration
send --help` exposes both `--payload` and typed lifecycle flags; the worker
contract says to prefer typed flags, while the installed CLI does not combine
typed flags with raw `--payload`. To carry the additional evidence, the generated
prompt therefore specifies one complete raw payload object containing exact
camelCase lifecycle fields and the nested attestation:

```json
{
  "taskId": "task_0123456789ab",
  "dispatchId": "ctx_0123456789ab",
  "outcome": "succeeded",
  "task_evidence": {
    "schema": "luucycle.task-evidence.v1",
    "task_id": "task_0123456789ab",
    "dispatch_id": "ctx_0123456789ab",
    "routed_skill": {"identity": "...", "path": "/absolute/SKILL.md", "sha256": "..."},
    "loaded_skill": {"identity": "...", "path": "/absolute/SKILL.md", "sha256": "..."},
    "writes": {"artifact": false, "report": false},
    "storage": {"kind": "existing_record", "ref": "orca:task:task_0123456789ab:result"}
  }
}
```

Call the selected executable as an argument list and pass `json.dumps(payload)`
as the single `--payload` argument; do not interpolate a shell command. The body
remains exactly the guide-required three sentences. No report-path or Task
result write is implied by this payload.

`validate_native_worker_done(expectation, projected_message, ...)` parses the
adapter's raw `native_message.payload` JSON, checks equality with
`parsed_payload`, binds `taskId`/`dispatchId`/`outcome`, extracts `task_evidence`,
and delegates evidence checks to `orca_adapter.validate_task_evidence`. This pure
function checks supplied bytes; callers use the owned inbox collector to establish
the native source. An arbitrary object with the same IDs is not authenticated.
The inbox collector links the native Task result's `messageId`, body, outcome and
assignee to this exact worker_done message. The attestation lives in its payload;
the existing Task result supplies the report narrative, not the attestation itself.

## Controlled Dispatch messages

`preflight_dispatch_message(plan, authority, message, now=..., max_age_seconds=5)`
is the pure check. It requires a complete, source-verified authority observation
with the exact Run, Task, Dispatch, and terminal IDs from the plan, no more than
the configured age, and active non-sealed lifecycle states. It refuses unknown,
stale, mismatched, settled, sealed, or released authority.

`controlled_dispatch_send(plan, message, read_fresh_authority=..., send=...)`
calls the authority reader immediately before the sender. The reader must use
the selected Orca executable and the installed, version-matched `orchestration`
guide's supported read operation. For any command not covered by that guide,
consult that executable's `--help`; never infer a command from this wrapper.
The send callback should use the guide's stable native address
`dispatch:<exact-dispatch-id>` and pass the full identity envelope for native
validation. The guide identifies `orchestration send` as durable enqueue only;
an accepted enqueue is not read, started, settled, or accepted work.

The script also exposes a read-only CLI preflight for reviewing caller-provided
JSON snapshots. First obtain fresh authority through supported Orca reads and
retain the approved plan and that observation as JSON, then run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/worker_contract.py" preflight \
  --plan /absolute/path/approved-plan.json \
  --authority /absolute/path/fresh-authority.json \
  --message "<proposed message>"
```

Exit 0 and `status: OK` mean only that the supplied bytes passed the local
preflight. Exit 2 means STOP. This command does not query Orca, refresh the
snapshot, send, or acquire a lock; its timestamp check cannot make an old file
fresh.

The callback interface supports offline tests. For real messages use
`send_orca_message` or the `send` CLI subcommand with an approved bound plan,
`--orca-executable`, `--capture-root`, `--capture-authorized` and `--send-authorized`.
This path calls `orca_inbox.read_dispatch_authority` itself, then performs the exact
native Dispatch send. It accepts only Task `dispatched`, Dispatch `dispatched`,
and terminal accounting state `active`. A Task merely `ready` cannot receive input.
The selected absolute executable and its local runtime are trusted inputs; owned
retrieval establishes consistency with their responses, not binary authentication.
The reader retains source hashes and control records under the authorized root.
STOP before mutation reports `sent: false`; an ambiguous send reports `sent: null`
and keeps its process/stream evidence. Inspect that receipt before any manual retry.

### Enforcement limits

- The exact Dispatch address is Orca's native scope fence: it prevents this
  wrapper from routing a message to a group or an unrelated terminal.
- The fresh read and subsequent send are separate operations. The Dispatch can
  settle between them; neither this wrapper nor a preflight snapshot locks Orca.
- The currently documented native messaging operation does not expose a
  compare-and-send token or atomic settlement fence. `atomic: false` is explicit
  in every preflight and send result. Report this path's non-atomic preflight limit.
- This wrapper cannot intercept other CLIs, APIs, tools, or direct Orca calls.
  It is not a global lock and cannot prevent another sender from targeting a
  settled worker.
- Stop if Orca does not expose complete current Run/Task/Dispatch/terminal
  authority. Never promote an old worker inventory, message receipt, or local
  check result to current authority.

## Verification

Run this contract's fixtures without Python bytecode writes:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B tests/test_worker_contract.py
```

The tests mock authority reads and sends. They do not start a worker, create a
Run, call a live Orca mutation, or certify runtime fencing.
