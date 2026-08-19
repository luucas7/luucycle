# luucycle init

Branch of luucycle for **bootstrapping the skill library** in a fresh environment. Runs instead of the normal orchestration flow whenever the user asks to install/provision the luucycle prerequisites ("init", "bootstrap", "install skills", "installer les skills"). The manifest below is the user's to fill - never invent sources.

## Steps

1. **Check the hard prerequisite: Orca.** luucycle cannot dispatch without the Orca runtime - it is the only supported coordination layer (ROUTING.md routes orchestration through `orca-orchestration`; never substitute another subagent tool). Verify before anything else:
   - Binary present: `which orca-ide` (Linux) or `which orca` (macOS).
   - Runtime up: `orca status --json` must show a running runtime (start with `orca open --json` if needed; headless: `orca serve`).
   - **The orchestration feature must be enabled in Orca's Settings.** The agent cannot always toggle it itself - attempt the check (`orca skills get orchestration`), and if the feature is off or the check fails, STOP and ask the user to enable it in Settings, then wait for confirmation. If Orca is not installed at all, STOP and ask the user to install it first (https://www.onorca.dev) - do not continue init without it.

2. **Read the manifest.** The table below lists every skill luucycle needs, with its verified install command. Sources were verified against their official docs - keep them, or adjust when a source changes. Never guess a source that is not here; ask the user instead.

| Source | Install command | Why |
| --- | --- | --- |
| `npx skills` (prereq) | `npx skills ...` | The skills installer itself (no setup needed - npx fetches it) |
| Orca (REQUIRED - step 1) | Orca IDE, or headless `orca serve` | The coordination runtime; luucycle cannot run without it |
| `mattpocock/skills` | `npx skills@latest add mattpocock/skills` (interactive: take the engineering + productivity sets, make sure `setup-matt-pocock-skills` is one of them) | spec/tickets/implement/tdd/code-review/grilling/triage/research and the rest of the engineering flow |
| `pbakaus/impeccable` | `npx impeccable install` | The UI Gatekeeper (SKILL.md step 6) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orchestration --global` | Mandatory worker orchestration (dispatches, `worker_done`) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orca-cli --global` | Worktrees, terminals, full handoffs |

   Gotchas: on Linux outside an Orca-managed terminal, the binary is `orca-ide`, never bare `orca` (GNOME screen reader). Headless hosts (SSH/CI) can use `orca skills install --skill orchestration` instead of `npx skills add` - they resolve the same `npx` commands and add non-interactive flags.

3. **Install each entry.** For every row, run the install command. The install commands themselves handle scope (project vs global, agent target, symlink vs copy) - do not decide for them, pass through what the user picks.

4. **Post-install setup.** Run `/impeccable init` once after impeccable is installed - it is mandatory: it writes the design context (PRODUCT.md / DESIGN.md) that every gate verdict reads, and init is blocked without it. Also run `/setup-matt-pocock-skills` once per repo (issue tracker, triage labels, domain doc layout) before the first engineering flow.

5. **Verify.** Run `npx skills list` and confirm every manifest entry appears. Reinstall anything missing before moving on.

6. **Bootstrap the roster.** Run the `add-cli` branch (ADD-CLI.md) for each newly installed CLI the user wants in the roster (it creates `.agents/luucycle/` at the repo root if absent). An empty roster is blocking (RULES rule 9) - never finish init with zero `Accessible: true` agents and no add-cli run.

**Completion criterion:** Orca runtime confirmed up with orchestration enabled (or the user explicitly deferred the Settings check), every manifest row is either installed and visible in `skills list` or explicitly dropped by the user, `/impeccable init` ran (or was explicitly deferred by the user), every CLI the user wants on the roster has been through `add-cli`, and `.agents/luucycle/ROSTER.md` (repo root) has at least one `Accessible: true` agent (or the user accepted an empty roster for a later run).