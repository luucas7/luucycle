"""Read-only Git baseline contract; fixtures commit only inside scratch repos."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/luucycle/scripts/git_baseline.py"


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "tracked").write_bytes(b"committed\x00bytes\n")
        self.git("add", "tracked")
        self.git("commit", "-qm", "fixture")

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["GIT_OPTIONAL_LOCKS"] = "0"
        return subprocess.check_output(["git", "-C", str(self.repo), *args], env=env)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                              capture_output=True)

    def capture(self, *targets):
        result = self.cli("capture", "--repo", self.repo,
                          *["--target=" + p for p in targets])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def save(self, value, name="baseline.json"):
        p = Path(self.tmp.name) / name
        p.write_text(json.dumps(value), encoding="utf-8")
        return p

    def check(self, baseline, *args):
        result = self.cli("check", "--repo", self.repo, "--snapshot", self.save(baseline), *args)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_capture_dirty_bytes_index_head_targets_without_mutation(self):
        (self.repo / "tracked").write_bytes(b"staged\x00secret")
        self.git("add", "tracked")
        (self.repo / "tracked").write_bytes(b"unstaged\xffsecret")
        (self.repo / "untracked").write_bytes(b"private")
        before = (self.repo / ".git/index").read_bytes()
        baseline = self.capture("tracked", "not-created")
        self.assertEqual(baseline["schema"], "luucycle.git-baseline.v1")
        state = baseline["state"]
        self.assertEqual(state["head"]["oid"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertEqual(state["files"]["tracked"]["sha256"], hashlib.sha256(b"unstaged\xffsecret").hexdigest())
        self.assertEqual(state["files"]["untracked"]["sha256"], hashlib.sha256(b"private").hexdigest())
        self.assertEqual(state["targets"], {"not-created": {"kind": "absent"}, "tracked": state["files"]["tracked"]})
        self.assertEqual(state["index"]["entries"][0]["oid"], self.git("rev-parse", ":tracked").decode().strip())
        self.assertNotIn("secret", json.dumps(baseline))
        self.assertEqual((self.repo / ".git/index").read_bytes(), before)
        self.assertEqual(self.capture("tracked", "not-created"), baseline)

    def test_check_detects_worktree_and_index_changes_even_same_status(self):
        (self.repo / "tracked").write_bytes(b"already dirty")
        baseline = self.capture("new")
        code, result = self.check(baseline)
        self.assertEqual((code, result["status"], result["changes"]), (0, "PASS", []))
        (self.repo / "tracked").write_bytes(b"different dirty")
        (self.repo / "new").write_bytes(b"added")
        self.git("add", "new")
        code, result = self.check(baseline)
        self.assertEqual((code, result["status"]), (1, "STOP"))
        self.assertEqual({d["scope"] for d in result["changes"]}, {"files", "index", "targets"})
        self.assertTrue(any(d["path"] == "tracked" for d in result["changes"]))
        self.assertTrue(any(d["scope"] == "index" for d in result["changes"]))

    def test_check_detects_deletions_renames_modes_and_head(self):
        (self.repo / "extra").write_bytes(b"untracked")
        baseline = self.capture()
        (self.repo / "extra").unlink()
        (self.repo / "tracked").rename(self.repo / "renamed")
        (self.repo / "renamed").chmod(0o755)
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture rename")
        code, result = self.check(baseline)
        self.assertEqual((code, result["status"]), (1, "STOP"))
        self.assertTrue(any(d["scope"] == "head" for d in result["changes"]))
        self.assertTrue(any(d["path"] == "extra" and d["after"] is None for d in result["changes"]))
        self.assertTrue(any(d["path"] == "tracked" and d["after"] is None for d in result["changes"]))
        self.assertTrue(any(d["path"] == "renamed" and d["before"] is None for d in result["changes"]))

    def reseal(self, baseline):
        raw = (json.dumps(baseline["state"], sort_keys=True, ensure_ascii=True,
                          separators=(",", ":")) + "\n").encode("ascii")
        baseline["sha256"] = hashlib.sha256(raw).hexdigest()
        return baseline

    def test_rejects_invalid_incomplete_and_tampered_snapshot(self):
        baseline = self.capture("missing")
        mutations = [
            lambda b: b.update(schema="other"),
            lambda b: b.update(sha256="0" * 64),
            lambda b: b["state"].pop("head"),
            lambda b: b["state"].update(extra=1),
            lambda b: b["state"]["files"].update(tracked={"kind": "file"}),
            lambda b: b["state"]["targets"].update(missing={"kind": "file"}),
            lambda b: b["state"]["index"].update(entries=[]),
            lambda b: b["state"]["files"].update({"../escape": b["state"]["files"]["tracked"]}),
        ]
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                bad = json.loads(json.dumps(baseline))
                mutate(bad)
                if number != 1:
                    self.reseal(bad)
                code, report = self.check(bad)
                self.assertEqual(code, 2)
                self.assertEqual(report["status"], "STOP")
                self.assertIn("error", report)
        for raw in (b"{", b"{}", b"[]", b'{"schema":1,"schema":2}', b"NaN"):
            with self.subTest(raw=raw):
                source = Path(self.tmp.name) / "invalid.json"
                source.write_bytes(raw)
                result = self.cli("check", "--repo", self.repo, "--snapshot", source)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "STOP")
                self.assertNotIn(b"Traceback", result.stderr)

    def test_snapshot_cannot_be_replayed_against_different_repository(self):
        baseline = self.capture()
        baseline["state"]["repo"] = str(Path(self.tmp.name) / "different")
        self.reseal(baseline)
        code, report = self.check(baseline)
        self.assertEqual((code, report["status"]), (2, "STOP"))

    def test_rejects_unsafe_targets_without_resolving_or_normalizing_them(self):
        (self.repo / "directory").mkdir()
        (self.repo / "linkdir").symlink_to(Path(self.tmp.name), target_is_directory=True)
        for target in ("", ".", "directory", "directory/", "../escape", "a/../b", "./tracked",
                       "/absolute", ".git/index", "linkdir/elsewhere", "unknown/", "a//b"):
            with self.subTest(target=target):
                result = self.cli("capture", "--repo", self.repo, "--target", target)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "STOP")
        spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for target in (Path(""), Path(".")):
            with self.assertRaises(module.BaselineError):
                module.capture(self.repo, [target])

    def test_rejects_nonroot_symlink_repo_special_files_and_nested_git(self):
        sub = self.repo / "sub"
        sub.mkdir()
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        for repo in (sub, alias, Path(self.tmp.name)):
            with self.subTest(repo=repo):
                result = self.cli("capture", "--repo", repo)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "STOP")
        (sub / ".git").mkdir()
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)
        (sub / ".git").rmdir()
        os.mkfifo(self.repo / "pipe")
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)

    def test_inventory_includes_directories_ignored_files_and_symlink_bytes(self):
        (self.repo / ".gitignore").write_text("ignored\n")
        (self.repo / "ignored").write_bytes(b"private ignored value")
        (self.repo / "empty").mkdir()
        (self.repo / "empty").chmod(0o755)
        (self.repo / "link").symlink_to("outside-missing")
        baseline = self.capture("link")
        self.assertIn("directories", baseline["state"])
        self.assertEqual(baseline["state"]["directories"]["empty"], {"kind": "directory", "mode": 0o755})
        self.assertIn("ignored", baseline["state"]["files"])
        self.assertEqual(baseline["state"]["files"]["link"]["kind"], "symlink")
        self.assertEqual(baseline["state"]["files"]["link"]["sha256"], hashlib.sha256(b"outside-missing").hexdigest())
        (self.repo / "empty").rmdir()
        (self.repo / "link").unlink()
        (self.repo / "link").symlink_to("other")
        code, report = self.check(baseline)
        self.assertEqual(code, 1)
        self.assertTrue(any(d["scope"] == "directories" for d in report["changes"]))
        self.assertTrue(any(d["path"] == "link" for d in report["changes"]))

    def test_collection_limits_stop_explicitly_without_partial_snapshot(self):
        for limit_args, message in ((["--max-files", "1"], "file limit"),
                                    (["--max-bytes", "1"], "byte limit")):
            with self.subTest(limit=limit_args):
                result = self.cli("capture", "--repo", self.repo, *limit_args)
                self.assertEqual(result.returncode, 2)
                report = json.loads(result.stdout)
                self.assertEqual(report["status"], "STOP")
                self.assertIn(message, report["error"])
                self.assertNotIn("state", report)

    def test_collection_time_limit_stops_before_observation(self):
        module = self.load_module()
        with mock.patch.object(module.time, "monotonic", side_effect=[0.0, 2.0]):
            with self.assertRaisesRegex(module.BaselineError, "time limit"):
                module.capture(self.repo, max_seconds=1)

    def test_git_pipe_is_stopped_before_producing_unbounded_listing(self):
        module = self.load_module()
        binary = Path(self.tmp.name) / "bin"
        binary.mkdir()
        marker = Path(self.tmp.name) / "fully-produced"
        executable = binary / "git"
        executable.write_text(f"#!{sys.executable}\nimport os\nfrom pathlib import Path\n"
                              "for _ in range(128): os.write(1, b'x' * 65536)\n"
                              f"Path({str(marker)!r}).write_text('too much')\n")
        executable.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(binary)}):
            with self.assertRaisesRegex(module.BaselineError, "byte limit"):
                module.git(self.repo, "ls-files", budget=module.Budget(5, 1024, 10))
        self.assertFalse(marker.exists(), "producer must be stopped while draining, before full output buffering")

    def load_module(self):
        spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_capture_stops_on_mutation_during_inventory(self):
        module = self.load_module()
        original = module.file_record
        calls = []
        def changing(*args, **kwargs):
            record = original(*args, **kwargs)
            if not calls:
                calls.append(True)
                (self.repo / "tracked").write_bytes(b"concurrent writer")
            return record
        with mock.patch.object(module, "file_record", side_effect=changing):
            with self.assertRaisesRegex(module.BaselineError, "mutat|chang|stable"):
                module.capture(self.repo)

    def test_capture_does_not_follow_ancestor_swapped_to_symlink(self):
        module = self.load_module()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret").write_bytes(b"must not hash")
        nested = self.repo / "nested"
        nested.mkdir()
        (nested / "secret").write_bytes(b"safe")
        original = module.file_record
        observed = []
        def swapping(path, *args, **kwargs):
            if Path(path).name == "secret" and nested.is_dir() and not nested.is_symlink():
                nested.rename(self.repo / "moved")
                nested.symlink_to(outside, target_is_directory=True)
            record = original(path, *args, **kwargs)
            observed.append(record.get("sha256"))
            return record
        with mock.patch.object(module, "file_record", side_effect=swapping):
            with self.assertRaises((module.BaselineError, OSError)):
                module.capture(self.repo)
        self.assertNotIn(hashlib.sha256(b"must not hash").hexdigest(), observed)

    def test_expected_exact_deltas_allow_clean_task_edits_not_other_changes(self):
        baseline = self.capture("new")
        (self.repo / "tracked").write_bytes(b"task edit")
        (self.repo / "new").write_bytes(b"task addition")
        _, first = self.check(baseline)
        expected = self.save({"baseline_sha256": baseline["sha256"], "changes": first["changes"]}, "expected.json")
        code, report = self.check(baseline, "--expected", str(expected))
        self.assertEqual((code, report["status"]), (0, "PASS"))
        self.assertEqual(report["changes"], first["changes"])
        self.assertEqual(report["unexpected"], [])
        (self.repo / "new").write_bytes(b"not the approved result")
        code, report = self.check(baseline, "--expected", str(expected))
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "STOP")

    def test_expected_changes_cannot_exempt_preexisting_dirty_or_untracked_bytes(self):
        (self.repo / "tracked").write_bytes(b"preexisting secret")
        self.git("add", "tracked")
        self.git("update-index", "--assume-unchanged", "tracked")
        (self.repo / "tracked").write_bytes(b"hidden unstaged secret")
        (self.repo / "private").write_bytes(b"untracked secret")
        baseline = self.capture()
        (self.repo / "tracked").write_bytes(b"committed\x00bytes\n")
        (self.repo / "private").unlink()
        _, first = self.check(baseline)
        expected = self.save({"baseline_sha256": baseline["sha256"], "changes": first["changes"]}, "expected.json")
        code, report = self.check(baseline, "--expected", str(expected))
        self.assertEqual((code, report["status"]), (1, "STOP"))
        self.assertEqual({d["path"] for d in report["protected_changes"]}, {"private", "tracked"})

    def test_expected_manifest_is_strict_and_baseline_bound(self):
        baseline = self.capture()
        for value in (["tracked"], {}, {"baseline_sha256": "0" * 64, "changes": []},
                      {"baseline_sha256": baseline["sha256"], "changes": [{"path": "tracked"}]}):
            with self.subTest(value=value):
                expected = self.save(value, "expected.json")
                code, report = self.check(baseline, "--expected", str(expected))
                self.assertEqual((code, report["status"]), (2, "STOP"))

    def test_unborn_head_and_absent_index_are_explicit(self):
        empty = Path(self.tmp.name) / "empty-repo"
        empty.mkdir()
        subprocess.run(["git", "-C", str(empty), "init", "-q"], check=True)
        result = self.cli("capture", "--repo", empty, "--target", "future")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        baseline = json.loads(result.stdout)
        self.assertIsNone(baseline["state"]["head"]["oid"])
        self.assertIsNone(baseline["state"]["index"]["sha256"])
        self.assertEqual(baseline["state"]["index"]["entries"], [])
        source = self.save(baseline)
        result = self.cli("check", "--repo", empty, "--snapshot", source)
        self.assertEqual((result.returncode, json.loads(result.stdout)["status"]), (0, "PASS"))

    def test_rejects_symlink_metadata_and_snapshot_sources(self):
        baseline = self.capture()
        source = self.save(baseline)
        alias = Path(self.tmp.name) / "source-link"
        alias.symlink_to(source)
        result = self.cli("check", "--repo", self.repo, "--snapshot", alias)
        self.assertEqual(result.returncode, 2)
        index = self.repo / ".git/index"
        saved = Path(self.tmp.name) / "original-index"
        index.rename(saved)
        index.symlink_to(saved)
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "STOP")
        self.assertEqual(saved.read_bytes(), source.parent.joinpath("original-index").read_bytes())

    def test_cli_usage_errors_are_deterministic_json_stop(self):
        for args in ((), ("unknown",), ("capture",), ("check", "--repo", self.repo),
                     ("capture", "--repo", self.repo, "--unexpected", "private-value")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stdout)
                self.assertEqual(json.loads(result.stdout)["status"], "STOP")
                self.assertNotIn(b"private-value", result.stdout + result.stderr)

    def test_structural_validation_rejects_consistently_resealed_inventory_holes(self):
        baseline = self.capture("target")
        for mutate in (
            lambda s: s["counts"].update(files=True),
            lambda s: s["files"].update({"orphan/file": s["files"]["tracked"]}),
            lambda s: s["directories"].update(tracked={"kind": "directory", "mode": 0o755}),
            lambda s: s["directories"].update(target={"kind": "directory", "mode": 0o755}),
            lambda s: s["head"]["entries"].clear(),
        ):
            with self.subTest(mutate=mutate):
                bad = json.loads(json.dumps(baseline))
                mutate(bad["state"])
                # Preserve declared counts to detect omitted information, not trust re-sealing.
                self.reseal(bad)
                code, report = self.check(bad)
                self.assertEqual((code, report["status"]), (2, "STOP"))

    def test_head_metadata_symlinks_and_raw_byte_changes_are_detected(self):
        baseline = self.capture()
        head = self.repo / ".git/HEAD"
        original = head.read_bytes()
        head.write_bytes(original.rstrip(b"\n"))
        code, report = self.check(baseline)
        self.assertEqual((code, report["status"]), (1, "STOP"))
        self.assertTrue(any(d["scope"] == "head" for d in report["changes"]))
        saved = Path(self.tmp.name) / "saved-head"
        head.rename(saved)
        head.symlink_to(saved)
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)

    def test_same_path_replaced_repository_is_not_the_original_source(self):
        baseline = self.capture()
        old = self.repo.with_name("old")
        self.repo.rename(old)
        import shutil
        shutil.copytree(old, self.repo, symlinks=True)
        code, report = self.check(baseline)
        self.assertEqual((code, report["status"]), (2, "STOP"))

    def test_deeply_nested_invalid_json_stops_without_traceback(self):
        source = Path(self.tmp.name) / "deep.json"
        source.write_bytes(b"[" * 1200 + b"]" * 1200)
        result = self.cli("check", "--repo", self.repo, "--snapshot", source)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "STOP")
        self.assertNotIn(b"Traceback", result.stderr)

    def test_generator_targets_are_materialized_before_stable_reads(self):
        module = self.load_module()
        baseline = module.capture(self.repo, (x for x in ("tracked", "missing")))
        self.assertEqual(set(baseline["state"]["targets"]), {"tracked", "missing"})

    def test_index_gitlink_without_checkout_stops_incomplete_inventory(self):
        oid = self.git("rev-parse", "HEAD").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", "160000," + oid + ",submodule")
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "STOP")

    def test_split_indexes_stop_capture_and_check_including_symlink_backing(self):
        baseline = self.capture()
        self.git("update-index", "--split-index")
        shared = list((self.repo / ".git").glob("sharedindex.*"))
        self.assertEqual(len(shared), 1)
        index_bytes = (self.repo / ".git/index").read_bytes()
        shared_bytes = shared[0].read_bytes()
        # This is the v1 snapshot an older capture made for this split index:
        # logical entries are unchanged; only the raw index checksum differs.
        split_baseline = json.loads(json.dumps(baseline))
        split_baseline["state"]["index"]["sha256"] = hashlib.sha256(index_bytes).hexdigest()
        self.reseal(split_baseline)
        with self.subTest(operation="capture initially split"):
            result = self.cli("capture", "--repo", self.repo)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "STOP")
            self.assertIn("Split indexes are unsupported", report["error"])
        with self.subTest(operation="check normal to split"):
            code, report = self.check(baseline)
            self.assertEqual((code, report["status"]), (2, "STOP"))
            self.assertIn("Split indexes are unsupported", report["error"])
        saved = Path(self.tmp.name) / "shared-index-outside-git"
        shared[0].rename(saved)
        shared[0].symlink_to(saved)
        with self.subTest(operation="check split backing symlink"):
            code, report = self.check(split_baseline)
            self.assertEqual((code, report["status"]), (2, "STOP"))
            self.assertIn("Split indexes are unsupported", report["error"])
        self.assertEqual((self.repo / ".git/index").read_bytes(), index_bytes)
        self.assertEqual(saved.read_bytes(), shared_bytes)
        self.assertTrue(shared[0].is_symlink())

    def test_capture_never_executes_configured_fsmonitor_hook(self):
        marker = Path(self.tmp.name) / "executed"
        hook = Path(self.tmp.name) / "monitor"
        hook.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\nprint(\"token\\0\")\n")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        self.capture()
        self.assertFalse(marker.exists())

    def test_raw_index_flag_changes_are_observed_without_worktree_changes(self):
        baseline = self.capture()
        self.git("update-index", "--skip-worktree", "tracked")
        code, report = self.check(baseline)
        self.assertEqual((code, report["status"]), (1, "STOP"))
        self.assertEqual([d["scope"] for d in report["changes"]], ["index"])
        delta = report["changes"][0]
        self.assertEqual(delta["before"]["entries"], delta["after"]["entries"])
        self.assertNotEqual(delta["before"]["sha256"], delta["after"]["sha256"])

    def test_conflicted_index_stages_and_odd_names_round_trip(self):
        oid = self.git("rev-parse", ":tracked").decode().strip()
        data = ("0 " + "0" * 40 + "\ttracked\n" + "100644 " + oid + " 1\ttracked\n" + "100644 " + oid + " 2\ttracked\n").encode()
        subprocess.run(["git", "-C", str(self.repo), "update-index", "--index-info"], input=data, check=True)
        names = ["line\nname", "tab\tname", "space name", "-leading", os.fsdecode(b"bad-\xff")]
        for name in names:
            (self.repo / name).write_bytes(b"opaque\0\xff")
        baseline = self.capture(*names)
        self.assertEqual({e["stage"] for e in baseline["state"]["index"]["entries"]}, {1, 2})
        self.assertTrue(set(names) <= set(baseline["state"]["files"]))
        code, report = self.check(baseline)
        self.assertEqual((code, report["status"]), (0, "PASS"))

    def test_partial_clone_missing_tree_stops_without_lazy_fetch(self):
        marker = Path(self.tmp.name) / "fetch-ran"
        transport = Path(self.tmp.name) / "fake-upload-pack"
        transport.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\nraise SystemExit(1)\n")
        transport.chmod(0o755)
        self.git("config", "remote.origin.url", "ext::" + str(transport))
        self.git("config", "remote.origin.promisor", "true")
        self.git("config", "remote.origin.partialclonefilter", "blob:none")
        self.git("config", "extensions.partialClone", "origin")
        self.git("config", "protocol.ext.allow", "always")
        tree = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        (self.repo / ".git/objects" / tree[:2] / tree[2:]).unlink()
        result = self.cli("capture", "--repo", self.repo)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "STOP")
        self.assertFalse(marker.exists(), "A read-only baseline must not invoke a promisor fetch")

    def test_linked_worktree_uses_its_own_index_and_detached_head(self):
        worktree = Path(self.tmp.name) / "worktree"
        self.git("worktree", "add", "--detach", "--quiet", str(worktree), "HEAD")
        result = self.cli("capture", "--repo", worktree, "--target", "tracked")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        baseline = json.loads(result.stdout)
        self.assertIsNone(baseline["state"]["head"]["ref"])
        self.assertEqual(baseline["state"]["index"]["entries"][0]["path"], "tracked")
        source = self.save(baseline)
        result = self.cli("check", "--repo", worktree, "--snapshot", source)
        self.assertEqual((result.returncode, json.loads(result.stdout)["status"]), (0, "PASS"))

    def test_sha256_git_object_format_round_trips(self):
        repo = Path(self.tmp.name) / "sha-repo"
        repo.mkdir()
        run = lambda *args: subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
        run("init", "--object-format=sha256", "-q")
        (repo / "tracked").write_bytes(b"sha256 repo\x00data")
        run("add", "tracked")
        run("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
        result = self.cli("capture", "--repo", repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        baseline = json.loads(result.stdout)
        self.assertEqual(len(baseline["state"]["files"]["tracked"]["git_oid"]), 64)
        source = self.save(baseline)
        result = self.cli("check", "--repo", repo, "--snapshot", source)
        self.assertEqual((result.returncode, json.loads(result.stdout)["status"]), (0, "PASS"))

    def test_comparison_cannot_exempt_a_changed_target_selection(self):
        module = self.load_module()
        before = module.capture(self.repo, ["tracked"])
        after = module.capture(self.repo)
        with self.assertRaises(module.BaselineError):
            module.compare(before, after)


if __name__ == "__main__":
    unittest.main()
