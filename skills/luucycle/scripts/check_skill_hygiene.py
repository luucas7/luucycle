#!/usr/bin/env python3
"""
Static Skill Hygiene Linter.

Parses Markdown skill files and evaluates them against core agent document principles:
- RULE_HYGIENE_NEGATION: Flags orphan negative prohibitions that lack paired positive behaviors.
  ("Prompt the positive" - writing-for-agents).
- RULE_CONTEXT_LOAD_BUDGET: Enforces token and character budget on frontmatter descriptions
  ("Context pointers", "The two loads", "Pruning" - writing-for-agents).
- RULE_COMPLETION_CRITERIA: Enforces checkable, observable completion criteria on operational step sequences
  ("Steps and completion criteria" - writing-for-agents).
- RULE_POINTER_INTEGRITY: Validates local context pointers, sibling files, and anchor fragments on disk
  ("Context pointers" - writing-for-agents).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

RULE_HYGIENE_NEGATION = "RULE_HYGIENE_NEGATION"
RULE_CONTEXT_LOAD_BUDGET = "RULE_CONTEXT_LOAD_BUDGET"
RULE_COMPLETION_CRITERIA = "RULE_COMPLETION_CRITERIA"
RULE_POINTER_INTEGRITY = "RULE_POINTER_INTEGRITY"

MSG_ORPHAN_NEGATION = (
    "Orphan negation: pair prohibition with an explicit positive target behavior "
    "('Prompt the positive' - writing-for-agents)."
)
MSG_BUDGET_EXCEEDED = (
    "Frontmatter description exceeds context load budget: {tokens} tokens, {chars} characters "
    "(budget: max {max_tokens} tokens, {max_chars} characters). Prune always-loaded pointer: "
    "front-load leading words, collapse synonyms into one trigger per branch, cut identity "
    "the body already carries, and prune no-ops ('Context pointers', 'The two loads', 'Pruning' - writing-for-agents)."
)
MSG_MISSING_COMPLETION_CRITERION = (
    "Operational step lacks verifiable completion criterion: steps must conclude with an "
    "observable termination condition or exit state ('Steps and completion criteria' - writing-for-agents)."
)
MSG_VAGUE_COMPLETION_BOUND = (
    'Operational step contains vague completion bound ("{bound}"): sharpen the bound '
    "into an observable, checkable condition ('Steps and completion criteria' - writing-for-agents)."
)
MSG_BROKEN_TARGET = (
    "Broken context pointer: target file '{target}' does not exist on disk "
    "('Context pointers' - writing-for-agents)."
)
MSG_BROKEN_ANCHOR = (
    "Broken context pointer: anchor fragment '#{anchor}' not found in target file '{target}' "
    "('Context pointers' - writing-for-agents)."
)

PROHIBITIVE_PATTERN = re.compile(
    r"\b(never|do\s+not|don['’]t|prohibit(?:s|ed|ing|ion|ions)?|forbidden)\b",
    re.IGNORECASE,
)

CONTRASTIVE_MARKERS_PATTERN = re.compile(
    r"\b(instead|always|must|only|rather\s+than|rather|prefer(?:s|red|ring)?|preferably|"
    r"alternative(?:s)?|alternatively|require(?:s|d|ment|ments)?|ensure(?:s|d)?|unless|except(?:s|ed|ing|ion|ions)?|otherwise)\b",
    re.IGNORECASE,
)

SPECIAL_PHRASES_PATTERN = re.compile(
    r"\b(dispatched\s+to\s+a\s+fresh\s+terminal|dispatch(?:es|ed|ing)?\s+to\s+a\s+fresh\s+terminal|"
    r"release\s+immediately|immediately\s+release)\b",
    re.IGNORECASE,
)

POSITIVE_DIRECTIVE_PATTERN = re.compile(
    r"\b(use|uses|utilize|utilizes|run|runs|execute|executes|inspect|inspects|read|reads|query|queries|"
    r"explain|explains|state|states|tell|tells|describe|describes|report|reports|record|records|log|logs|"
    r"propose|proposes|present|presents|recommend|recommends|suggest|suggests|create|creates|generate|generates|"
    r"write|writes|build|builds|preserve|preserves|retain|retains|keep|keeps|maintain|maintains|"
    r"release|releases|terminate|terminates|close|closes|seal|seals|dispatch|dispatches|re-dispatch|re-dispatches|"
    r"route|routes|forward|forwards|verify|verifies|validate|validates|check|checks|test|tests|confirm|confirms|"
    r"assert|asserts|stop|stops|pause|pauses|halt|halts|wait|waits|load|loads|import|imports|fetch|fetches|"
    r"pull|pulls|ask|asks|prompt|prompts|elicit|elicits|finish|finishes|conclude|concludes|complete|completes|"
    r"return|returns|yield|yields|output|outputs|derive|derives|extract|extracts|treat|treats|handle|handles|"
    r"combine|combines|reuse|reuses|diagnose|diagnoses|repair|repairs|re-run|re-runs|follow|follows|apply|applies|"
    r"adhere|adheres|substitute|substitutes|replace|replaces|choose|chooses|select|selects|pick|picks|"
    r"open|opens|show|shows|display|displays|let|continue|continues|obtain|obtains|process|processes|"
    r"exercise|exercises|omit|omits|edit|edits|modify|modifies|update|updates)\b",
    re.IGNORECASE,
)

VAGUE_BOUNDS_PATTERN = re.compile(
    r"\b(understanding\s+reached|sufficient\s+understanding|explore\s+and\s+understand|as\s+you\s+see\s+fit)\b",
    re.IGNORECASE,
)

TERMINAL_MARKERS_PATTERN = re.compile(
    r"\b("
    r"completion\s+criteri(?:on|a)|criterion:|criteria:|completion\s+condition"
    r"|until"
    r"|complete(?:s|d)?\s+(?:only\s+)?when"
    r"|return(?:s|ed)?"
    r"|stop(?:s)?\s+(?:on|at|with|and)"
    r"|continue(?:s|d|ing)?\s+(?:on|with|from)"
    r"|receipt(?:s)?"
    r"|terminal\s+sealing|sealing\s+the\s+session|seal(?:s|ed)?"
    r"|observable\s+exit\s+state|exit\s+state|exit\s+code"
    r"|must\s+(?:succeed|return|report|exist|be)"
    r"|wait\s+for"
    r"|pause\s+(?:and\s+ask|the\s+task|on)"
    r"|conclude(?:s)?\s+with"
    r"|state\s+the|report\s+the|show\s+one\s+row"
    r"|blocking"
    r"|never\s+finish"
    r"|checkpoint"
    r")\b",
    re.IGNORECASE,
)

DOC_COMPLETION_PATTERN = re.compile(
    r"(?:^#+\s*completion\s+criteri(?:on|a)|\*\*(?:completion\s+criteri(?:on|a)|complete\s+only\s+when):?\*\*|\bcompletion\s+criteri(?:on|a):)",
    re.IGNORECASE | re.MULTILINE,
)

NON_OPERATIONAL_HEADING_PATTERN = re.compile(
    r"\b(rules|guardrails|reference|policies|faq|table\s+of\s+contents|changelog|user\s+stories|stories|overview|what\s+it\s+does|structure|requirements|install|development)\b",
    re.IGNORECASE,
)

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass
class LineRef:
    line_number: int  # 1-based
    text: str


@dataclass
class MarkdownNode:
    node_type: str  # 'frontmatter', 'heading', 'list_item', 'paragraph', 'code_block', 'table', 'divider'
    start_line: int
    end_line: int
    text: str
    lines: List[LineRef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarkdownDocument:
    path: Path
    nodes: List[MarkdownNode]
    frontmatter: Dict[str, Any]
    raw_text: str
    lines: List[str]


@dataclass
class Diagnostic:
    file: str
    line: int
    rule: str
    snippet: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "rule": self.rule,
            "snippet": self.snippet,
            "message": self.message,
        }


def parse_frontmatter_yaml(lines: List[str]) -> Tuple[Dict[str, Any], int, int]:
    """
    Extract key-values from frontmatter between opening and closing ---.
    Returns (data_dict, start_line, end_line).
    """
    if not lines or lines[0].strip() != "---":
        return {}, 0, 0

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, 0, 0

    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_val_lines: List[str] = []

    for line in lines[1:end_idx]:
        # Check for key: value
        kv_match = re.match(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)$", line)
        if kv_match:
            if current_key:
                data[current_key] = "\n".join(current_val_lines).strip()
            current_key = kv_match.group(1)
            first_val = kv_match.group(2).strip()
            current_val_lines = [first_val] if first_val else []
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            current_val_lines.append(line.strip())

    if current_key:
        data[current_key] = "\n".join(current_val_lines).strip()

    return data, 1, end_idx + 1


def parse_markdown(content: str, path: Optional[Path] = None) -> MarkdownDocument:
    """
    Parses a Markdown document into structured nodes:
    - frontmatter
    - headings (# through ######)
    - list items (ordered and unordered, including multiline continuations)
    - paragraphs
    - fenced code blocks (``` or ~~~)
    - tables
    - dividers
    """
    raw_lines = content.splitlines()
    nodes: List[MarkdownNode] = []
    doc_path = path or Path("<anonymous>")

    total_lines = len(raw_lines)
    idx = 0

    # 1. Frontmatter
    frontmatter_data, fm_start, fm_end = parse_frontmatter_yaml(raw_lines)
    if fm_end > 0:
        fmlines = [LineRef(i + 1, raw_lines[i]) for i in range(fm_start - 1, fm_end)]
        nodes.append(
            MarkdownNode(
                node_type="frontmatter",
                start_line=fm_start,
                end_line=fm_end,
                text="\n".join(raw_lines[fm_start - 1 : fm_end]),
                lines=fmlines,
                metadata={"data": frontmatter_data},
            )
        )
        idx = fm_end

    in_table = False
    table_lines: List[LineRef] = []

    def flush_table() -> None:
        nonlocal in_table, table_lines
        if in_table and table_lines:
            nodes.append(
                MarkdownNode(
                    node_type="table",
                    start_line=table_lines[0].line_number,
                    end_line=table_lines[-1].line_number,
                    text="\n".join(l.text for l in table_lines),
                    lines=list(table_lines),
                )
            )
            table_lines = []
            in_table = False

    while idx < total_lines:
        line_num = idx + 1
        line = raw_lines[idx]
        stripped = line.strip()

        # Blank line
        if not stripped:
            flush_table()
            idx += 1
            continue

        # Fenced code block
        fence_match = re.match(r"^(\s*)(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            flush_table()
            fence_char = fence_match.group(2)[0]
            fence_len = len(fence_match.group(2))
            info_str = fence_match.group(3).strip()
            code_lines = [LineRef(line_num, line)]
            start_l = line_num
            idx += 1
            while idx < total_lines:
                c_line_num = idx + 1
                c_line = raw_lines[idx]
                code_lines.append(LineRef(c_line_num, c_line))
                close_match = re.match(r"^\s*(`{3,}|~{3,})\s*$", c_line)
                if (
                    close_match
                    and close_match.group(1)[0] == fence_char
                    and len(close_match.group(1)) >= fence_len
                ):
                    idx += 1
                    break
                idx += 1
            nodes.append(
                MarkdownNode(
                    node_type="code_block",
                    start_line=start_l,
                    end_line=code_lines[-1].line_number,
                    text="\n".join(l.text for l in code_lines),
                    lines=code_lines,
                    metadata={"lang": info_str},
                )
            )
            continue

        # Table row
        if "|" in line:
            in_table = True
            table_lines.append(LineRef(line_num, line))
            idx += 1
            continue
        else:
            flush_table()

        # Heading (# through ######)
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            nodes.append(
                MarkdownNode(
                    node_type="heading",
                    start_line=line_num,
                    end_line=line_num,
                    text=heading_text,
                    lines=[LineRef(line_num, line)],
                    metadata={"level": level},
                )
            )
            idx += 1
            continue

        # Thematic break / divider
        if re.match(r"^(?:---|\*\*\*|___)\s*$", stripped):
            nodes.append(
                MarkdownNode(
                    node_type="divider",
                    start_line=line_num,
                    end_line=line_num,
                    text=stripped,
                    lines=[LineRef(line_num, line)],
                )
            )
            idx += 1
            continue

        # List item (ordered or unordered)
        list_match = re.match(r"^(\s*)(?:(\d+)[.)]|[-*+])\s+(.*)$", line)
        if list_match:
            is_ordered = list_match.group(2) is not None
            order_num = int(list_match.group(2)) if is_ordered else None
            indent_len = len(list_match.group(1))
            item_lines = [LineRef(line_num, line)]
            start_l = line_num
            idx += 1
            # Gather continuation lines
            while idx < total_lines:
                c_line = raw_lines[idx]
                c_stripped = c_line.strip()
                if not c_stripped:
                    break
                # If it's a new list item, heading, divider, table, or code block, stop
                if (
                    re.match(r"^(\s*)(?:(\d+)[.)]|[-*+])\s+", c_line)
                    or re.match(r"^#{1,6}\s+", c_stripped)
                    or re.match(r"^(?:---|\*\*\*|___)\s*$", c_stripped)
                    or re.match(r"^(\s*)(`{3,}|~{3,})", c_line)
                    or "|" in c_line
                ):
                    break
                # Indented continuation or directly adjacent sentence line
                item_lines.append(LineRef(idx + 1, c_line))
                idx += 1

            nodes.append(
                MarkdownNode(
                    node_type="list_item",
                    start_line=start_l,
                    end_line=item_lines[-1].line_number,
                    text=" ".join(l.text.strip() for l in item_lines),
                    lines=item_lines,
                    metadata={"ordered": is_ordered, "number": order_num, "indent": indent_len},
                )
            )
            continue

        # Paragraph
        para_lines = [LineRef(line_num, line)]
        start_l = line_num
        idx += 1
        while idx < total_lines:
            c_line = raw_lines[idx]
            c_stripped = c_line.strip()
            if not c_stripped:
                break
            if (
                re.match(r"^#{1,6}\s+", c_stripped)
                or re.match(r"^(\s*)(?:(\d+)[.)]|[-*+])\s+", c_line)
                or re.match(r"^(?:---|\*\*\*|___)\s*$", c_stripped)
                or re.match(r"^(\s*)(`{3,}|~{3,})", c_line)
                or "|" in c_line
            ):
                break
            para_lines.append(LineRef(idx + 1, c_line))
            idx += 1

        nodes.append(
            MarkdownNode(
                node_type="paragraph",
                start_line=start_l,
                end_line=para_lines[-1].line_number,
                text=" ".join(l.text.strip() for l in para_lines),
                lines=para_lines,
            )
        )

    flush_table()

    return MarkdownDocument(
        path=doc_path,
        nodes=nodes,
        frontmatter=frontmatter_data,
        raw_text=content,
        lines=raw_lines,
    )


def split_sentences(text: str) -> List[str]:
    """
    Split text into distinct sentences while preserving common abbreviations.
    """
    pattern = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\betc)(?<=[.!?])\s+(?=[A-Z0-9*#`\"\x27])"
    sentences = [s.strip() for s in re.split(pattern, text) if s.strip()]
    return sentences if sentences else ([text.strip()] if text.strip() else [])


def is_inside_inline_code(text: str, match_start: int, match_end: int) -> bool:
    """
    Returns True if the character match range is enclosed in backticks (`...`).
    """
    before = text[:match_start]
    backticks_before = before.count("`")
    after = text[match_end:]
    return (backticks_before % 2 == 1) and ("`" in after)


def is_paired_with_positive_target(
    sentence: str, prev_sentence: Optional[str] = None, next_sentence: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Determines if a prohibition is paired with an explicit positive target behavior.
    Returns (is_paired, reason).
    """
    # 1. Contrastive / target markers in the same sentence
    if CONTRASTIVE_MARKERS_PATTERN.search(sentence):
        return True, "contrastive_marker"

    # 2. Specific domain phrases explicitly defining positive behaviors
    if SPECIAL_PHRASES_PATTERN.search(sentence):
        return True, "special_positive_phrase"

    # 3. Compound sentence with contrastive punctuation (; or : or , but or , rather than)
    if ";" in sentence or ":" in sentence or ", but " in sentence or ", rather than " in sentence:
        clauses = re.split(r"[;:]|, but |, rather than ", sentence)
        for clause in clauses:
            clause_clean = clause.strip()
            # If this clause is positive (no prohibitive terms) and specifies an action
            if not PROHIBITIVE_PATTERN.search(clause_clean) and (
                POSITIVE_DIRECTIVE_PATTERN.search(clause_clean)
                or CONTRASTIVE_MARKERS_PATTERN.search(clause_clean)
            ):
                return True, "contrastive_clause"

    # 4. Attributive / qualifying prohibition attached to an affirmative definition
    # e.g., "Exact unique record ID, never shortened or replaced by a title"
    # e.g., "requires inspection, never a guessed value"
    if "," in sentence:
        parts = sentence.split(",")
        for part in parts:
            part_clean = part.strip()
            if not PROHIBITIVE_PATTERN.search(part_clean) and len(part_clean) > 3:
                if POSITIVE_DIRECTIVE_PATTERN.search(part_clean) or re.search(
                    r"\b(id|ids|record|boundary|audit|checkpoint|state|terminal|result|receipt)\b",
                    part_clean,
                    re.IGNORECASE,
                ):
                    return True, "attributive_definition"

    # 5. Adjacent sentence coupling in immediate context (preceding or succeeding sentence)
    if prev_sentence:
        if (
            CONTRASTIVE_MARKERS_PATTERN.search(prev_sentence)
            or POSITIVE_DIRECTIVE_PATTERN.search(prev_sentence)
            or SPECIAL_PHRASES_PATTERN.search(prev_sentence)
        ):
            return True, "preceding_sentence"

    if next_sentence:
        if (
            CONTRASTIVE_MARKERS_PATTERN.search(next_sentence)
            or POSITIVE_DIRECTIVE_PATTERN.search(next_sentence)
            or SPECIAL_PHRASES_PATTERN.search(next_sentence)
        ):
            return True, "succeeding_sentence"

    return False, "orphan"


def check_rule_hygiene_negation(doc: MarkdownDocument) -> List[Diagnostic]:
    """
    Evaluates RULE_HYGIENE_NEGATION on a MarkdownDocument.
    Flags prohibitive terms lacking adjacent positive behavioral target instructions.
    """
    diagnostics: List[Diagnostic] = []

    # Checkable nodes: paragraph, list_item, table
    checkable_nodes = [
        n for n in doc.nodes if n.node_type in ("paragraph", "list_item", "table")
    ]

    for node in checkable_nodes:
        # Check if node text contains any prohibitive term
        if not PROHIBITIVE_PATTERN.search(node.text):
            continue

        sentences = split_sentences(node.text)

        for s_idx, sentence in enumerate(sentences):
            # Check all prohibitive matches in sentence
            for match in PROHIBITIVE_PATTERN.finditer(sentence):
                # Ignore if inside backticks (`never`)
                if is_inside_inline_code(sentence, match.start(), match.end()):
                    continue

                prev_s = sentences[s_idx - 1] if s_idx > 0 else None
                next_s = sentences[s_idx + 1] if s_idx < len(sentences) - 1 else None

                paired, _ = is_paired_with_positive_target(sentence, prev_s, next_s)
                if not paired:
                    # Find exact line number in node.lines
                    matched_term = match.group(0)
                    exact_line = node.start_line
                    snippet = sentence

                    for lref in node.lines:
                        # Check if line contains this prohibitive term
                        m_line = re.search(r"\b" + re.escape(matched_term) + r"\b", lref.text, re.IGNORECASE)
                        if m_line and not is_inside_inline_code(lref.text, m_line.start(), m_line.end()):
                            exact_line = lref.line_number
                            snippet = lref.text.strip()
                            break

                    diagnostics.append(
                        Diagnostic(
                            file=str(doc.path),
                            line=exact_line,
                            rule=RULE_HYGIENE_NEGATION,
                            snippet=snippet,
                            message=MSG_ORPHAN_NEGATION,
                        )
                    )
                    # Once a sentence is flagged as orphan negation, move to next sentence
                    break

    # Also check frontmatter description if present
    if "description" in doc.frontmatter and doc.frontmatter["description"]:
        desc_text = str(doc.frontmatter["description"])
        for match in PROHIBITIVE_PATTERN.finditer(desc_text):
            if is_inside_inline_code(desc_text, match.start(), match.end()):
                continue
            desc_sentences = split_sentences(desc_text)
            for d_idx, ds in enumerate(desc_sentences):
                if match.group(0).lower() in ds.lower():
                    prev_d = desc_sentences[d_idx - 1] if d_idx > 0 else None
                    next_d = desc_sentences[d_idx + 1] if d_idx < len(desc_sentences) - 1 else None
                    paired, _ = is_paired_with_positive_target(ds, prev_d, next_d)
                    if not paired:
                        # Find line in frontmatter node
                        fm_node = next((n for n in doc.nodes if n.node_type == "frontmatter"), None)
                        exact_line = 1
                        if fm_node:
                            for lref in fm_node.lines:
                                if "description" in lref.text or match.group(0).lower() in lref.text.lower():
                                    exact_line = lref.line_number
                                    break
                        diagnostics.append(
                            Diagnostic(
                                file=str(doc.path),
                                line=exact_line,
                                rule=RULE_HYGIENE_NEGATION,
                                snippet=ds,
                                message=MSG_ORPHAN_NEGATION,
                            )
                        )
                        break

    return diagnostics


def slugify(text: str) -> str:
    """
    Standard markdown heading slugification (matching GitHub / standard markdown anchors).
    """
    return re.sub(r"[^\w\s-]", "", text.lower()).strip().replace(" ", "-")


def check_rule_context_load_budget(
    doc: MarkdownDocument,
    max_tokens: int = 120,
    max_chars: int = 600,
) -> List[Diagnostic]:
    """
    Evaluates RULE_CONTEXT_LOAD_BUDGET on a MarkdownDocument.
    Measures character and token length of frontmatter description and flags
    descriptions exceeding the configured context load ceiling.
    """
    diagnostics: List[Diagnostic] = []
    if "description" not in doc.frontmatter or not doc.frontmatter["description"]:
        return diagnostics

    desc = str(doc.frontmatter["description"]).strip()
    words_count = len(desc.split())
    len_tokens = (len(desc) + 3) // 4
    token_estimate = max(words_count, len_tokens)
    char_count = len(desc)

    if token_estimate > max_tokens or char_count > max_chars:
        fm_node = next((n for n in doc.nodes if n.node_type == "frontmatter"), None)
        line_num = 1
        snippet = desc[:80] + "..." if len(desc) > 80 else desc
        if fm_node:
            for lref in fm_node.lines:
                if re.search(r"^\s*description\s*:", lref.text, re.IGNORECASE):
                    line_num = lref.line_number
                    snippet = lref.text.strip()
                    break

        diagnostics.append(
            Diagnostic(
                file=str(doc.path),
                line=line_num,
                rule=RULE_CONTEXT_LOAD_BUDGET,
                snippet=snippet,
                message=MSG_BUDGET_EXCEEDED.format(
                    tokens=token_estimate,
                    chars=char_count,
                    max_tokens=max_tokens,
                    max_chars=max_chars,
                ),
            )
        )

    return diagnostics


def check_rule_completion_criteria(doc: MarkdownDocument) -> List[Diagnostic]:
    """
    Evaluates RULE_COMPLETION_CRITERIA on a MarkdownDocument.
    Verifies that sequential operational steps conclude with checkable, observable
    completion criteria or terminal exit conditions, alerting on vague bounds.
    """
    has_doc_completion = bool(DOC_COMPLETION_PATTERN.search(doc.raw_text))
    diagnostics: List[Diagnostic] = []
    current_heading = ""
    i = 0
    nodes = doc.nodes

    while i < len(nodes):
        node = nodes[i]
        if node.node_type == "heading":
            current_heading = node.text
            i += 1
            continue

        if NON_OPERATIONAL_HEADING_PATTERN.search(current_heading):
            i += 1
            continue

        is_step = (
            (node.node_type == "list_item" and node.metadata.get("ordered"))
            or (node.node_type == "paragraph" and re.match(r"^\s*\d+\.\s+\*\*", node.text))
        )
        if is_step:
            step_nodes = [node]
            j = i + 1
            while j < len(nodes):
                next_node = nodes[j]
                if next_node.node_type == "heading":
                    break
                if (
                    (next_node.node_type == "list_item" and next_node.metadata.get("ordered"))
                    or (next_node.node_type == "paragraph" and re.match(r"^\s*\d+\.\s+\*\*", next_node.text))
                ):
                    break
                step_nodes.append(next_node)
                j += 1

            step_text = " ".join(n.text for n in step_nodes)
            vague_match = VAGUE_BOUNDS_PATTERN.search(step_text)
            first_line = node.lines[0].text.strip() if node.lines else node.text[:80]

            if vague_match:
                diagnostics.append(
                    Diagnostic(
                        file=str(doc.path),
                        line=node.start_line,
                        rule=RULE_COMPLETION_CRITERIA,
                        snippet=first_line,
                        message=MSG_VAGUE_COMPLETION_BOUND.format(bound=vague_match.group(0)),
                    )
                )
            else:
                has_marker = bool(TERMINAL_MARKERS_PATTERN.search(step_text))
                if not has_marker and not has_doc_completion:
                    diagnostics.append(
                        Diagnostic(
                            file=str(doc.path),
                            line=node.start_line,
                            rule=RULE_COMPLETION_CRITERIA,
                            snippet=first_line,
                            message=MSG_MISSING_COMPLETION_CRITERION,
                        )
                    )
            i = j
            continue
        i += 1

    return diagnostics


def check_rule_pointer_integrity(doc: MarkdownDocument) -> List[Diagnostic]:
    """
    Evaluates RULE_POINTER_INTEGRITY on a MarkdownDocument.
    Validates that all referenced local documents, sibling files, and anchor fragments exist on disk.
    """
    diagnostics: List[Diagnostic] = []

    for node in doc.nodes:
        if node.node_type in ("code_block", "divider"):
            continue

        for lref in node.lines:
            for match in LINK_PATTERN.finditer(lref.text):
                if is_inside_inline_code(lref.text, match.start(), match.end()):
                    continue

                label = match.group(1)
                target = match.group(2)

                if target.startswith(
                    (
                        "http://",
                        "https://",
                        "mailto:",
                        "ftp://",
                        "ssh://",
                        "git://",
                        "tel:",
                        "conversation://",
                        "<",
                        "{{",
                        "$",
                    )
                ):
                    continue

                if target.startswith("file://"):
                    raw_target = target[7:]
                    file_part = raw_target.split("#")[0].strip()
                    anchor_part = raw_target.split("#")[1].strip() if "#" in raw_target else None
                    target_path = (
                        Path(file_part).resolve()
                        if file_part
                        else (doc.path.resolve() if doc.path.is_file() else None)
                    )
                else:
                    file_part = target.split("#")[0].strip()
                    anchor_part = target.split("#")[1].strip() if "#" in target else None

                    if doc.path.is_file() or doc.path.parent.exists():
                        base_dir = doc.path.parent
                    else:
                        base_dir = Path.cwd()

                    target_path = (
                        (base_dir / file_part).resolve()
                        if file_part
                        else (doc.path.resolve() if doc.path.is_file() else None)
                    )

                if file_part:
                    if not target_path or not target_path.exists():
                        diagnostics.append(
                            Diagnostic(
                                file=str(doc.path),
                                line=lref.line_number,
                                rule=RULE_POINTER_INTEGRITY,
                                snippet=match.group(0),
                                message=MSG_BROKEN_TARGET.format(target=file_part),
                            )
                        )
                        continue

                if anchor_part and target_path and target_path.exists() and target_path.suffix.lower() == ".md":
                    try:
                        target_content = target_path.read_text(encoding="utf-8")
                        headings = [
                            slugify(m.group(1))
                            for m in re.finditer(r"^#{1,6}\s+(.*)$", target_content, re.MULTILINE)
                        ]
                        line_match = re.match(r"^L(\d+)(?:-L?(\d+))?$", anchor_part)
                        if line_match:
                            total_lines = len(target_content.splitlines())
                            start_l = int(line_match.group(1))
                            end_l = int(line_match.group(2)) if line_match.group(2) else start_l
                            if start_l > total_lines or end_l > total_lines or start_l < 1:
                                target_name = file_part if file_part else doc.path.name
                                diagnostics.append(
                                    Diagnostic(
                                        file=str(doc.path),
                                        line=lref.line_number,
                                        rule=RULE_POINTER_INTEGRITY,
                                        snippet=match.group(0),
                                        message=MSG_BROKEN_ANCHOR.format(
                                            anchor=anchor_part, target=target_name
                                        ),
                                    )
                                )
                        elif anchor_part not in headings:
                            target_name = file_part if file_part else doc.path.name
                            diagnostics.append(
                                Diagnostic(
                                    file=str(doc.path),
                                    line=lref.line_number,
                                    rule=RULE_POINTER_INTEGRITY,
                                    snippet=match.group(0),
                                    message=MSG_BROKEN_ANCHOR.format(
                                        anchor=anchor_part, target=target_name
                                    ),
                                )
                            )
                    except Exception:
                        pass

    return diagnostics


def lint_markdown_file(
    path: Path,
    max_description_tokens: int = 120,
    max_description_chars: int = 600,
) -> List[Diagnostic]:
    """
    Parses and lints a single Markdown file against all hygiene rules:
    - RULE_HYGIENE_NEGATION
    - RULE_CONTEXT_LOAD_BUDGET
    - RULE_COMPLETION_CRITERIA
    - RULE_POINTER_INTEGRITY
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [
            Diagnostic(
                file=str(path),
                line=1,
                rule="FILE_READ_ERROR",
                snippet="",
                message=f"Failed to read file: {exc}",
            )
        ]

    doc = parse_markdown(content, path=path)
    diags: List[Diagnostic] = []
    diags.extend(check_rule_hygiene_negation(doc))
    diags.extend(
        check_rule_context_load_budget(
            doc,
            max_tokens=max_description_tokens,
            max_chars=max_description_chars,
        )
    )
    diags.extend(check_rule_completion_criteria(doc))
    diags.extend(check_rule_pointer_integrity(doc))
    diags.sort(key=lambda d: (d.line, d.rule))
    return diags


def lint_path(
    target_path: Path,
    max_description_tokens: int = 120,
    max_description_chars: int = 600,
) -> Tuple[List[Diagnostic], int]:
    """
    Lints a file or all Markdown files within a directory.
    Returns (diagnostics, files_count).
    """
    if not target_path.exists():
        raise FileNotFoundError(f"Path does not exist: {target_path}")

    files: List[Path] = []
    if target_path.is_file():
        if target_path.suffix.lower() == ".md":
            files = [target_path]
        else:
            files = [target_path]
    elif target_path.is_dir():
        files = sorted(target_path.rglob("*.md"))

    all_diagnostics: List[Diagnostic] = []
    for f in files:
        diags = lint_markdown_file(
            f,
            max_description_tokens=max_description_tokens,
            max_description_chars=max_description_chars,
        )
        all_diagnostics.extend(diags)

    return all_diagnostics, len(files)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Static Skill Hygiene Linter for agent skills."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to a markdown file or directory containing skills (default: .)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON diagnostics for CI",
    )
    parser.add_argument(
        "--max-description-tokens",
        type=int,
        default=120,
        help="Maximum tokens allowed for frontmatter description (default: 120)",
    )
    parser.add_argument(
        "--max-description-chars",
        type=int,
        default=600,
        help="Maximum characters allowed for frontmatter description (default: 600)",
    )

    args = parser.parse_args(argv)
    target = Path(args.path)

    try:
        diagnostics, files_count = lint_path(
            target,
            max_description_tokens=args.max_description_tokens,
            max_description_chars=args.max_description_chars,
        )
    except FileNotFoundError as exc:
        if args.json:
            print(json.dumps([{"error": str(exc)}], indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([d.to_dict() for d in diagnostics], indent=2))
    else:
        if diagnostics:
            for d in diagnostics:
                print(f"{d.file}:{d.line}: [{d.rule}] {d.message}")
                print(f'  Snippet: "{d.snippet}"')
            file_plural = "file" if files_count == 1 else "files"
            diag_plural = "violation" if len(diagnostics) == 1 else "violations"
            print(
                f"\nFound {len(diagnostics)} skill hygiene {diag_plural} across {files_count} {file_plural}."
            )
        else:
            file_plural = "file" if files_count == 1 else "files"
            print(
                f"Checked {files_count} {file_plural} in {target}. All skills pass hygiene checks! (0 violations)"
            )

    return 0 if len(diagnostics) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
