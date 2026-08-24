# luucycle init

Branch of luucycle for **bootstrapping the skill library** in a fresh environment. Run it only for `/luucycle init`; otherwise `ASK-LUCAS.md` may recommend it.

## Steps

1. **Resolve the Orca prerequisite.** When the `orchestration` skill is installed, read it before running Orca. Otherwise use its safe bootstrap order: `ORCA_CLI_COMMAND` value → `orca-dev` when `ORCA_DEV_REPO_ROOT` is set → `orca-ide` on Linux → `orca` elsewhere. Reuse the selected executable for every command.
   - `command -v <resolved executable>` must succeed.
   - `<resolved executable> status --json` must report a running runtime; start it only after user approval.
   - `<resolved executable> skills get orchestration` must return the version-matched guide. Treat only an explicit “unknown command” response as an old-CLI case and follow the installed orchestration skill's bounded fallback; report every other failure verbatim.

   If Orca is absent, stop and direct the user to https://www.onorca.dev. On Linux outside an Orca-managed terminal, bare `orca` is never the selected executable.

2. **Resolve the manifest.** The table below records the expected first-party source and candidate install command for every dependency. Before presenting a missing dependency, verify its current command with installed CLI help or current first-party documentation and record the evidence date. When the source cannot be verified, report `UNKNOWN` and ask the user for the authoritative source.

| Source | Candidate install command | Why |
| --- | --- | --- |
| `npx skills` (prereq) | `npx skills ...` | The skills installer itself (no setup needed - npx fetches it) |
| Orca (REQUIRED - step 1) | Orca IDE, or the resolved executable's `serve` command for headless use | The coordination runtime; luucycle cannot dispatch without it |
| `mattpocock/skills` | `npx skills@latest add mattpocock/skills` (interactive: take the engineering + productivity sets, make sure `setup-matt-pocock-skills` is one of them) | spec/tickets/implement/tdd/code-review/grilling/triage/research and the rest of the engineering flow |
| `pbakaus/impeccable` | `npx impeccable install` | The UI Gatekeeper (`IMPLEMENT.md` Gatekeeper step) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orchestration --global` | Mandatory worker orchestration (dispatches, `worker_done`) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orca-cli --global` | Worktrees, terminals, full handoffs |

   Headless hosts may use `<resolved executable> skills install --skill orchestration` instead of `npx skills add`; confirm the exact command from the version-matched guide first.

3. **Confirm and install.** Present the missing entries, verified install commands, evidence, and scopes. Wait for approval, then run only the approved commands and preserve the user's scope choices.

4. **Hand off user-invoked setup.** Ask the user to run `/impeccable init` for UI readiness and `/setup-matt-pocock-skills` for feature-alignment readiness, one at a time in the current project. These commands are user-invoked; present the exact next command and wait for its result instead of simulating the invocation. On resume, inspect the resulting project artifacts and skip completed setup. A setup the user defers leaves only its readiness scope degraded.

5. **Verify runtime, skills, and project setup.** Run checks 1–3 from `DOCTOR.md`. Retry an approved failed install command at most once; if verification still fails, stop with the evidence. Roster failures are expected until step 6.

6. **Bootstrap the roster.** Run the `roster add` branch ([ROSTER-ADD.md](ROSTER-ADD.md)) for each newly installed CLI the user wants in the roster (it creates `.agents/luucycle/` at the repo root if absent). An empty roster is blocking (RULES rule 10) - never finish init with zero `Accessible: true` agents and no `roster add` run.

7. **Run the final audit.** Run all of `DOCTOR.md` after roster bootstrap and report its three readiness scopes.

**Completion criterion:** the resolved Orca runtime and version-matched orchestration guide are available, every approved install command and result is verified, at least one worker is accessible and role-mapped, and Doctor reports the state of implementation, feature alignment, and UI readiness without hiding deferred gaps.
