# luucycle Roles

Single source of truth for role → agent mapping. A role = task type + ordered eligible agents + context template + output format. `ROSTER.md` holds agent facts (command, flags, cost) — never repeat them here. The `add-cli` branch (ADD-CLI.md step 6) appends agents to ROSTER.md **and** to the eligible lists below — both files stay in sync.

A role is always an ordered list, never a single agent: take the first `Accessible: true` agent on the list (fallback is silent, RULES rule 2). Agents may serve several roles.

| Role | When | Context to inject | Output format | Eligible agents (first = best) |
| --- | --- | --- | --- | --- |
| `verifier` | double-checks, review passes, gate passes | diff + checklist + the review skill's verdict rules | one line per finding: `path:line: severity: problem. fix.` | Deepseek V4 Flash, Gemini 3.7 Flash, freebuff |
| `builder` | feature work, TDD, mid-complexity implementation | spec + target files + conventions | diff receipt: files touched, what changed, risk | Luna, Gemini Pro 3.1, Gemini 3.7 Flash, freebuff |
| `architect` | complex reasoning, systemic refactors, deep debugging | full context + constraints + stakes | plan: approach, files, risks, effort | Sol, Claude Opus 4.6, Kimi K3 |
| `researcher` | huge contexts, full-codebase audits, API docs | documents / codebase to absorb + question | synthesis with precise answers and sources | Kimi K3, Claude Opus 4.6 |
| `scaffolder` | boilerplate, scripts, docs, zero-shot easy tasks | raw spec only, no history | delivered files + one-line summary | deepseek-flash, GPT-5 mini |
