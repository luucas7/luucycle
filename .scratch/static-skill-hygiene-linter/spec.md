# Spec: Static Skill Hygiene Linter

## Problem Statement

Agent skills written in Markdown inevitably suffer from documentation degradation over time ("sediment"):
- Negative prohibitions triggering the negation failure mode, anchoring forbidden behaviors in agent attention.
- Verbose descriptions that inflate context load on every conversational turn.
- Operational steps lacking objective, checkable completion criteria, leading to premature task completion.
- Broken internal context pointers and dead cross-references.

Without automated static analysis, checking that a skill adheres to the principles of `/writing-for-agents` relies entirely on manual and subjective human review.

## Solution

A static analysis tool designed specifically for agent skills and documents.

The tool parses Markdown skill documents and evaluates them against core agent document principles:
1. Detecting orphan negative prohibitions that lack paired positive behaviors.
2. Measuring context load budgets against configured thresholds (descriptions and pointer lengths).
3. Verifying that sequential procedural steps end on checkable completion criteria.
4. Ensuring integrity across local context pointers and relative file links.

The tool operates as a fast, zero-dependency CLI script and Python test, failing closed on violations with precise file and line diagnostics.

## User Stories

1. As a skill author, I want a static linter to inspect my Markdown skills against agent documentation principles, so that I can detect behavioral defects before deploying them to models.
2. As a skill author, I want the linter to flag orphan negations (`never`, `don't`, `do not`) that lack a paired positive behavioral target, so that I avoid triggering negative anchoring bugs.
3. As a skill author, I want the linter to measure context load for frontmatter descriptions and router tables, warning when token budgets are exceeded.
4. As an orchestration developer, I want the linter to verify that each numbered step in an execution document ends with an explicit, checkable completion criterion, preventing premature completion.
5. As an orchestration developer, I want all context pointers and relative Markdown links to be validated for target existence, avoiding dead reference bugs.
6. As a CI pipeline, I want the linter to return zero exit codes on compliant documents and non-zero on rule violations, providing clean terminal and machine-readable output.

## Implementation Decisions

- **Architectural Placement & Seam**:
  - Implement as a standalone script alongside repository verification tools, integrated into the repository test suite.
  - The seam is the static file interface: Markdown text streams in, structured diagnostic reports and exit codes stream out.

- **Parsing & Token Extraction**:
  - Use a lightweight, standard library Markdown parsing engine that identifies:
    - YAML frontmatter (keys, values, byte length).
    - Heading hierarchy (h1 through h6).
    - Numbered operational step sequences.
    - Bulleted lists and tabular routers.
    - Context pointers and relative link anchors.
    - Raw prose paragraphs and code blocks.

- **Linter Rule Definitions**:
  - `RULE_HYGIENE_NEGATION`: Flags prohibitive tokens (`never`, `do not`, `don't`, `prohibit`, `forbidden`) unless immediately accompanied by a positive target clause within the same rule boundary.
  - `RULE_CONTEXT_LOAD_BUDGET`: Enforces byte and token length ceilings on frontmatter `description` fields and router summary entries to prevent context window bloating.
  - `RULE_COMPLETION_CRITERIA`: Evaluates numbered step blocks in procedural documents, ensuring the presence of observable, checkable completion criteria (e.g. explicitly defined exit states, receipts, or validation outputs).
  - `RULE_POINTER_INTEGRITY`: Validates that all referenced local documents, sibling files, and anchor fragments exist on disk.

- **Output & Exit Contract**:
  - Terminal mode: human-readable diagnostics with file path, line number, violated rule name, and remediation guidance.
  - JSON mode: structured array of diagnostic objects suitable for CI reporting.
  - Exit code 0 on clean pass; exit code 1 on rule violations.

## Testing Decisions

- **Good Test Definition**:
  - Tests verify that the linter correctly flags intentionally malformed Markdown fixtures (e.g., orphan negations, bloated descriptions, missing completion bounds, broken links) and cleanly passes compliant agent documentation.
  - Tests must never depend on external network access or third-party parsing packages.

- **Modules Tested**:
  - Skill hygiene parser and AST extractor.
  - Individual hygiene rule evaluators.
  - CLI runner and diagnostic formatter.

- **Prior Art**:
  - Existing link checking scripts in the repository verifying relative file paths.

## Out of Scope

- General natural language grammar, typography, or spelling checking unrelated to agent execution.
- Modifying files destructively or applying automatic formatting rewrites without user confirmation.

## Further Notes

- Implements automated enforcement of the tenets specified in [`writing-for-agents`](file:///home/lucas/Documents/luucycle/.agents/skills/writing-for-agents/SKILL.md).
