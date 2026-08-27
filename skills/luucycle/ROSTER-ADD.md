# luucycle roster add

Branch of luucycle for **growing the roster**. Run it only for `/luucycle roster add`; otherwise `ASK-LUCAS.md` may recommend it. The roster is the single source of truth for available workers; add entries only through this flow.

## Steps

1. **Inventory worker CLIs.** When the invocation names a CLI, scope discovery to that command. Otherwise test every candidate with `command -v` and keep every installed result; start with `codex`, `cline`, `opencode`, `agy`, `claude`, `gemini`, `aider`, `cursor-agent`, `amp`, and `goose`, then add commands already recorded in the roster or named by the user. Deduplicate resolved binaries without collapsing distinct commands that point to the same product. Report the complete installed/missing matrix before model discovery. Never stop after the first installed CLI.
   - **Completion criterion:** every candidate is accounted for as installed or missing, and every installed command remains in the discovery set.

2. **Read each installed CLI's help.** Run `<cmd> --help` plus relevant subcommand help (`models`, `auth`, `config`, `agent`) for every discovered command. Inspect only documented text configuration and non-secret catalog/cache files needed to identify model selection and the non-interactive or confirmation-bypass flag; skip credentials, tokens, auth stores, histories, and unrelated files. Record the invocation flag, not a prediction of which operations it permits.
   - **Completion criterion:** for every installed CLI, you can state how it selects a model and how it runs without confirmation - or that it supports neither.

3. **Extract each model catalog.** Use the first available authoritative source for each CLI: a `models` command or model picker/list → a CLI-owned local catalog/cache → current first-party documentation for that CLI. For Codex, inspect `${CODEX_HOME:-$HOME/.codex}/models_cache.json` when present and extract only catalog metadata such as model ID, visibility, and API support. Treat the configured model as the active default only; it never bounds availability. Combine independent sources when one proves CLI visibility and another proves current cost. Do not run a model prompt during discovery.
   - **Completion criterion:** every installed CLI has an evidence row naming all visible/loadable model IDs and their source/date, or an explicit `UNKNOWN` explaining why its catalog could not be established. A configured default is never reported as the sole available model when a catalog, picker, or first-party list exposes alternatives.

4. **Propose the best models for every discovered CLI.** For each CLI with an established catalog, pick up to three models across cost tiers: high (sharpest), medium (best value), and low (bulk/verification). Each proposal carries every field required by [ROSTER-FORMAT.md](ROSTER-FORMAT.md), every role it can plausibly serve with a decimal fit, and the source/date used for cost and model availability. Fit ranks role aptitude only; do not investigate or encode permission compatibility. Do not silently omit an installed CLI, stop after one product, or duplicate an agent already eligible for that role; report the reason for every CLI or tier that yields no proposal.
   - **Completion criterion:** every discovered CLI and viable tier is represented by a complete proposal and all plausible role fits, or an explicit reason for omission.

5. **Build the exact write plan.** Encode the proposed entries and complete replacement role lists as the proposal JSON described in [ROSTER-FORMAT.md](ROSTER-FORMAT.md).

   When the roster files exist, run:

   ```bash
   python3 "<skill-root>/scripts/roster.py" plan --json <proposal.json> "<repo-root>"
   ```

   When `.agents/luucycle/` is missing, render the exact initial `ROSTER.md`, `ROLES.md`, and `WARNINGS.md` contents from [ROSTER-FORMAT.md](ROSTER-FORMAT.md) instead. No roster file is written in this step.
   - **Completion criterion:** the exact contents of every file that would change are available for review, and the repository remains unchanged.

6. **Approve once, then write.** Present the exact file previews and changes. For an existing roster, also present the returned validation status and `base_hashes`. Wait for explicit approval of this exact write. If the user requests changes, rebuild and present the plan again; that revised plan replaces the previous approval target.

   After approval of an existing-roster plan, save the full plan JSON and run:

   ```bash
   python3 "<skill-root>/scripts/roster.py" apply --json <plan.json> "<repo-root>"
   ```

   Existing roster updates go through `plan` and `apply`; do not hand-edit existing roster files. For a missing roster, create the three approved previews exactly as shown, then immediately run `python3 "<skill-root>/scripts/roster.py" check --json "<repo-root>"` before continuing.
   - **Completion criterion:** the approved previews are written exactly once, or no write occurs because approval was not given or the hash guard rejected the plan.

7. **Verify roster health.** Run `python3 "<skill-root>/scripts/roster.py" check --json "<repo-root>"`, then run the roster and enabled-CLI checks in `DOCTOR.md`. Fix only entries added in this approved pass; report unrelated existing failures without rewriting them.
   - **Completion criterion:** the added entries pass roster and enabled-CLI checks, or every unresolved field is reported without changing unrelated entries.

**Completion criterion:** every approved roster entry and scored role change is present, every non-`none` Model/Bypass Flag appears in first-party help, no proposal was silently dropped, and Doctor confirms the new state or names the unresolved field.

## Gotchas

- **The active model is not the catalog.** A config value such as `model = "gpt-5.6-sol"` proves the default only. Continue through the CLI's picker, local catalog/cache, or first-party model documentation before deciding that no alternatives exist.
- **No model selection (freebuff-style).** A CLI can be a bare interactive picker with no flags. Record `none - interactive picker` as the Model Flag; never invent a flag.
- **A model flag is not a model catalog.** When first-party help exposes a selector but no accepted IDs, preserve that verified selector as the Model Flag and continue through the authoritative catalog sources in step 3. If all of them fail, report the catalog as `UNKNOWN` and retain only a separately verified default; never guess IDs.
- **Billed probes are exceptional.** Exhaust free help and catalog sources before reaching the consent gate in RULES rule 14.
