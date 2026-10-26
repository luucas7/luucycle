"""Offline documentation/data contracts, never proof that an agent obeyed them."""
from datetime import date
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = ROOT / "docs/skill-improvement.md"
RESEARCH = ROOT / "docs/skill-improvement-research.md"


def required_text(path):
    if not path.is_file():
        raise AssertionError(f"Missing workflow artifact: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def contract(text):
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    if len(blocks) != 1:
        raise ValueError("Expected one normative workflow matrix")
    return json.loads(blocks[0])


def local_link_errors(path, text):
    """Resolve actual relative Markdown targets; ignore remote URLs/code spans."""
    errors = []
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", text):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
        if not destination.is_file():
            errors.append(target)
            continue
        if parsed.fragment:
            headings = re.findall(r"^#{1,6} (.+)$", destination.read_text(encoding="utf-8"), re.M)
            anchors = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
            if unquote(parsed.fragment) not in anchors:
                errors.append(target)
    return errors


class RepositoryWorkflowTests(unittest.TestCase):
    def test_root_routes_before_repo_changes_without_loading_a_manual(self):
        root = required_text(ROOT / "AGENTS.md")
        self.assertLessEqual(len(root.splitlines()), 24)
        self.assertLessEqual(len(root.encode("utf-8")), 2400)
        self.assertRegex(root, r"(?i)avant toute modification")
        self.assertIn("(docs/skill-improvement.md)", root)
        self.assertRegex(root, r"(?i)obligatoire")

    def test_all_change_profiles_keep_gates_but_read_only_stays_read_only(self):
        matrix = contract(required_text(PROCEDURE))
        self.assertEqual(set(matrix), {"read-only", "editorial", "behavior", "runtime"})
        self.assertEqual(matrix["read-only"], {"change": False, "gates": [], "validation": "none"})
        for profile in ("editorial", "behavior", "runtime"):
            with self.subTest(profile=profile):
                self.assertTrue(matrix[profile]["change"])
                self.assertEqual(matrix[profile]["gates"], [
                    "baseline", "research", "hypothesis", "minimal-change",
                    "validation", "independent-review", "resolution", "receipt",
                ])
        self.assertEqual(matrix["editorial"]["validation"], "targeted")
        self.assertEqual(matrix["behavior"]["validation"], "targeted-and-regressions")
        self.assertEqual(matrix["runtime"]["validation"], "integration-with-separate-consent")

    def test_workflow_gates_link_to_real_completion_sections(self):
        text = required_text(PROCEDURE)
        matrix = contract(text)
        positions = []
        for gate in matrix["behavior"]["gates"]:
            heading = "## " + gate + "\n"
            self.assertIn(heading, text)
            start = text.index(heading)
            positions.append(start)
            section = text[start + len(heading):].split("\n## ", 1)[0]
            self.assertIn("Terminé quand", section, gate)
        self.assertEqual(positions, sorted(positions))

    def test_documentation_relative_targets_resolve(self):
        for path in (ROOT / "AGENTS.md", PROCEDURE, RESEARCH):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(local_link_errors(path, required_text(path)), [])

    def test_writing_prerequisite_has_pinned_upstream_and_explicit_blocked_fallback(self):
        text = required_text(PROCEDURE)
        section = text.split("### writing-for-agents\n", 1)[1].split("\n## research", 1)[0]
        targets = re.findall(r"\[[^\]\n]+\]\((https://raw\.githubusercontent\.com/[^)\s]+)\)", section)
        self.assertEqual(len(targets), 2)
        paths = [urlsplit(target).path for target in targets]
        for path in paths:
            self.assertRegex(path, r"^/mattpocock/skills/[0-9a-f]{40}/skills/productivity/writing-for-agents/(SKILL|SKILL-MECHANICS)\.md$")
        commits = {path.split("/")[3] for path in paths}
        self.assertEqual(len(commits), 1)
        self.assertIn("`" + commits.pop() + "`", section)
        self.assertEqual({Path(path).name for path in paths}, {"SKILL.md", "SKILL-MECHANICS.md"})
        hashes = re.findall(r"\| `(SKILL(?:-MECHANICS)?\.md)` \| `([0-9a-f]{64})` \|", section)
        self.assertEqual({name for name, _ in hashes}, {"SKILL.md", "SKILL-MECHANICS.md"})
        for required in ("registre", "skills-lock.json", "provenance", "SHA-256", "Sans instance conforme",
                         "réseau absent", "BLOQUÉ", "arrêter", "sans prétendre à la conformité",
                         "accord explicite", "installation automatique"):
            self.assertIn(required, section)

    def test_documentation_links_resolve_in_export_without_ignored_dependencies(self):
        # Copy the working contents, including new non-ignored files, not .git.
        # An export has no index: check its existing documents directly instead
        # of launching this suite again or searching a parent repository's Git.
        if (ROOT / ".git").exists():
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=ROOT, capture_output=True, check=True,
            )
            paths = sorted(set(result.stdout.decode().split("\0")) - {""})
        else:
            paths = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file()]
        with tempfile.TemporaryDirectory() as temporary:
            exported = Path(temporary)
            for relative in paths:
                if Path(relative).parts[0] in {".git", ".agents", ".claude"}:
                    continue
                source = ROOT / relative
                if not source.is_file():
                    continue  # Tracked deletions are absent from the working export.
                target = exported / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            for absent in (".git", ".agents", ".claude", "skills-lock.json"):
                self.assertFalse((exported / absent).exists(), absent)
            for relative in ("AGENTS.md", "docs/skill-improvement.md", "docs/skill-improvement-research.md"):
                path = exported / relative
                with self.subTest(path=relative):
                    self.assertTrue(path.is_file(), relative)
                    self.assertEqual(local_link_errors(path, path.read_text(encoding="utf-8")), [])

    def test_link_checker_detects_missing_file_and_missing_section(self):
        # Negative controls guard against a silently inert link checker.
        self.assertEqual(local_link_errors(PROCEDURE, "[bad](missing-workflow-file.md)"),
                         ["missing-workflow-file.md"])
        self.assertEqual(local_link_errors(PROCEDURE, "[bad](skill-improvement.md#missing-section)"),
                         ["skill-improvement.md#missing-section"])

    def test_research_citations_have_unique_primary_sources_and_access_date(self):
        text = required_text(RESEARCH)
        body, sources = text.split("## Sources", 1)
        prose = re.sub(r"```.*?```", "", body, flags=re.S)
        cited = set(re.findall(r"\[(\d+)\]", prose))
        rows = re.findall(r"^(?:- )?\[(\d+)\] (?:\[[^\]]+\]\()?(https://[^\s)]+)", sources, re.M)
        self.assertEqual(cited, {number for number, _ in rows})
        self.assertEqual(len(rows), len({number for number, _ in rows}))
        self.assertEqual(len(rows), len({url for _, url in rows}))
        hosts = {urlsplit(url).netloc for _, url in rows}
        self.assertTrue({"developers.openai.com", "platform.claude.com", "arxiv.org", "agentskills.io"} <= hosts)
        consulted = re.search(r"Consultation : (\d{4}-\d{2}-\d{2})", text)
        self.assertIsNotNone(consulted)
        assert consulted is not None
        date.fromisoformat(consulted.group(1))


if __name__ == "__main__":
    unittest.main()
