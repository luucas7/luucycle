# luucycle doctor report

Read this file only for explicit `/luucycle doctor`, after completing the checks in `DOCTOR.md`.

Present one compact table:

| Component | Status | Evidence | Next action |
| --- | --- | --- | --- |

Use `PASS`, `WARN`, `FAIL`, or `UNKNOWN`. Evidence names the observed file, binary, skill, role, or error; an unexecuted check is `UNKNOWN`.

Then report these readiness scopes:

- **Implementation:** runtime, orchestration, skills, and roles required by the stated task; without a task, use the core path.
- **Feature alignment:** `grill-with-docs`, `to-spec`, `to-tickets`, and a configured tracker.
- **UI work:** UI implementation readiness, impeccable, and its initialized design context.

Use the readiness states defined in `DOCTOR.md` and state which tasks remain runnable. For every gap, give the smallest applicable repair command:

- runtime or skills → `/luucycle init`, or start Orca when installed but stopped;
- roster or CLI → `/luucycle add-cli`;
- tracker → `/setup-matt-pocock-skills`;
- impeccable context → `/impeccable init`.

When every scope is ready, state that directly without proposing setup work.

**Completion criterion:** all three scopes have a readiness state, every gap has a concrete next action, and every reported status is backed by check evidence.
