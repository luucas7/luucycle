# luucycle roster format

Read this file when creating or validating `.agents/luucycle/`. Agent IDs are stable references shared by the roster and roles files.

## ROSTER.md

Create `.agents/luucycle/ROSTER.md` with this header:

```md
# luucycle Roster

Append-only snapshots of worker facts. The latest snapshot for an Agent ID is current.

## Agents
```

Append snapshots in this exact form:

```md
### <agent-id> @ <YYYY-MM-DDTHH:MM:SSZ>

- Agent ID: `<agent-id>`
- CLI: `<product name>`
- Command: `<executable>`
- Invocation: `<non-model subcommand and argument template>`
- Model: `<exact model ID or auto-default>`
- Model Flag: `<flag template or none - reason>`
- Bypass Flag: `<flag template or none - reason>`
- Permission Profile: `<what the bypass permits>`
- Cost: `low|medium|high`
- Accessible: `true|false`
- Strength: `<one line>`
- Supersedes: `<immediately prior snapshot heading for this Agent ID, or none for its first snapshot>`
- Verified: `<YYYY-MM-DD; evidence source>`
```

Use `<cli>:<model>` as the Agent ID when possible. A correction or access change appends a snapshot with the same Agent ID and points `Supersedes` to that Agent ID's immediately prior snapshot; existing snapshots remain unchanged.

## ROLES.md

Create `.agents/luucycle/ROLES.md` with this exact table. Eligible agents are ordered Agent IDs separated by `<br>`; the first accessible current snapshot wins.

```md
# luucycle Roles

| Role | When | Context to inject | Output format | Eligible agents (first = best) |
| --- | --- | --- | --- | --- |
| `verifier` | double-checks, review passes, gate passes | diff + checklist + routed skill verdict rules | `path:line: severity: problem. fix.` | |
| `builder` | feature work, TDD, mid-complexity implementation | task + routed skill + target files + conventions | files touched, change, verification, risk | |
| `architect` | systemic refactors and deep debugging | full context + routed skill + constraints + stakes | approach, files, risks, effort | |
| `researcher` | full-codebase or primary-source research | sources + routed skill + question | synthesis with precise sources | |
| `scaffolder` | boilerplate, scripts, docs, easy tasks | raw task + routed skill | delivered files + verification | |
```

Every accessible Agent ID appears in at least one role. Every role lists at least one accessible Agent ID before it can be selected.

## WARNINGS.md

Create `.agents/luucycle/WARNINGS.md` with:

```md
# luucycle WARNINGS

Observed CLI/model failure modes. Each entry records symptom, cause, and the behavior that avoids it, or points to the owning IMPLEMENT.md step.

_None yet._
```
