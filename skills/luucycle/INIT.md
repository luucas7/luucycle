# luucycle init

Branch of luucycle for **bootstrapping the skill library** in a fresh environment. Runs instead of the normal orchestration flow whenever the user asks to install/provision the luucycle prerequisites ("init", "bootstrap", "install skills", "installer les skills"). The manifest below is the user's to fill — never invent sources.

## Steps

1. **Read the manifest.** The table below lists every skill luucycle needs (impeccable, orca-orchestration, the matt-pocock engineering set, etc.). It is intentionally empty — ask the user for each source (repo URL or `owner/repo` shorthand) and fill it in before running anything. Never guess a source.

| Source | Skill | Why |
| --- | --- | --- |
|  |  |  |

2. **Install each entry.** For every filled row, run the CLI install for that source. The install commands themselves handle scope (project vs global, agent target, symlink vs copy) — do not decide for them, pass through what the user picks:

```bash
npx skills add <source> --skill <skill-name>
```

3. **Verify.** Run `npx skills list` and confirm every manifest entry appears. Reinstall anything missing before moving on.

4. **Bootstrap the roster.** Run the `add-cli` branch (ADD-CLI.md) for each newly installed CLI the user wants in the roster. An empty roster is blocking (RULES rule 9) — never finish init with zero `Accessible: true` agents and no add-cli run.

**Completion criterion:** every manifest row is either installed and visible in `skills list` or explicitly dropped by the user, every CLI the user wants on the roster has been through `add-cli`, and `ROSTER.md` has at least one `Accessible: true` agent (or the user accepted an empty roster for a later run).