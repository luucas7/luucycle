#!/usr/bin/env python3
"""
Unit tests for the Static Skill Hygiene Linter (check_skill_hygiene.py).
Tests:
- Markdown parser structures (frontmatter, headings, lists, paragraphs, code blocks)
- Orphan negation detection (exact lines, snippets, rule name, message)
- Paired negation allowance (contrastive markers, adjacent directives, compound clauses)
- CLI interface (text mode, JSON mode, exit codes 0 and 1)
- Subsecond and offline execution
"""

import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from skills.luucycle.scripts.check_skill_hygiene import (
    MSG_BROKEN_ANCHOR,
    MSG_BROKEN_TARGET,
    MSG_BUDGET_EXCEEDED,
    MSG_MISSING_COMPLETION_CRITERION,
    MSG_ORPHAN_NEGATION,
    MSG_VAGUE_COMPLETION_BOUND,
    RULE_COMPLETION_CRITERIA,
    RULE_CONTEXT_LOAD_BUDGET,
    RULE_HYGIENE_NEGATION,
    RULE_POINTER_INTEGRITY,
    check_rule_completion_criteria,
    check_rule_context_load_budget,
    check_rule_hygiene_negation,
    check_rule_pointer_integrity,
    lint_markdown_file,
    lint_path,
    main,
    parse_markdown,
)


class TestMarkdownParser(unittest.TestCase):
    """Verifies parsing of Markdown structures with accurate line numbers."""

    def test_parse_frontmatter(self):
        content = """---
name: sample-skill
description: Comprehensive testing skill for agents.
tags:
  - test
  - agent
---
# First Heading
Paragraph text.
"""
        doc = parse_markdown(content, Path("sample.md"))
        fm_nodes = [n for n in doc.nodes if n.node_type == "frontmatter"]
        self.assertEqual(len(fm_nodes), 1)
        fm = fm_nodes[0]
        self.assertEqual(fm.start_line, 1)
        self.assertEqual(fm.end_line, 7)
        self.assertEqual(doc.frontmatter.get("name"), "sample-skill")
        self.assertIn("Comprehensive testing skill", doc.frontmatter.get("description", ""))

    def test_parse_headings(self):
        content = """# Heading 1
Prose paragraph.

## Heading 2
Another paragraph.

### Heading 3
"""
        doc = parse_markdown(content, Path("headings.md"))
        headings = [n for n in doc.nodes if n.node_type == "heading"]
        self.assertEqual(len(headings), 3)

        self.assertEqual(headings[0].metadata["level"], 1)
        self.assertEqual(headings[0].text, "Heading 1")
        self.assertEqual(headings[0].start_line, 1)

        self.assertEqual(headings[1].metadata["level"], 2)
        self.assertEqual(headings[1].text, "Heading 2")
        self.assertEqual(headings[1].start_line, 4)

        self.assertEqual(headings[2].metadata["level"], 3)
        self.assertEqual(headings[2].text, "Heading 3")
        self.assertEqual(headings[2].start_line, 7)

    def test_parse_ordered_and_unordered_lists(self):
        content = """1. First step in the execution sequence.
   Continuation line of step 1.
2. Second step in the sequence.

- Bullet item alpha
- Bullet item beta
  with multiline continuation
"""
        doc = parse_markdown(content, Path("lists.md"))
        list_items = [n for n in doc.nodes if n.node_type == "list_item"]
        self.assertEqual(len(list_items), 4)

        # Step 1
        self.assertTrue(list_items[0].metadata["ordered"])
        self.assertEqual(list_items[0].metadata["number"], 1)
        self.assertEqual(list_items[0].start_line, 1)
        self.assertEqual(list_items[0].end_line, 2)
        self.assertIn("Continuation line", list_items[0].text)

        # Step 2
        self.assertTrue(list_items[1].metadata["ordered"])
        self.assertEqual(list_items[1].metadata["number"], 2)
        self.assertEqual(list_items[1].start_line, 3)

        # Unordered bullets
        self.assertFalse(list_items[2].metadata["ordered"])
        self.assertIsNone(list_items[2].metadata["number"])
        self.assertEqual(list_items[2].start_line, 5)

        self.assertFalse(list_items[3].metadata["ordered"])
        self.assertEqual(list_items[3].start_line, 6)
        self.assertEqual(list_items[3].end_line, 7)

    def test_parse_paragraphs_and_code_blocks(self):
        content = """This is the first paragraph.
It continues on the second line.

```python
# Code block comment
def execute():
    return True
```

This is the second paragraph after the code block.
"""
        doc = parse_markdown(content, Path("blocks.md"))
        paragraphs = [n for n in doc.nodes if n.node_type == "paragraph"]
        code_blocks = [n for n in doc.nodes if n.node_type == "code_block"]

        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(len(code_blocks), 1)

        self.assertEqual(paragraphs[0].start_line, 1)
        self.assertEqual(paragraphs[0].end_line, 2)

        self.assertEqual(code_blocks[0].start_line, 4)
        self.assertEqual(code_blocks[0].end_line, 8)
        self.assertEqual(code_blocks[0].metadata.get("lang"), "python")

        self.assertEqual(paragraphs[1].start_line, 10)
        self.assertEqual(paragraphs[1].end_line, 10)

    def test_parse_tables(self):
        content = """| Field | Type | Description |
| --- | --- | --- |
| id | string | Unique record ID |
| status | string | Current lifecycle state |
"""
        doc = parse_markdown(content, Path("tables.md"))
        tables = [n for n in doc.nodes if n.node_type == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].start_line, 1)
        self.assertEqual(tables[0].end_line, 4)


class TestOrphanNegationDetection(unittest.TestCase):
    """Verifies accurate detection of orphan prohibitions lacking positive targets."""

    def test_detects_never_orphan(self):
        content = """# Guidelines

Never modify the production database directly.
"""
        doc = parse_markdown(content, Path("rules.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.file, "rules.md")
        self.assertEqual(d.line, 3)
        self.assertEqual(d.rule, RULE_HYGIENE_NEGATION)
        self.assertEqual(d.snippet, "Never modify the production database directly.")
        self.assertEqual(d.message, MSG_ORPHAN_NEGATION)

    def test_detects_do_not_orphan(self):
        content = """# Setup

1. Clone the repository.
2. Do not touch configuration files.
3. Start the dev server.
"""
        doc = parse_markdown(content, Path("setup.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.line, 4)
        self.assertEqual(d.rule, RULE_HYGIENE_NEGATION)
        self.assertEqual(d.snippet, "2. Do not touch configuration files.")

    def test_detects_dont_orphan(self):
        content = """# Debugging

Don't delete diagnostic logs.
"""
        doc = parse_markdown(content, Path("debug.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.line, 3)
        self.assertIn("Don't delete diagnostic logs.", d.snippet)

    def test_detects_prohibited_and_forbidden_orphan(self):
        content = """# Security Policy

Direct SSH access is strictly prohibited.

Running untrusted scripts is forbidden.
"""
        doc = parse_markdown(content, Path("security.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(len(diags), 2)
        self.assertEqual(diags[0].line, 3)
        self.assertEqual(diags[1].line, 5)

    def test_detects_orphan_in_frontmatter_description(self):
        content = """---
name: dangerous-skill
description: Do not execute this without root.
---
# Main
Content here.
"""
        doc = parse_markdown(content, Path("fm.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].line, 3)
        self.assertEqual(diags[0].rule, RULE_HYGIENE_NEGATION)


class TestPairedNegationPasses(unittest.TestCase):
    """Verifies that prohibitions paired with positive target behaviors pass cleanly."""

    def test_paired_with_instead(self):
        content = """# Guidelines

Do not edit files directly; use `read_file` and authorized tools instead.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_with_always(self):
        content = """# Deployment

Always verify database health before rollout; never deploy without checking.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_with_must(self):
        content = """# Audit

Audit workers do not edit files; they must inspect code and diffs only.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_with_only(self):
        content = """# Doctor

Doctor is read-only: the script may inspect files and run free CLI help only.
It never installs, updates, starts services, or edits files.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_with_special_phrases(self):
        content = """# Worker Lifecycle

Receiving the compact receipt completes the interaction: release immediately.
For a worker that never reports, re-dispatch once to the fallback in a fresh terminal.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_contrastive_clause(self):
        content = """# Routing

Reuse what a routed skill already defines; do not improvise a parallel flow.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_adjacent_succeeding_sentence(self):
        content = """# Lucas Routing

For an application or product question, do not inspect or analyze the application.
Explain that alignment starts with `/luucycle cook` and give that copyable command.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_adjacent_preceding_sentence(self):
        content = """# Repair Handling

Recommend its repair command first. Still state which command will continue the intended work.
Do not perform the repair automatically.
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_paired_attributive_definition(self):
        content = """| Field | Contract |
| --- | --- |
| `id` | Exact unique record ID, never shortened or replaced by a title |
"""
        doc = parse_markdown(content, Path("ok.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])


class TestCodeBlocksAndInlineIgnored(unittest.TestCase):
    """Verifies that code blocks and inline code literals do not trigger false alerts."""

    def test_fenced_code_block_is_ignored(self):
        content = """# Code Snippet

```python
# Never commit credentials
if not user:
    raise ValueError("do not continue")
```
"""
        doc = parse_markdown(content, Path("code.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])

    def test_inline_code_literal_is_ignored(self):
        content = """# CLI Reference

The argument `never` specifies continuous execution without timeouts.
The flag `do not` is an obsolete synonym for `--dry-run`.
"""
        doc = parse_markdown(content, Path("inline.md"))
        diags = check_rule_hygiene_negation(doc)
        self.assertEqual(diags, [])


class TestContextLoadBudget(unittest.TestCase):
    """Verifies that frontmatter description adheres to context load budgets."""

    def test_compliant_description_passes(self):
        content = """---
name: concise-skill
description: Route luucycle setup, readiness, and multi-worker implementation workflows.
---
# Main
"""
        doc = parse_markdown(content, Path("concise.md"))
        diags = check_rule_context_load_budget(doc)
        self.assertEqual(diags, [])

    def test_bloated_description_tokens_exceeded(self):
        desc = " ".join(["keyword"] * 130)
        content = f"""---
name: bloated-tokens-skill
description: {desc}
---
# Main
"""
        doc = parse_markdown(content, Path("bloated_tokens.md"))
        diags = check_rule_context_load_budget(doc)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.line, 3)
        self.assertEqual(d.rule, RULE_CONTEXT_LOAD_BUDGET)
        self.assertIn("Frontmatter description exceeds context load budget", d.message)
        self.assertIn("Prune always-loaded pointer", d.message)

    def test_bloated_description_chars_exceeded(self):
        desc = "a" * 650
        content = f"""---
name: bloated-chars-skill
description: {desc}
---
# Main
"""
        doc = parse_markdown(content, Path("bloated_chars.md"))
        diags = check_rule_context_load_budget(doc)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.line, 3)
        self.assertEqual(d.rule, RULE_CONTEXT_LOAD_BUDGET)
        self.assertIn("650 characters", d.message)

    def test_configurable_limits_via_args(self):
        content = """---
name: medium-skill
description: Moderate length description with exactly fifteen words for checking custom token limits.
---
# Main
"""
        doc = parse_markdown(content, Path("medium.md"))
        # Passes under default (120 tokens, 600 chars)
        self.assertEqual(check_rule_context_load_budget(doc), [])
        # Fails under strict budget (max_tokens=10)
        strict_diags = check_rule_context_load_budget(doc, max_tokens=10, max_chars=600)
        self.assertEqual(len(strict_diags), 1)
        self.assertEqual(strict_diags[0].rule, RULE_CONTEXT_LOAD_BUDGET)

    def test_missing_description_passes(self):
        content = """---
name: no-desc-skill
version: 1.0.0
---
# Main
"""
        doc = parse_markdown(content, Path("no_desc.md"))
        self.assertEqual(check_rule_context_load_budget(doc), [])

    def test_no_frontmatter_passes(self):
        content = """# Pure Markdown Document
No frontmatter at all.
"""
        doc = parse_markdown(content, Path("no_fm.md"))
        self.assertEqual(check_rule_context_load_budget(doc), [])


class TestCompletionCriteria(unittest.TestCase):
    """Verifies that operational step sequences conclude with checkable completion criteria."""

    def test_steps_with_explicit_completion_criterion_pass(self):
        content = """# Add Worker

## Steps

1. **Inventory CLIs.** Run discovery on candidate CLIs.
   - **Completion criterion:** Every installed command is identified.
2. **Catalog models.** Query CLI help or catalog files.
   - **Completion criterion:** Model list established or recorded as UNKNOWN.
"""
        doc = parse_markdown(content, Path("steps_explicit.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(diags, [])

    def test_steps_with_terminal_markers_pass(self):
        content = """# Execution Run

## Steps

1. **Audit dependencies.** Inspect installed packages; stop on missing dependency.
2. **Execute build.** Run compiler until exit code 0.
3. **Dispatch worker.** Await compact receipt; trigger terminal sealing immediately.
"""
        doc = parse_markdown(content, Path("steps_markers.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(diags, [])

    def test_steps_in_document_with_terminal_criterion_pass(self):
        content = """# Cook Feature

## Steps

1. **Verify alignment readiness.** Run scoped audit in doctor.
2. **Start alignment.** Load and run interactive grilling.
3. **Hand off planned work.** Give the exact command for next phase.

**Completion criterion:** The topic is cooked. Alignment readiness is settled and artifacts verified.
"""
        doc = parse_markdown(content, Path("cook_steps.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(diags, [])

    def test_operational_steps_lacking_completion_bounds_fail(self):
        content = """# Vague Workflow

## Steps

1. **Review files.** Look at the codebase.
2. **Edit files.** Make updates to configuration.
"""
        doc = parse_markdown(content, Path("vague_workflow.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(len(diags), 2)

        self.assertEqual(diags[0].line, 5)
        self.assertEqual(diags[0].rule, RULE_COMPLETION_CRITERIA)
        self.assertIn("1. **Review files.**", diags[0].snippet)
        self.assertEqual(diags[0].message, MSG_MISSING_COMPLETION_CRITERION)

        self.assertEqual(diags[1].line, 6)
        self.assertEqual(diags[1].rule, RULE_COMPLETION_CRITERIA)
        self.assertIn("2. **Edit files.**", diags[1].snippet)

    def test_vague_bounds_trigger_alert(self):
        content = """# Premature Completion Risk

## Steps

1. **Inspect codebase.** Read files until understanding reached.

**Completion criterion:** Done.
"""
        doc = parse_markdown(content, Path("vague_bound.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].line, 5)
        self.assertEqual(diags[0].rule, RULE_COMPLETION_CRITERIA)
        self.assertIn("understanding reached", diags[0].message)

    def test_non_operational_reference_sections_ignored(self):
        content = """# Repository Rules

1. **Implementation is explicit.** Authorizes coordination only.
2. **Approve each selected phase.** Wait for user sign-off.
"""
        doc = parse_markdown(content, Path("RULES.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(diags, [])

    def test_user_stories_and_overview_sections_ignored(self):
        content = """# Product Specification

## Overview

1. As a user, I want a fast static linter.
2. Provide high precision and zero false positives.

## User Stories

1. As a skill author, I want to catch orphan prohibitions.
2. As an engineer, I want context pointers validated on disk.

## Requirements

1. Must support Python 3.10+.
2. Zero external dependencies.
"""
        doc = parse_markdown(content, Path("spec.md"))
        diags = check_rule_completion_criteria(doc)
        self.assertEqual(diags, [])


class TestPointerIntegrity(unittest.TestCase):
    """Verifies that relative Markdown links and anchor fragments exist on disk."""

    def test_valid_relative_links_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            target = tmppath / "target.md"
            target.write_text("# Target\nContent here.\n", encoding="utf-8")

            source = tmppath / "source.md"
            source_content = f"# Source\nSee [target]({target.name}) for details.\n"
            source.write_text(source_content, encoding="utf-8")

            doc = parse_markdown(source_content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(diags, [])

    def test_valid_anchor_links_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            target = tmppath / "guide.md"
            target.write_text("# Guide\n\n## Script Output\nDetails.\n", encoding="utf-8")

            source = tmppath / "source.md"
            source_content = "# Source\nSee [guide](guide.md#script-output).\n"
            source.write_text(source_content, encoding="utf-8")

            doc = parse_markdown(source_content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(diags, [])

    def test_valid_same_file_anchor_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "doc.md"
            content = "# Main\n\nJump to [steps](#steps).\n\n## Steps\nContent.\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(diags, [])

    def test_external_links_ignored(self):
        content = """# External Links
See [website](https://example.com/docs), [http link](http://example.com), and [email](mailto:lucas@example.com).
"""
        doc = parse_markdown(content, Path("links.md"))
        diags = check_rule_pointer_integrity(doc)
        self.assertEqual(diags, [])

    def test_broken_file_link_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.md"
            content = "# Source\nSee [missing file](nonexistent_reference.md).\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(len(diags), 1)
            d = diags[0]
            self.assertEqual(d.line, 2)
            self.assertEqual(d.rule, RULE_POINTER_INTEGRITY)
            self.assertIn("nonexistent_reference.md", d.message)
            self.assertEqual(d.snippet, "[missing file](nonexistent_reference.md)")

    def test_broken_anchor_link_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            target = tmppath / "target.md"
            target.write_text("# Target Document\n\n## Valid Section\n", encoding="utf-8")

            source = tmppath / "source.md"
            content = "# Source\nSee [bad section](target.md#missing-section).\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(len(diags), 1)
            d = diags[0]
            self.assertEqual(d.line, 2)
            self.assertEqual(d.rule, RULE_POINTER_INTEGRITY)
            self.assertIn("missing-section", d.message)

    def test_inline_code_links_ignored(self):
        content = """# Documentation
Code example showing link format: `[example](nonexistent.md)`.
"""
        doc = parse_markdown(content, Path("code_link.md"))
        diags = check_rule_pointer_integrity(doc)
        self.assertEqual(diags, [])

    def test_valid_file_uri_link_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            target = tmppath / "referenced.md"
            target.write_text("# Target Section\nValid content here.\n", encoding="utf-8")

            source = tmppath / "source.md"
            target_uri = f"file://{target.resolve()}"
            target_uri_with_anchor = f"file://{target.resolve()}#target-section"
            content = f"# Source\nSee [valid target]({target_uri}) and [with anchor]({target_uri_with_anchor}).\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(diags, [])

    def test_missing_file_uri_link_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.md"
            missing_path = "/nonexistent/path/to/missing_file.md"
            missing_uri = f"file://{missing_path}"
            content = f"# Source\nSee [missing target]({missing_uri}).\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(len(diags), 1)
            d = diags[0]
            self.assertEqual(d.line, 2)
            self.assertEqual(d.rule, RULE_POINTER_INTEGRITY)
            self.assertIn(missing_path, d.message)
            self.assertEqual(d.snippet, f"[missing target]({missing_uri})")

    def test_file_uri_broken_anchor_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            target = tmppath / "referenced.md"
            target.write_text("# Target Section\nValid content here.\n", encoding="utf-8")

            source = tmppath / "source.md"
            target_uri_bad_anchor = f"file://{target.resolve()}#missing-section"
            content = f"# Source\nSee [bad anchor]({target_uri_bad_anchor}).\n"
            source.write_text(content, encoding="utf-8")

            doc = parse_markdown(content, source)
            diags = check_rule_pointer_integrity(doc)
            self.assertEqual(len(diags), 1)
            d = diags[0]
            self.assertEqual(d.line, 2)
            self.assertEqual(d.rule, RULE_POINTER_INTEGRITY)
            self.assertIn("missing-section", d.message)

    def test_agent_internal_schemes_ignored(self):
        content = """# Orchestration Conversation
Refer to subagent trace at [subagent run](conversation://48b54617-8a0d-40ef-9a90-ccc2afe94161).
"""
        doc = parse_markdown(content, Path("agent_trace.md"))
        diags = check_rule_pointer_integrity(doc)
        self.assertEqual(diags, [])


class TestCommandLineInterface(unittest.TestCase):
    """Verifies CLI behavior: exit codes, human-readable formatting, and JSON output."""

    def test_cli_clean_file_text_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Clean Skill\n\nPrompt the positive target behavior.\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 0)
            self.assertIn("All skills pass hygiene checks! (0 violations)", buf.getvalue())

    def test_cli_clean_file_json_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Clean Skill\n\nPrompt the positive target behavior.\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name, "--json"])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 0)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(parsed, [])

    def test_cli_orphan_violation_text_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Bad Skill\n\nNever delete database backups.\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 1)
            output = buf.getvalue()
            self.assertIn("RULE_HYGIENE_NEGATION", output)
            self.assertIn(MSG_ORPHAN_NEGATION, output)
            self.assertIn("Never delete database backups.", output)
            self.assertIn("Found 1 skill hygiene violation", output)

    def test_cli_orphan_violation_json_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Bad Skill\n\nNever delete database backups.\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name, "--json"])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 1)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(len(parsed), 1)
            item = parsed[0]
            self.assertEqual(item["file"], tmp.name)
            self.assertEqual(item["line"], 3)
            self.assertEqual(item["rule"], RULE_HYGIENE_NEGATION)
            self.assertEqual(item["snippet"], "Never delete database backups.")
            self.assertEqual(item["message"], MSG_ORPHAN_NEGATION)

    def test_cli_nonexistent_path(self):
        buf = io.StringIO()
        old_stderr = sys.stderr
        try:
            sys.stderr = buf
            exit_code = main(["/nonexistent/skill_path/SKILL.md"])
        finally:
            sys.stderr = old_stderr

        self.assertEqual(exit_code, 2)
        self.assertIn("Path does not exist", buf.getvalue())

    def test_cli_budget_violation_json_mode(self):
        desc = " ".join(["token"] * 130)
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write(f"---\nname: bloated\ndescription: {desc}\n---\n# Main\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name, "--json"])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 1)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["rule"], RULE_CONTEXT_LOAD_BUDGET)
            self.assertIn("exceeds context load budget", parsed[0]["message"])

    def test_cli_custom_budget_flags(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("---\nname: small\ndescription: Ten words description that exceeds a tiny limit of five words.\n---\n# Main\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                # Default limit (120) passes
                exit_code_default = main([tmp.name])
            finally:
                sys.stdout = old_stdout
            self.assertEqual(exit_code_default, 0)

            buf_strict = io.StringIO()
            try:
                sys.stdout = buf_strict
                exit_code_strict = main([tmp.name, "--max-description-tokens", "5"])
            finally:
                sys.stdout = old_stdout
            self.assertEqual(exit_code_strict, 1)
            self.assertIn("RULE_CONTEXT_LOAD_BUDGET", buf_strict.getvalue())

    def test_cli_completion_criteria_violation_text_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Bad Workflow\n\n## Steps\n\n1. **Unbounded step.** Do some action.\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 1)
            self.assertIn("RULE_COMPLETION_CRITERIA", buf.getvalue())
            self.assertIn("Operational step lacks verifiable completion criterion", buf.getvalue())

    def test_cli_broken_pointer_violation_text_mode(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("# Bad Links\n\nReference [nonexistent](missing_target_file.md).\n")
            tmp.flush()

            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                exit_code = main([tmp.name])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(exit_code, 1)
            self.assertIn("RULE_POINTER_INTEGRITY", buf.getvalue())
            self.assertIn("missing_target_file.md", buf.getvalue())


class TestExistingSkillsCompliance(unittest.TestCase):
    """Verifies that all existing repository skills pass the hygiene linter."""

    def test_skills_luucycle_is_clean(self):
        luucycle_dir = Path(__file__).resolve().parent.parent / "skills" / "luucycle"
        self.assertTrue(luucycle_dir.exists(), f"Directory not found: {luucycle_dir}")

        diagnostics, files_count = lint_path(luucycle_dir)
        self.assertGreaterEqual(files_count, 13)
        self.assertEqual(
            diagnostics,
            [],
            f"Expected 0 violations in skills/luucycle, got: {[d.to_dict() for d in diagnostics]}",
        )

    def test_execution_speed_subsecond_offline(self):
        luucycle_dir = Path(__file__).resolve().parent.parent / "skills" / "luucycle"
        start_time = time.perf_counter()
        diagnostics, files_count = lint_path(luucycle_dir)
        elapsed = time.perf_counter() - start_time

        self.assertEqual(len(diagnostics), 0)
        self.assertLess(
            elapsed,
            1.0,
            f"Hygiene check took {elapsed:.3f}s, expected < 1.0s",
        )


if __name__ == "__main__":
    unittest.main()
