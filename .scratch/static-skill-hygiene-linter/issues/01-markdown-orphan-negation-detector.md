# 01 — Markdown skill parser and orphan negation detector

**What to build:** Develop a static analysis tool that parses Markdown skill files and detects orphan negative prohibitions that lack a paired positive behavioral target. The tool flags prohibitive phrasing that triggers negative behavioral anchoring bugs and outputs precise file and line diagnostics.

**Blocked by:** None — can start immediately

**Status:** done

- [x] Parser identifies YAML frontmatter, headings, step lists, and prose paragraphs in Markdown skills.
- [x] Detection rule identifies prohibitive terms (`never`, `do not`, `don't`, `prohibit`) lacking adjacent positive target instructions.
- [x] Diagnostics report file path, line number, offending snippet, and actionable guidance for positive refactoring.
- [x] Command exits with code 0 on clean skills and non-zero code when orphan negations are detected.
- [x] Automated tests verify detection on intentionally malformed fixtures and clean passing on valid skills.
