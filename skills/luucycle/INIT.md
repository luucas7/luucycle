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

4. **Inspect, then hand off user-invoked setup.** Before recommending either setup command, read its installed skill and inspect the current project's existing artifacts read-only.
   - For Impeccable, inspect at minimum the resolved `PRODUCT.md`, `DESIGN.md`, and `.impeccable/`. Apply the installed Impeccable skill's own validity and conditionality rules; absence of an artifact that the skill makes optional is not by itself an incomplete setup.
   - For Matt Pocock, derive the complete expected artifact set, content checks, and conditional artifacts from the installed `setup-matt-pocock-skills` skill on every run. Do not substitute a Luucycle-invented checklist.

   Treat each setup independently. When its artifacts are already present and valid, report it briefly as already satisfied, do not recommend its init command, and continue. Only when its artifacts are absent or incomplete, present the exact next command (`/impeccable init` or `/setup-matt-pocock-skills`) and wait for its result instead of simulating the invocation. Handle at most one pending command at a time; on resume, repeat the read-only inspection before deciding whether that setup is satisfied. This gate never overwrites, regenerates, updates, or repairs an existing artifact. A setup the user defers leaves only its readiness scope degraded.

5. **Verify runtime, skills, and project setup.** Run `python3 "<skill-root>/scripts/doctor.py" "<repo-root>" --scope core --json`, then run Task scope with the setup skills the user approved. Retry an approved failed install command at most once; if verification still fails, stop with the evidence. Roster failures are expected until step 6.

6. **Bootstrap the roster.** Run the bare `roster add` branch ([ROSTER-ADD.md](ROSTER-ADD.md)) once so it inventories every installed worker CLI and proposes models for each one (it creates `.agents/luucycle/` at the repo root if absent). Let the user exclude detected CLIs or models at confirmation; do not preselect only the current/default CLI. An empty roster is blocking (RULES rule 10) - never finish init with zero `Enabled: true` agents and no `roster add` run.

7. **Run the final audit.** Run `python3 "<skill-root>/scripts/doctor.py" "<repo-root>" --scope complete --json` after roster bootstrap and report the three readiness scopes from `DOCTOR.md`.

**Completion criterion:** the resolved Orca runtime and version-matched orchestration guide are available, every approved install command and result is verified, at least one worker is enabled, CLI-verified, and role-mapped, and Doctor reports the state of implementation, feature alignment, and UI readiness without hiding deferred gaps.
