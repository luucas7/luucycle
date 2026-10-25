# Native Orca evidence boundary

`scripts/orca_adapter.py` is separate from the normalized projector in
[COMPACT.md](COMPACT.md). It owns read-only source retrieval and native identity
checks; it never sends worker input, acknowledges messages, starts agents or
grants acceptance.

## Supported scope

The certified specimen version is **Orca 1.4.229**. `scripts/orca_adapter.py`
projects the closed `succeeded` / `completed` / `released` inventory. The
separate `scripts/orca_inbox.py` reads exact native Deliveries and can inspect
current Task/Dispatch authority for active states without treating those states
as completion. Both retain exact IDs, source references, and full native controls.

Other versions, unknown controls, remote hosts and unretrieved retry/creator
lineage return STOP. The inventory adapter does not verify Delivery IDs.
Archive metadata is checked, but archive contents are not retrieved or certified.

## Native Delivery collection

`orca_inbox.collect_delivery(run_id, capture_root, executable=..., terminal=...,
capture_authorized=True, consume_authorized=True)` targets one exact local Run.
It invokes the version-matched guide and uses the native default
`orchestration check --run <id> --json`, then reads Run, Task, worker and current
Dispatch authority and closes the snapshot with matching reads. A default check
creates or replays a durable native Delivery; this is an inbox mutation, and the
caller must explicitly authorize it for that selected Run. The tool does not
acknowledge, reply, send, release, retry an ambiguous check, or choose another
Run. Empty checks are checkpoints without a Delivery ID.

`--peek` remains a non-consuming diagnostic and does not return a Delivery ID.
It cannot be used to project or acknowledge a Delivery. `--all` is history, not a
Delivery. The collector retains the exact native check JSON including the
Delivery ID and complete message body/payload, plus stderr/process receipts and
SHA-256 references. Unknown controls, foreign IDs, partial pages, failed
commands, clipped streams, stale authority or missing assignee/Dispatch joins
return STOP. `source_verified` means owned local retrieval and closing checks
passed; it is not worker acceptance.

`source_verified` means owned retrieval and consistency with responses from the
selected absolute trusted executable and runtime. It does not authenticate the
binary or prove worker claims. The closing fence ignores changing terminal text
and observation timestamps while retaining them in the raw sources. Authority
changes still stop collection. A partial inventory beyond one page remains STOP.

The projector emits `projection.messages[]` with the complete
`native_message`, exact `ids`, native Task/worker/worker-show/current-Dispatch
records, and `parsed_payload` only as an additional JSON view of the original
payload string. For `worker_done`, `taskId`, `dispatchId` and `outcome` must be
present with exact native camelCase names. Orca's `--payload` is exclusive with
typed payload flags, so a payload that carries an attestation must contain the
same IDs and outcome itself. Any nested task evidence remains an assertion to
validate separately; it is never copied into Task.result or invented by this
projector.

The collector links worker_done to the native Task result's exact message ID,
body, outcome and assignee. The existing Task result supplies the report narrative;
the attestation remains in the message's `payload.task_evidence`. Missing evidence
leaves acceptance incomplete while the native settlement remains available for
immediate terminal release.

`compact_delivery(result, normalized_path)` mechanically builds a normalized
return and calls `compact.py`. Retain the returned normalized bytes at that path
before displaying its compact view. Identified task and terminal narrative is
removed; native summary bodies, payloads and safety controls survive even when
their size prevents a particular reduction target.

`read_dispatch_authority(...)` is a separate read-only capture for an exact
Run/Task/Dispatch tuple. It returns native task/dispatch/worker statuses,
assignee, observed time and source references only after all exact identities
and closing receipts agree. `sealed` is true only for the natively completed,
released success shape; a current active Dispatch remains unsealed. This API
does not send worker input or make lifecycle changes.

The live collector is bounded: 64 workers, 128 subprocesses, 30 seconds per
subprocess, 8 MiB per stream and 64 MiB raw stdout in aggregate. Exceeding a bound
is STOP, not a complete sampled result. Capture receipts retain exit code, stderr
reference, truncation and timeout state before normalization.

## Live retrieval versus fixtures

Live `collect` requires an existing authorized capture directory and explicit
`--capture-authorized`. It retains native streams and a normalized artifact with
references, byte lengths and SHA-256 digests, then calls the existing projector.
Use the selected, version-matched Orca executable; verify the actual executable
selection before invoking the collector. Never substitute the Linux screen reader.

Offline fixture inspection:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/orca_adapter.py" fixture --version 1.4.229 --run '<exact-run-id>' --directory '<repo-root>/tests/fixtures/orca/1.4.229'
```

`fixture` always reports `source_verified: false`, even for structurally correct
records. The specimens' provenance manifest distinguishes byte-exact native
responses from narrative-redacted specimens and records their hashes. IDs remain
verbatim. Use fixture results solely for offline structural evidence; establish
live authority through the owned retrieval path instead.

Synthetic inbox cases live under `tests/fixtures/orca/1.4.229/inbox-synthetic/`
and are explicitly labelled as synthetic in the provenance manifest. They test
projector behavior only and do not stand in for a captured native Delivery.

Live results may have `source_verified: true` after owned retrieval, but that
means only the supported inventory sources were checked. Without task evidence
expectations, acceptance is `NOT_EVALUATED`, not accepted. `REVIEW` means inspect
the retained controls; STOP exits 2 and must stop dependent commands.

Audit has no capture permission by default. This collector writes evidence, so
Audit must stop or use a separately verified existing-record/in-memory mechanism;
passing a permission flag is not permission to exceed the approved task rights.

## Task-scoped evidence

Pass `--expectations '<policy.json>'` to bind policies to exact Task IDs. Each
policy contains:

- `routed_skill`: exact `identity`, absolute `path`, and lowercase SHA-256;
- `permissions`: explicit boolean `artifact_write` and `report_write`;
- `storage`: `existing_record` or `artifact`;
- `report_path`: exact authorized absolute path when storage is `artifact`.

The standalone evidence validator checks JSON with schema
`luucycle.task-evidence.v1`, exact `task_id` and `dispatch_id`, matching
`routed_skill` and `loaded_skill` objects, boolean write declarations in
`writes.artifact` / `writes.report`, and a `storage` object.

The inventory reader's optional expectations only succeed for a record already
containing that schema. Ordinary native worker_done produces a Task result wrapper
instead; use `orca_inbox` and WORKER-CONTRACT to read its payload attestation.
The inventory tool leaves such missing evidence incomplete rather than rewriting it.

For read-only work, storage has `kind: existing_record` and the exact reference
`orca:task:<task-id>:result`; both write declarations are false. A writing report
uses `kind: artifact`, `path` and `sha256`, with the corresponding permissions and
write declarations. The validator checks current local skill/report contents.

These checks establish evidence consistency, not that a model actually read a
skill or that a report's factual claims are true. Successful checks remain
`EVIDENCE_REVIEW_NOT_ACCEPTED`. Missing, malformed, foreign or inaccessible proof
returns STOP with acceptance `INCOMPLETE`; inspect complete existing sources or
use a new dispatch. The settled worker stays sealed.

## Verification

Run `tests/test_orca_adapter.py` with Python bytecode disabled. The default suite
uses versioned specimens and scratch-only subprocess probes; live integration
requires explicit opt-in and an available matching local runtime. Report these
scopes separately. A live inventory diagnostic never certifies archive contents,
Deliveries, actual worker skill loading, or end-to-end launch acceptance.
