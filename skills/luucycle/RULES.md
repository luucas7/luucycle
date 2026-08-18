# luucycle rules

Absolute. Read before anything else in a luucycle session. No rule here can be overridden by the task at hand.

1. **Confirm before dispatch.** Present a table of the planned tasks, the skill and model assigned to each, and its cost tier; wait for the user's explicit approval before spawning any worker.

2. **Pause on a missing worker.** When a worker of the requested model cannot be created, stop the affected branch and propose an alternative; resume only after the user approves.

3. **Route through skills.** Decompose the request and hand each task to the skill that owns that kind of work - orchestration for coordination, the matt-pocock engineering skills for spec/tickets/implement/review, impeccable for UI. Reuse what a routed skill already defines; do not improvise a parallel flow.

4. **Gate all UI through impeccable.** Any change that touches the interface passes through impeccable before it is considered complete.

5. **One source of truth.** The roster is the only authority on available models, their cost, and their strengths. This file is the only authority on behaviour. Keep each meaning in exactly one place.

6. **Same process every run.** Predictability is the goal: follow the SKILL.md steps in order on every run, whatever the task.

7. **Roster is append-only.** When the roster is stale, ask what changed and add a new timestamped snapshot; never rewrite a past file.

8. **Skills are always reachable and loaded.** Every task loads its routed skill and follows its instructions. luucycle dispatches through skills; it never reimplements a skill's behaviour inline or routes around it.

9. **Empty roster is blocking.** With zero `Accessible: true` agents, stop the run, signal the empty roster, and propose the `add-cli` branch. Never dispatch, never improvise entries.

10. **ROLES.md owns role → agent mapping.** `ROSTER.md` is the only authority on agent facts; `ROLES.md` is the only authority on which roles each agent serves. The `add-cli` branch updates both in the same pass - a change to one without the other is a violation.

11. **Skill edits require `writing-great-skills`.** Loading it is mandatory before modifying any luucycle file (SKILL.md, RULES.md, ROSTER.md, ROLES.md, ADD-CLI.md, WARNINGS.md, START.md, INIT.md, ASK-LUCAS.md).

9. **Close the loop at session end.** When the session's work is settled and the user asks to close it (or explicitly asks to commit/close), commit the session's own changes (skill/doc updates) on the latest `v*` branch and close the issues the session resolved - with the results in the closing comment. Skill edits are written with `writing-great-skills`; the retrospective always notes any skill improvement made. The user's session-end request counts as the explicit commit ask.
