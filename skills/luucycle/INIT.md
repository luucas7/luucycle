# luucycle init

Branch of luucycle for **bootstrapping the skill library** in a fresh environment. Runs instead of the normal orchestration flow whenever the user asks to install/provision the luucycle prerequisites ("init", "bootstrap", "install skills", "installer les skills"). The manifest below is the user's to fill — never invent sources.

## Steps

1. **Read the manifest.** The table below lists every skill luucycle needs, with its verified install command. Sources were verified against their official docs — keep them, or adjust when a source changes. Never guess a source that is not here; ask the user instead.

| Source | Install command | Why |
| --- | --- | --- |
| `npx skills` (prereq) | `npx skills ...` | The skills installer itself (no setup needed — npx fetches it) |
| `mattpocock/skills` | `npx skills add mattpocock/skills` (interactive: take the engineering + productivity sets, make sure `setup-matt-pocock-skills` is one of them) | spec/tickets/implement/tdd/code-review/grilling/triage/research and the rest of the engineering flow |
| `pbakaus/impeccable` | `npx impeccable install` | The UI Gatekeeper (SKILL.md step 6) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orchestration --global` | Mandatory worker orchestration (dispatches, `worker_done`) |
| `stablyai/orca` | `npx skills add https://github.com/stablyai/orca --skill orca-cli --global` | Worktrees, terminals, full handoffs |

   Gotchas: orca orchestration is an RPC layer over the Orca runtime — no GUI needed, but the runtime must be up (`orca status --json`, start with `orca open --json`; headless: `orca serve`). On Linux outside an Orca-managed terminal, the binary is `orca-ide`, never bare `orca` (GNOME screen reader). Headless hosts can use `orca skills install --skill orchestration` instead of `npx skills add`.

2. **Install each entry.** For every row, run the install command. The install commands themselves handle scope (project vs global, agent target, symlink vs copy) — do not decide for them, pass through what the user picks.

3. **Verify.** Run `npx skills list` and confirm every manifest entry appears. Reinstall anything missing before moving on.

4. **Bootstrap the roster.** Run the `add-cli` branch (ADD-CLI.md) for each newly installed CLI the user wants in the roster. An empty roster is blocking (RULES rule 9) — never finish init with zero `Accessible: true` agents and no add-cli run.

**Completion criterion:** every manifest row is either installed and visible in `skills list` or explicitly dropped by the user, every CLI the user wants on the roster has been through `add-cli`, and `ROSTER.md` has at least one `Accessible: true` agent (or the user accepted an empty roster for a later run).