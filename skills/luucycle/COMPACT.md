# Compact coordinator returns

Read this contract before implementation planning, dispatch, recovery, or resuming
an implementation session. It owns return shape and projection mechanics;
[RULES.md](RULES.md) owns authorization and the installed orchestration guide owns
Orca commands, acknowledgments, authority, and lifecycle.

## Produce, retain, project

Keep detailed task bodies, worker reports, transcripts, and raw runtime receipts
outside the coordinator's context. Choose durable evidence from the task permissions,
not just the phase label. A task with authorized report storage retains its detailed
report as a local artifact with an exact path and digest. A task using existing-record
storage, including a read-only verifier inside Execution, reports through a complete
native message linked to its Task result. Source edits alone do not grant report writes.
Send the coordinator a compact
receipt containing status, required decision, exact IDs, evidence, changes, and
blockers, with the controls below. Use the guide's short lifecycle summary and
report reference where supported; a completion signal alone proves no acceptance.

Audit retains its existing read-only boundary: no report files, temporary capture
files, new artifacts, or external writes. Use an existing retrievable Orca report
or message record for details, and an in-memory pipe for projection. If the runtime
cannot retain/retrieve those details within that boundary, stop with that limitation.
Creating storage requires a separately approved Execution plan.

Bind expected evidence before dispatch: exact routed skill, source path and SHA-256,
task rights, and the permitted report location or existing-record reference. Require
the receipt to attest the same loaded skill and digest, and validate them against
the approved task and retrievable source. This checks evidence consistency, not
independent proof of the model's internal reading. A missing proof, truncated
archive, unverifiable reference or incomplete source leaves **acceptance incomplete**.
Preserve that result and use a new dispatch if further work is needed; always keep
the settled worker sealed rather than soliciting a replacement report from it.

Every test/lint result names its command, exit status, exact linter scope or test
selection, files inspected and diagnostic counts. Keep targeted and global results
separate; a clean skill-only run says nothing about a whole-library lint result.

Before a tool returns a large list or report to the model, capture the full result
in the authorized artifact or consume it in a pipe, normalize it mechanically,
then project it. Do not first print the raw result, or use `head`, text slicing,
output limits, or a model-written summary as the projection. Keep stderr and exit
status: a nonzero command, invalid JSON, missing page, count mismatch, unknown
status, or unresolved error stops the affected decision for targeted verification.
An empty or timed-out wait is only a checkpoint under the guide.

`scripts/compact.py` consumes **luucycle.return.v1**, not native Orca JSON. Its
shape checks and SHA-256 do not authenticate native IDs. Use the distinct
`scripts/orca_adapter.py` for settled/released inventory and `scripts/orca_inbox.py`
for the local inbox/Delivery and current Dispatch boundaries documented in
[ORCA-ADAPTER.md](ORCA-ADAPTER.md). They retrieve native Run, Task and current
Dispatch records before projection. The inbox reader creates or replays a Delivery
only for an explicitly authorized Run; it never acknowledges or sends messages.
Use its mechanical `compact_delivery` projection instead of handwritten
native-to-normalized envelopes. Unsupported versions, remote authorities and
archive-content verification stop the affected decision; retain the native evidence
for inspection or an authorized new dispatch.

Discover the installed guide and command help first. Enumerate every supported
page, record scope and cursors, preserve native control fields (including unknown
ones) in `controls`, and move only identified narrative detail into `detail`.
Unsupported shapes, missing pages and unverifiable completeness are STOP.
Offline inspection always has `source_verified: false`; live source verification
certifies only the declared retrieval scope. Acceptance is `NOT_EVALUATED` without
task expectations and is never granted by projection or source verification alone.

## Versioned boundary

Envelope keys (all required, unknown keys rejected):

| Key | Contract |
| --- | --- |
| `schema` | `luucycle.return.v1` |
| `kind` | `tasks`, `workers`, `orca`, or `relay` |
| `complete` | Explicit boolean; true only after all pages/results are verified |
| `expected_count` | Nonnegative independently established count for this scope |
| `items` | Every record in scope; no sampling or row limit |
| `errors` | Every unresolved error, including command failure and stderr evidence |

Each item has exactly these keys. Empty collections and null decisions must be
explicit, never a substitute for an unperformed check.

| Key | Retained in projection |
| --- | --- |
| `id` | Exact unique record ID, never shortened or replaced by a title |
| `status` | `PENDING`, `RUNNING`, `DONE`, `BLOCKED`, `FAILED`, `UNKNOWN`, `PAUSED`, or `SEALED` |
| `decision` | Object describing the required decision, or null |
| `ids` | Namespaced exact string IDs, e.g. run/task/dispatch/roster agent/terminal/full worktree/thread/message/delivery/plan; never conflate them |
| `evidence` | All decision evidence: source references, observed verdicts, commands and actual results, artifact references/digests |
| `changes` | Exact changed files, revisions, partial work, and external write receipts; explicit empty array when none |
| `blockers` | All unresolved blockers and diagnostics |
| `controls` | All authorization and safety state, preserved recursively without filtering |
| `detail` | Narrative context, full task body, logs, detailed report; retained only in the referenced source |

Producers put **every fact needed for a decision or safety check outside `detail`**.
This includes phase and exact approved plan/scope with approval evidence; primary,
fallback, CLI/cost constraints and selection warnings; routed and actually loaded
skill; expected versus active Dispatch; partial changes; UI verdict tied to the
current merged revision and gate cycle; message processing/ack state; liveness and
its authority/source; settlement and terminal disposition; external-write target,
authorized content/revision, receipt, and independent read-back verification.
Preserve native `scope`, pagination, `failedStage`, `residualResources`, remote
authority, liveness reasons, attention categories and literal `nextAction` argv
when present. Unknown control fields also survive. Missing necessary evidence
requires inspection, never a guessed value. Worker lifecycle states follow the
deterministic one-shot state machine: `PENDING` -> `RUNNING` -> settled (`DONE`,
`BLOCKED`, `FAILED`) -> `SEALED`. Terminal sealing occurs immediately upon receiving
the compact receipt: settled worker sessions transition to `SEALED` or record
`sealed: true` in `controls`. A sealed worker session is terminal and irreversible;
the coordinator rejects any post-settlement input, follow-up prompt, or dispatch
targeting that session and uses a fresh terminal instead. Record whether this is
observed protocol compliance or a verified runtime fence. The script checks shape
and accounting; it does not infer buried facts or grant permission to act.

Projection removes only `detail`, retains all other values exactly, adds counts,
the raw source reference, SHA-256 and byte length. It never truncates a field or
item. `STOP` (exit 2) requires verification of the source or named item before any
dependent action; valid partial/failed receipts still expose their critical fields.
`REVIEW` (exit 0) only means the shape and accounting passed: apply authorization
and the guide's evidence checks before acting. Large critical fields stay large.
Unrepresentable Unicode or a JSON number that would round during serialization
also stops projection; represent precision-sensitive quantities as exact strings.

## Targeted reads and runtime handling

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/compact.py" project "<retained-return.json>"
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/compact.py" get "<retained-return.json>" --id "<exact-record-id>" --sha256 "<projection-source-sha256>"
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/compact.py" check-input "<retained-return.json>" --id "<worker-id>" [--sha256 "<projection-source-sha256>"]
```

For read-only streaming, pass `- --source-ref "<exact-existing-record-reference>"`
instead of the filename to any command. Retrieve that same record for a targeted
read; a digest mismatch stops the lookup. `get` returns one full item and collection
completeness/errors; it retains `STOP` and exit 2 while the source has unresolved
issues, even though the full item is available for inspection. It proves no global completion.
`check-input` is a snapshot guard, not a runtime send interceptor. It validates
the supplied collection's shape, completeness, count and worker state. It does not
authenticate native IDs, refresh authority, acquire a lock, or send any input; it
does not intercept subsequent Orca CLI commands. If the snapshot worker has a terminal status (`DONE`, `BLOCKED`,
`FAILED`, `SEALED`) or has `sealed: true` in controls, execution fails closed (exit 2,
`status: "STOP"`, diagnostic `"worker is sealed; post-completion input is rejected"`).
Active workers (`RUNNING`) succeed with exit 0 and `status: "OK"`.
That result applies only to those bytes, not to a later send or runtime state.
Only a tested runtime mutation boundary can establish runtime-enforced fencing;
report one-shot compliance as observed unless that boundary is verified.
After repair, obtain a fresh complete response and re-project before continuing.

Use [WORKER-CONTRACT.md](WORKER-CONTRACT.md) to build the worker prompt, bind
native launch IDs and validate the `task_evidence` in the exact worker_done payload.
Its live controlled-send path owns a fresh authority retrieval and refuses settled
sessions before enqueue. The read/send pair is non-atomic and covers only this path;
direct native clients remain outside its enforcement scope.

File input must designate a regular file. A directory, including either `""` or
`"."` resolved by `Path`, returns STOP; these values are equivalent directory
references, not two distinguishable filesystem states. Use `-` with a retrievable
source reference for stdin instead.

Use this boundary at task/spec/ticket expansion, every worker return, runtime
enumeration, inbox delivery and terminal diagnostics. Preserve all IDs for every
row and load a full item only for a specific next decision, disagreement, failure,
or evidence check. Read full approval targets and gate evidence when those are
needed: compact returns never replace an exact phase plan or authorize new work.

For Orca inbox batches, preserve every Delivery/message ID and active Task/Dispatch
pair. Process **every** message, validate settlement authority, and record the
terminal's next owner before acknowledging the exact Delivery under the guide.
Projection is neither processing nor acknowledgment. Keep failed start resources
and literal recovery receipts; an unavailable observation never proves death.
After any authorized external write, independently read back the exact target and
verify content/revision before reporting success. Keep mismatch evidence and stop
dependent work. Do not replay a write to compensate for an ambiguous receipt.

## Short relay between sessions

Use one `relay` item with the same compact fields and source references. In
`controls`, include `approvals` (phase, exact plan/scope, evidence and pending
approvals), `verified_state` (observation time, source, revision and limits), and
`incidents` (failures, partial state, fallbacks and unresolved errors). `ids` carries
the active Run/Task/Dispatch/agent/terminal/full worktree/message/Delivery IDs and
initial base branch reference where relevant; `decision` names the next decision.
Sealed worker states and `sealed: true` control flags are preserved across session
relays without modification. Resumed coordinators must honor that protocol and
use a fresh dispatch for further work; the checkpoint itself is not a runtime lock.
Keep detailed history in the referenced records. If Audit has no approved relay
storage, return this checkpoint in the conversation using existing records only.

On resume, read the relay and referenced approval, re-verify active authority,
current diff, pending deliveries, liveness and terminal disposition with targeted
queries from the installed guide. An old checkpoint is evidence of a past
observation, never current runtime truth or new approval. Unavailable, inconsistent,
incomplete or unresolved state pauses dependent work until verified. Continue
within the recorded approval only when its scope and current state still match.
