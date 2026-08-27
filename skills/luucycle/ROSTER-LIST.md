# luucycle roster list

Read-only view of the current roster. Show every Agent ID and its role assignments without probing CLIs or changing roster state.

## Steps

1. **Resolve the roster.** Resolve `<skill-root>` as the directory containing this file and `<repo-root>` as the current repository root. Run `python3 "<skill-root>/scripts/roster.py" list --json "<repo-root>"` and use its `agents` array. When roster files are missing, report the script errors and recommend `/luucycle roster add`.

2. **Present the agents.** Show one row per Agent ID, ordered by Agent ID:

   | Agent | CLI | Model | Cost | Enabled | Roles | Verified |
   | --- | --- | --- | --- | --- | --- | --- |

   Join multiple roles with commas as `<role>@<fit>` using each agent's `role_fit` map, and show `none` when an agent has no assigned role. Preserve recorded values; `roster list` reports roster state rather than testing it.

3. **Report roster health.** State the validator's `PASS`, `WARN`, or `FAIL` status after the table. Include every reported error and warning, then recommend `/luucycle doctor` when the user needs live CLI and full setup diagnostics.

**Completion criterion:** every Agent ID appears exactly once from the validator output, its enabled state and roles are visible, all validation findings are reported, and no state or external service was touched.
