# luucycle roster list

Read-only view of the current roster. Show the latest snapshot for every Agent ID and its role assignments without probing CLIs or changing roster state.

## Steps

1. **Resolve the roster.** Resolve `<skill-root>` as the directory containing this file and `<repo-root>` as the current repository root. Run `python3 "<skill-root>/scripts/check_roster.py" "<repo-root>" --json` and use its `agents` array. When roster files are missing, report that the roster is unavailable and recommend `/luucycle roster add`.

2. **Present the current agents.** Show one row per current Agent ID, ordered by Agent ID:

   | Agent | CLI | Model | Cost | Accessible | Roles | Verified |
   | --- | --- | --- | --- | --- | --- | --- |

   Join multiple roles with commas and show `none` when an agent has no assigned role. Preserve recorded values; `roster list` reports roster state rather than testing it.

3. **Report roster health.** State the validator's `PASS`, `WARN`, or `FAIL` status after the table. Include every reported error and warning, then recommend `/luucycle doctor` when the user needs live CLI and full setup diagnostics.

**Completion criterion:** every current Agent ID appears exactly once from the validator output, its recorded accessibility and roles are visible, all validation findings are reported, and no state or external service was touched.
