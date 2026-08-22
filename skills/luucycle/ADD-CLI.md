# luucycle add-cli

Branch of luucycle for **growing the roster**. Run it only for `/luucycle add-cli`; otherwise `ASK-LUCAS.md` may recommend it. The roster is the single source of truth for available workers; add entries only through this flow.

## Steps

1. **Locate the CLI.** Confirm the binary exists (`which <cmd>`) and record its version (`<cmd> --version`). If it is not on PATH, stop and ask for the path or install command.

2. **Read its docs.** Run `<cmd> --help` plus relevant subcommand help (`models`, `auth`, `config`, `agent`). Inspect only documented text configuration files needed to identify model selection; skip credentials, tokens, auth stores, histories, and unrelated files.
   - **Completion criterion:** you can state how this CLI selects a model (flag, subcommand, picker, config-only) and how permissions are bypassed - or you can state that it can do neither.

3. **Extract the model list.** Priority: a `models` subcommand (e.g. `agy models`) → config default + help examples → current first-party documentation when the CLI hides its catalog.
   - **Completion criterion:** you can name the exact loadable model IDs, or you can name the one default with no alternatives.

4. **Propose the three best.** Pick up to three models across cost tiers: high (sharpest), medium (best value), and low (bulk/verification). Each proposal carries every field required by [ROSTER-FORMAT.md](ROSTER-FORMAT.md), a first role it can serve, and the source/date used for cost and model availability. Do not duplicate an agent already eligible for that role.

5. **Confirm before writing.** Present the exact roster snapshots and role changes, then wait for explicit approval. A billed model probe requires separate approval immediately before the call.

6. **Append the approved state.** Create missing files from [ROSTER-FORMAT.md](ROSTER-FORMAT.md), append each approved snapshot to `.agents/luucycle/ROSTER.md`, and update the approved role lists in `.agents/luucycle/ROLES.md`. Corrections append a snapshot with `Supersedes`; they do not rewrite history.

7. **Verify roster health.** Run the roster and accessible-CLI checks in `DOCTOR.md`. Fix only entries added in this approved pass; report unrelated existing failures without rewriting them.

**Completion criterion:** every approved snapshot and role change is present, every non-`none` Model/Bypass Flag appears in first-party help, no proposal was silently dropped, and Doctor confirms the new state or names the unresolved field.

## Gotchas

- **No model selection (freebuff-style).** A CLI can be a bare interactive picker with no flags. Record `none - interactive picker` as the Model Flag and say so in Strengths; never invent a flag.
- **A model flag is not a model catalog.** When first-party help exposes a selector but no accepted IDs, record the verified default with `none - auto default` instead of guessing IDs.
- **Billed probes are exceptional.** Use free help/catalog commands first. When acceptance still cannot be established, propose one probe on the cheapest candidate and run it only after the user approves that billed call.
