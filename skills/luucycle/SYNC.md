# luucycle sync

Branch of luucycle for **publishing local skill edits to the canonical repo**. Runs instead of the normal orchestration flow whenever the user asks to publish/update the skill ("sync", "publish", "mettre à jour le skill", "push le skill"). The repo (`luucas7/luucycle`) is the source of truth for the skill — every local edit ends with a sync run.

## Steps

1. **Locate the local copy.** The skill being synced lives at `.agents/skills/luucycle/` in the working repo (or wherever this skill's base directory points, e.g. `~/.config/opencode/skills/luucycle/`). If more than one copy exists, ask which one to publish — never guess.

2. **Compare with the repo.** Clone (or fetch) `https://github.com/luucas7/luucycle` to a scratch directory and diff against the local copy: `diff -r <local> <clone>/skills/luucycle`. Show the user what changed and confirm before pushing — sync publishes, it never silently overwrites.

3. **Copy and commit.** Copy every changed `.md` file into `<clone>/skills/luucycle/`, add any new branch files to the README structure list, then commit with a conventional message describing the change (feat/fix/docs).

4. **Push and verify.** `git push` and confirm the remote is clean. Completion criterion: every locally changed file is on `origin/main`, nothing else in the commit, README structure list matches the file set.

## Gotchas

- The local working copy and the repo can both drift — when they do, resolve by intent (ask the user which side wins) instead of merging blindly.
- Installers (e.g. `npx skills add`) fetch from the repo, not from local — an unpublished edit does not exist for consumers until this branch runs.