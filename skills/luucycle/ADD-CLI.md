# luucycle add-cli

Branch of luucycle for **growing the roster**. Runs instead of the normal orchestration flow whenever the user names a new CLI or asks to add models ("add-cli", "add X", "ajouter un modèle"). The roster is the single source of truth for available workers - never bypass this flow by inventing entries.

## Steps

1. **Locate the CLI.** Confirm the binary exists (`which <cmd>`) and record its version (`<cmd> --version`). If it is not on PATH, stop and ask for the path or install command.

2. **Read its docs.** Run `<cmd> --help` plus any relevant subcommand help (`models`, `auth`, `config`, `agent`). Then check its config directory (`~/.<cmd>/`) for a default model or provider settings.
   - **Completion criterion:** you can state how this CLI selects a model (flag, subcommand, picker, config-only) and how permissions are bypassed - or you can state that it can do neither.

3. **Extract the model list.** Priority: a `models` subcommand (e.g. `agy models`) → config default + help examples → web docs (webfetch) when the CLI hides its catalog (codex/copilot-style).
   - **Completion criterion:** you can name the exact loadable model IDs, or you can name the one default with no alternatives.

4. **Propose the three best.** Pick the 3 most interesting models, **spread across cost tiers** - one high (sharpest), one medium (best value), one low (bulk/verification). If fewer than 3 distinct models exist, propose what exists. Each proposal carries: model ID, Model Flag and Bypass Flag (both verified against the CLI's own help), a one-line Strength, a role from `ROLES.md` this agent can serve (without duplicating an agent already on that role's list), and its Cost (low/medium/high).

5. **Confirm before writing.** Present the proposal in ROSTER.md's entry format and wait for the user's explicit approval (RULES rule 1). If the user adjusts the picks, re-present only the changed lines.

6. **Append to the roster.** Add the entries to ROSTER.md in its exact format, in the order approved, and add each agent to its approved role's eligible list in `ROLES.md` (RULES rule 10 - the two files move together). The roster is append-only: never edit an existing entry in the same pass - flag corrections on existing entries are separate, user-requested fixes.

**Completion criterion:** every approved entry is appended to ROSTER.md verbatim and mapped into ROLES.md, every Model/Bypass Flag actually appears in that CLI's help output, the requested cost spread is reflected, and no proposed entry was silently dropped.

## Gotchas

- **No model selection (freebuff-style).** A CLI can be a bare interactive picker with no flags. Record `none - interactive picker` as the Model Flag and say so in Strengths; never invent a flag.
- **`--model` rejects plausible IDs.** Observed on copilot (2026-08-18): the flag parses but refuses every explicit ID (`claude-sonnet-4-6`, `gpt-5.4`, `gpt-5.3-codex`, `gpt-5-mini` all rejected) - only the plan's own model set is accepted. A rejected ID means the flag is unusable: record the entry with the default model and `none - auto default`, and verify by running the flag once (a rejected ID costs nothing beyond the error).
- **Skip the probes that cost money.** A `models` subcommand or `--help` is free; a `-p "..."` probe on the target CLI bills credits - run at most one probe, on the cheapest candidate, only when the flag's acceptance is in doubt.