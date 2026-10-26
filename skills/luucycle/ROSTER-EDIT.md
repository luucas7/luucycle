# luucycle roster edit

Reassess **existing Agent IDs only** for `/luucycle roster edit [agent|cli]`. Use [ROSTER-FORMAT.md](ROSTER-FORMAT.md) for schema and `roster.py` for mechanics; this branch owns research, comparison, and approval, not a second writer. New models or CLIs belong to `/luucycle roster add`.

## Steps

1. **Resolve the existing scope.** Resolve `<skill-root>` as this file's directory and `<repo-root>` as the current repository root. Read the recorded facts and role lists, then run:

   ```bash
   python3 -B "<skill-root>/scripts/roster.py" list --json "<repo-root>"
   ```

   With no selector, reassess all recorded entries, including disabled entries. A selector matches an exact Agent ID, or the recorded CLI product or Command; a CLI match selects all its existing entries. Preserve the literal selector; if it is ambiguous between these meanings, show the candidate IDs and ask for the intended scope before research. With no matches, report that and recommend `roster list` or `roster add`, without creating entries. Missing roster files go to `roster add`; malformed existing files are reported without hand-repairing them.
   - **Completion criterion:** list the selected stable IDs and baseline facts/fits, or stop with the exact missing/ambiguous/invalid scope.

2. **Refresh first-party evidence.** For every selected command, read its current first-party documentation and free `--help`, version, and relevant subcommand help. Reuse the free CLI/help and catalog discovery mechanics in [ROSTER-ADD.md](ROSTER-ADD.md) steps 2–3 only, scoped to these commands; keep its growth/proposal/bootstrap flow out of this branch. Verify recorded model identity, availability, invocation, model and bypass flags, and any explicit Orca alias from version-matched help. Read provider model documentation plus current pricing and quota documentation, even when a local catalog is available. A default config value is not a catalog; a visible model is not proof of account access or price.

   Record an evidence table for every selected entry: field/claim, recorded value, observed value, first-party source URL or help/catalog path and command, CLI version, checked date (`YYYY-MM-DD`), and uncertainty. Cost evidence identifies plan/subscription, currency and billing unit, free allowance, applicable rate/usage quota, reset window, regional/account conditions, and paid overage or fallback where documented. Distinguish published limits from actual remaining account quota, which remains `UNKNOWN` unless safely evidenced. Missing, conflicting, or stale sources remain `UNKNOWN`, not zero cost, unlimited quota, or verified availability. Retain old unverified values as stale; do not advance their verification claim. Keep `Cost` within the existing low/medium/high schema and explain the evidence-based tier judgment instead of adding quota fields to the roster.

   Inspect only documented non-secret configuration/catalog metadata. Skip credentials, tokens, auth stores, histories, and unrelated files. Use help/catalog/docs instead of model prompts; any exceptional model probe, even on a free plan, needs separate fresh consent immediately before each call, naming the exact CLI/model, prompt, scope, and possible cost/quota use. Approval of discovery or a roster write does not approve a probe.
   - **Completion criterion:** every selected entry has dated evidence or explicit `UNKNOWN` for availability, flags, cost, and quota; no model call has occurred without its own fresh consent.

3. **Compare every role fit.** Assess every selected entry against every canonical role in `ROSTER-FORMAT.md`, not just its current roles. Show a comparative before/after table with current and proposed decimal fits (or omission), comparison with relevant existing peers, source/date, rationale, and unknowns. Use first-party capability descriptions and available relevant evaluation evidence; label fit as a judgment, not a measured benchmark. Explain unchanged fits and every addition/removal. Plausible aptitude determines eligibility; fit never predicts permissions or sandbox access. Keep uncertain old fits explicitly unverified instead of inventing improved scores. New models may be mentioned as `roster add` candidates only; preserve stable IDs and existing model identities in this edit.
   - **Completion criterion:** every selected entry/role pair has an evidence-backed change, justified unchanged value, or explicit unknown; proposed omissions have reasons and peer comparisons preserve out-of-scope scores.

4. **Build the exact plan without writing the roster.** Encode complete replacement entries for changed selected IDs and complete replacement role lists for affected roles using the existing proposal JSON contract. Preserve all out-of-scope entries, their role references/fits, and unaffected roles. Preserve enabled state unless an explicit change is proposed and approved. Evidence and quota details belong in the review and the selected entry's scoped `Verified` source/date summary, not new schema fields or an automatic `WARNINGS.md` edit. If evidence supports no changes, report that and stop without apply.

   ```bash
   python3 -B "<skill-root>/scripts/roster.py" plan --json <proposal.json> "<repo-root>"
   ```

   Review the full `previews`, `changes`, validation, warnings, `base_hashes`, and `expected_hashes`. Check the preview Agent ID set equals the baseline set: no addition, deletion, duplicate, or ID rename. The shared planner supports upserts, so this existing-only scope check is the branch's responsibility. Its canonical renderer may normalize legacy formatting; include every such difference in the review or stop if it exceeds the intended scope.
   - **Completion criterion:** a valid exact plan preserves existing identity and out-of-scope facts/fits, or errors are reported with no roster write.

5. **Approve the exact write, then apply.** Present the evidence/unknowns, before/after facts and fits, exact file previews or complete diff, validation/warnings, and base/expected hashes. Ask for explicit approval of this exact plan before any roster write. Refusal or absent approval leaves roster files unchanged. Any requested revision requires a rebuild and approval again; any concurrent change rejected by the hash guard also requires a new plan and approval again. Approval is consent to this content, not native write permission; if permission is unavailable, stop with the plan unapplied.

   Only after approval, save that full plan JSON and run:

   ```bash
   python3 -B "<skill-root>/scripts/roster.py" apply --json <plan.json> "<repo-root>"
   ```

   Use the existing hash-guarded apply only; never hand-edit the roster or bypass a stale plan rejection.
   - **Completion criterion:** the exact approved previews are applied, or no write occurs and the rejection/approval gap is reported.

6. **Verify the result.** After successful apply, reread `ROSTER.md` and `ROLES.md`, compare their contents with the approved previews and `expected_hashes`, confirm stable IDs/out-of-scope facts/fits are unchanged, then run:

   ```bash
   python3 -B "<skill-root>/scripts/roster.py" check --json "<repo-root>"
   ```

   Run the free roster and enabled-CLI checks in [DOCTOR.md](DOCTOR.md). Report unchanged disabled entries separately; do not enable them to make diagnostics pass. A further repair needs a fresh exact plan and approval. Finish with changed IDs, evidence dates, role changes, health results, and unresolved cost/quota/access facts; help-only checks do not prove an actual model launch.
   - **Completion criterion:** readback matches the approved plan, roster validation and scoped health checks have results, and every unresolved finding is explicit.
