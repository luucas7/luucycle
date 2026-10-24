# 02 — Context load budget and completion criteria verifier

**What to build:** Extend the static skill linter to evaluate context load token/character budgets on always-loaded descriptions and verify that all sequential operational steps conclude with checkable, observable completion criteria.

**Blocked by:** 01 — Markdown skill parser and orphan negation detector

**Status:** done

- [x] Linter measures character and token length of frontmatter `description` fields, enforcing a configurable context load ceiling.
- [x] Linter checks numbered operational steps, flagging steps that lack explicit, checkable completion criteria.
- [x] Context pointers and relative Markdown links are verified for target file existence.
- [x] Tool supports both human-readable terminal output and structured JSON output for continuous integration.
- [x] Unit tests cover budget violations, missing completion bounds, and broken internal links.
