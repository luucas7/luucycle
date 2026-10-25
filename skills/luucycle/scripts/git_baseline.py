#!/usr/bin/env python3
"""Hash-only, read-only Git baselines (POSIX, stdlib + Git).

Usage::

    python3 -B git_baseline.py capture --repo /repo --target path > /scratch/base.json
    python3 -B git_baseline.py check --repo /repo --snapshot /scratch/base.json

Capture prints a deterministic snapshot to stdout; keep artifacts OUTSIDE the
repository. Inventory includes ignored files and empty directories, excluding
root .git metadata except HEAD and the complete index. Symlinks hash their link
bytes, not their referents. Targets name files, links or absent paths; directory
targets (including both Path("") and Path(".")) stop. Path objects may already
have normalized their spelling; only strings preserve the original spelling.

Check returns 0/PASS for preservation, 1/STOP for changes and 2/STOP for invalid
input or unsafe/incomplete observation. --expected accepts exactly
{"baseline_sha256": snapshot["sha256"], "changes": [exact check delta, ...]}.
It accounts for precise task changes, never broad path exclusions. Initial
dirty/untracked bytes remain protected even with matching expected deltas;
HEAD/index changes cannot be exempted. Every observed delta remains in output.

Snapshots contain paths, modes, sizes and hashes, never file contents. They are
integrity checks, not backups or signed attestations. Two full reads and stat
checks detect practical races, not adversarial ABA or changes after the last
read. No locks, resets, staging, cleanup, hooks, filters or lazy fetches run.
Submodules, nested repositories, special files and symlink metadata stop.
Split indexes (including leftover sharedindex.* metadata) are unsupported and
stop without following their backing files. Raw blob comparison conservatively
protects checkouts transformed by clean filters.
"""
import argparse
import hashlib
import json
import os
import selectors
from pathlib import Path
import stat
import subprocess
import sys
import time

SCHEMA = "luucycle.git-baseline.v1"
DEFAULT_MAX_SECONDS = 120.0
DEFAULT_MAX_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_FILES = 100_000


class BaselineError(ValueError):
    """An incomplete or unsafe observation must stop the caller."""


class Budget:
    """Cumulative bounds for both complete inventory passes."""

    def __init__(self, seconds, byte_limit, file_limit):
        require(seconds > 0 and byte_limit > 0 and file_limit > 0,
                "Collection limits must be positive")
        self.deadline = time.monotonic() + seconds
        self.byte_limit = byte_limit
        self.file_limit = file_limit
        self.bytes = 0
        self.files = 0

    def check(self):
        require(time.monotonic() <= self.deadline, "Collection time limit exceeded; observation is incomplete")

    def add_bytes(self, count):
        self.check()
        self.bytes += count
        require(self.bytes <= self.byte_limit,
                "Collection byte limit exceeded; observation is incomplete")

    def add_file(self):
        self.check()
        self.files += 1
        require(self.files <= self.file_limit,
                "Collection file limit exceeded; observation is incomplete")


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args, allowed=(0,), budget=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_NO_LAZY_FETCH"] = "1"
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo), *args]
    if budget is None:
        result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        # Bound pipes while draining them, rather than measuring only after an
        # arbitrarily large Git listing has already been buffered in memory.
        budget.check()
        with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            output = [bytearray(), bytearray()]
            try:
                with selectors.DefaultSelector() as selected:
                    selected.register(process.stdout, selectors.EVENT_READ, 0)
                    selected.register(process.stderr, selectors.EVENT_READ, 1)
                    while selected.get_map():
                        budget.check()
                        events = selected.select(max(0.001, budget.deadline - time.monotonic()))
                        for key, _ in events:
                            data = os.read(key.fileobj.fileno(), 65536)
                            if not data:
                                selected.unregister(key.fileobj)
                                continue
                            budget.add_bytes(len(data))
                            output[key.data].extend(data)
                    budget.check()
                    process.wait(timeout=max(0.001, budget.deadline - time.monotonic()))
                result = subprocess.CompletedProcess(command, process.returncode, bytes(output[0]), bytes(output[1]))
            except subprocess.TimeoutExpired as exc:
                raise BaselineError("Collection time limit exceeded during Git observation; observation is incomplete") from exc
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
    if result.returncode not in allowed:
        raise BaselineError("Git observation failed")
    return result.stdout


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def file_record(path, *, dir_fd=None, algorithm="sha1", budget=None):
    info = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    if stat.S_ISLNK(info.st_mode):
        data = os.fsencode(os.readlink(path, dir_fd=dir_fd))
        kind, size, sha256 = "symlink", len(data), digest(data)
        blob = hashlib.new(algorithm, b"blob " + str(size).encode() + b"\0" + data)
    elif stat.S_ISREG(info.st_mode):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        try:
            require(fingerprint(os.fstat(fd)) == fingerprint(info), "File changed before read")
            hasher, size = hashlib.sha256(), 0
            blob = hashlib.new(algorithm, b"blob " + str(info.st_size).encode() + b"\0")
            while True:
                if budget is not None:
                    budget.check()
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                if budget is not None:
                    budget.add_bytes(len(block))
                hasher.update(block)
                blob.update(block)
                size += len(block)
            require(fingerprint(os.fstat(fd)) == fingerprint(info), "File mutated during read")
            kind, sha256 = "file", hasher.hexdigest()
        finally:
            os.close(fd)
    else:
        raise BaselineError("Unsupported file type")
    require(fingerprint(os.stat(path, dir_fd=dir_fd, follow_symlinks=False)) == fingerprint(info),
            "File changed during read")
    return {"kind": kind, "mode": stat.S_IMODE(info.st_mode), "size": size,
            "sha256": sha256, "git_oid": blob.hexdigest()}


def inventory(repo, algorithm, budget):
    files, directories, observations = {}, {}, {}
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    def visit(fd, prefix):
        initial = os.fstat(fd)
        observations[prefix] = fingerprint(initial)
        for name in sorted(os.listdir(fd)):
            budget.check()
            if name == ".git":
                require(not prefix, "Nested repository is unsupported")
                continue
            path = prefix + "/" + name if prefix else name
            valid_path(path)
            budget.add_file()
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            observations[path] = fingerprint(info)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, flags, dir_fd=fd)
                try:
                    require(fingerprint(os.fstat(child)) == fingerprint(info), "Directory changed")
                    directories[path] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
                    visit(child, path)
                finally:
                    os.close(child)
            else:
                files[path] = file_record(name, dir_fd=fd, algorithm=algorithm, budget=budget)
            require(fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) == fingerprint(info),
                    "Inventory changed during read")
        require(fingerprint(os.fstat(fd)) == fingerprint(initial), "Directory mutated during read")
    fd = os.open(repo, flags)
    try:
        visit(fd, "")
    finally:
        os.close(fd)
    return files, directories, observations


def capture(repo, targets=(), *, max_seconds=DEFAULT_MAX_SECONDS,
            max_bytes=DEFAULT_MAX_BYTES, max_files=DEFAULT_MAX_FILES):
    # Neither pass retries: a moving source must be reported, not silently rebaselined.
    budget = Budget(max_seconds, max_bytes, max_files)
    targets = tuple(targets)
    first, observed = capture_once(repo, targets, budget)
    second, observed_again = capture_once(repo, targets, budget)
    require(first == second and observed == observed_again, "Source changed between stable reads")
    return validate(first)


def capture_once(repo, targets, budget):
    repo = Path(repo).absolute()
    require(repo.resolve() == repo and repo.is_dir(), "Repository must be a physical directory")
    require(os.fsdecode(git(repo, "rev-parse", "--show-toplevel", budget=budget).removesuffix(b"\n")) == str(repo),
            "Source must be the repository root")
    targets = [valid_path(os.fspath(p)) for p in targets]
    require(len(targets) == len(set(targets)), "Duplicate target")
    require(not (repo / ".git").is_symlink(), "Symlink Git metadata is unsafe")
    git_dir = Path(os.fsdecode(git(repo, "rev-parse", "--absolute-git-dir", budget=budget).removesuffix(b"\n")))
    # --git-path with absolute formatting resolves symlinks, hiding unsafe indexes.
    index_path = git_dir / "index"
    index_before, index_observed = regular_source(index_path, absent=True, budget=budget)
    # Git may follow split-index backing links even though index itself is safe.
    require(not any(p.name.startswith("sharedindex.") for p in git_dir.iterdir()),
            "Split indexes are unsupported (sharedindex.* metadata present)")
    head_before, head_observed = regular_source(git_dir / "HEAD", budget=budget)
    algorithm = git(repo, "rev-parse", "--show-object-format", budget=budget).decode().strip()
    require(algorithm in ("sha1", "sha256"), "Unsupported Git object format")
    head = {"oid": git(repo, "rev-parse", "--verify", "--quiet", "HEAD", allowed=(0, 1), budget=budget).decode().strip() or None,
            "ref": git(repo, "symbolic-ref", "-q", "HEAD", allowed=(0, 1), budget=budget).decode().strip() or None,
            "entries": [], "sha256": digest(head_before)}
    if head["oid"] is None:
        require(head["ref"] is not None, "Invalid unborn HEAD")
        require(not git(repo, "show-ref", "--verify", "--quiet", head["ref"], allowed=(1,), budget=budget), "Invalid unborn reference")
    rows = git(repo, "ls-tree", "-r", "-z", "HEAD", budget=budget) if head["oid"] else b""
    for row in rows.split(b"\0"):
        if row:
            metadata, path = row.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            require(kind == "blob", "Submodules are unsupported")
            head["entries"].append({"path": os.fsdecode(path), "mode": mode, "oid": oid, "stage": 0})
    entries = []
    for entry in git(repo, "ls-files", "--stage", "-z", budget=budget).split(b"\0"):
        if entry:
            metadata, path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode().split()
            require(mode != "160000", "Submodules are unsupported")
            entries.append({"path": os.fsdecode(path), "mode": mode,
                            "oid": oid, "stage": int(stage)})
    files, directories, observations = inventory(repo, algorithm, budget)
    index_after, index_observed_after = regular_source(index_path, absent=True, budget=budget)
    require(index_before == index_after and index_observed == index_observed_after,
            "Index mutated during capture")
    observations[".git/index"] = index_observed
    head_after, head_observed_after = regular_source(git_dir / "HEAD", budget=budget)
    require(head_before == head_after and head_observed == head_observed_after,
            "HEAD mutated during capture")
    observations[".git/HEAD"] = head_observed
    for target in targets:
        require(target not in directories, "Targets must name files, links or absent paths, not directories")
        parts = target.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            require(ancestor not in files, "Target ancestor is not a directory")
    targets = {str(p): files.get(str(p), {"kind": "absent"}) for p in targets}
    root_info = repo.stat()
    state = {"repo": str(repo), "identity": {"device": root_info.st_dev, "inode": root_info.st_ino,
                                            "git_dir": str(git_dir)}, "head": head,
             "index": {"sha256": digest(index_before) if index_before is not None else None, "entries": entries},
             "files": files, "targets": targets, "directories": directories,
             "counts": {"files": len(files), "targets": len(targets),
                        "directories": len(directories), "index_entries": len(entries),
                        "head_entries": len(head["entries"])}}
    return {"schema": SCHEMA, "state": state, "sha256": digest(canonical(state))}, observations


def require(condition, message="Invalid or incomplete snapshot"):
    if not condition:
        raise BaselineError(message)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def valid_hash(value, lengths=(64,)):
    return (type(value) is str and len(value) in lengths
            and all(c in "0123456789abcdef" for c in value))


def valid_path(value):
    require(type(value) is str and value and "\0" not in value)
    require(not value.startswith("/") and all(
        p not in ("", ".", "..", ".git") for p in value.split("/")), "Unsafe path")
    return value


def validate_record(record, absent=False):
    if absent and record == {"kind": "absent"}:
        return
    keys(record, ("kind", "mode", "size", "sha256", "git_oid"))
    require(record["kind"] in ("file", "symlink"))
    require(type(record["mode"]) is int and 0 <= record["mode"] <= 0o7777)
    require(type(record["size"]) is int and record["size"] >= 0)
    require(valid_hash(record["sha256"]) and valid_hash(record["git_oid"], (40, 64)))


def validate(snapshot):
    keys(snapshot, ("schema", "state", "sha256"))
    require(snapshot["schema"] == SCHEMA)
    s = snapshot["state"]
    keys(s, ("repo", "identity", "head", "index", "files", "targets", "directories", "counts"))
    keys(s["identity"], ("device", "inode", "git_dir"))
    require(all(type(s["identity"][k]) is int and s["identity"][k] >= 0 for k in ("device", "inode")))
    require(type(s["identity"]["git_dir"]) is str and Path(s["identity"]["git_dir"]).is_absolute())
    require(type(s["directories"]) is dict)
    for path, record in s["directories"].items():
        valid_path(path)
        keys(record, ("kind", "mode"))
        require(record["kind"] == "directory" and type(record["mode"]) is int
                and 0 <= record["mode"] <= 0o7777)
    require(type(s["repo"]) is str and Path(s["repo"]).is_absolute())
    keys(s["head"], ("oid", "ref", "entries", "sha256"))
    require(valid_hash(s["head"]["sha256"]))
    require(s["head"]["oid"] is None or valid_hash(s["head"]["oid"], (40, 64)))
    require(s["head"]["ref"] is None or (type(s["head"]["ref"]) is str
            and s["head"]["ref"].startswith("refs/")))
    keys(s["index"], ("sha256", "entries"))
    require(s["index"]["sha256"] is None or valid_hash(s["index"]["sha256"]))
    require(type(s["index"]["entries"]) is list and type(s["head"]["entries"]) is list)
    seen = set()
    for source, entry in [(scope, e) for scope in ("head", "index") for e in s[scope]["entries"]]:
        keys(entry, ("path", "mode", "oid", "stage"))
        valid_path(entry["path"])
        require(entry["mode"] in ("100644", "100755", "120000", "160000"))
        require(valid_hash(entry["oid"], (40, 64)))
        require(type(entry["stage"]) is int and entry["stage"] in range(4))
        identity = (source, entry["path"], entry["stage"])
        require(identity not in seen)
        seen.add(identity)
    for scope in ("files", "targets"):
        require(type(s[scope]) is dict)
        for path, record in s[scope].items():
            valid_path(path)
            validate_record(record, absent=scope == "targets")
            if scope == "targets":
                require(path not in s["directories"], "Directory target")
                require(record == s["files"].get(path, {"kind": "absent"}))
    require(not (s["files"].keys() & s["directories"].keys()), "Overlapping inventory kinds")
    for path in s["files"].keys() | s["directories"].keys():
        parent = path.rpartition("/")[0]
        require(not parent or parent in s["directories"], "Missing inventory parent")
    require(s["head"]["oid"] is not None or (s["head"]["ref"] is not None and not s["head"]["entries"]))
    require(s["index"]["sha256"] is not None or not s["index"]["entries"])
    counts = {"files": len(s["files"]), "targets": len(s["targets"]),
              "directories": len(s["directories"]), "index_entries": len(s["index"]["entries"]),
              "head_entries": len(s["head"]["entries"])}
    require(type(s["counts"]) is dict and all(type(n) is int for n in s["counts"].values()))
    require(s["counts"] == counts)
    require(valid_hash(snapshot["sha256"]) and snapshot["sha256"] == digest(canonical(s)),
            "Snapshot checksum mismatch")
    return snapshot


def regular_source(path, absent=False, budget=None):
    """Read a regular metadata/source file through no-follow directory handles."""
    path = Path(path).absolute()
    require(path.resolve() == path, "Symlink or noncanonical source is unsafe")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open("/", flags)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            if absent:
                return None, None
            raise
        try:
            initial = os.fstat(fd)
            require(stat.S_ISREG(initial.st_mode), "Source must be a regular file")
            blocks = []
            while True:
                if budget is not None:
                    budget.check()
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                if budget is not None:
                    budget.add_bytes(len(block))
                blocks.append(block)
            require(fingerprint(initial) == fingerprint(os.fstat(fd)), "Source mutated during read")
            require(fingerprint(initial) == fingerprint(os.stat(path.name, dir_fd=parent, follow_symlinks=False)),
                    "Source replaced during read")
            return b"".join(blocks), fingerprint(initial)
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise BaselineError("Non-finite JSON number")
    raw, _ = regular_source(path)
    if raw is None:
        raise BaselineError("Missing JSON source")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def protected_paths(state):
    """Protect raw initial dirt, including ignored and assume-unchanged bytes.

    Raw Git blobs are compared without clean filters: transformed checkouts are
    conservatively protected. An expected delta can never waive this protection.
    """
    head = {e["path"]: (e["mode"], e["oid"]) for e in state["head"]["entries"]}
    index = {e["path"]: (e["mode"], e["oid"]) for e in state["index"]["entries"] if e["stage"] == 0}
    dirty = {e["path"] for e in state["index"]["entries"] if e["stage"] != 0}
    dirty.update(p for p in head.keys() | index.keys() if head.get(p) != index.get(p))
    for path in state["files"].keys() | index.keys():
        record = state["files"].get(path)
        if record is None:
            dirty.add(path)
            continue
        mode = "120000" if record["kind"] == "symlink" else ("100755" if record["mode"] & 0o111 else "100644")
        if index.get(path) != (mode, record["git_oid"]):
            dirty.add(path)
    return dirty


def compare(before, after, expected=None):
    validate(before)
    validate(after)
    require(before["state"]["repo"] == after["state"]["repo"], "Repository mismatch")
    require(before["state"]["identity"] == after["state"]["identity"], "Repository identity changed")
    require(before["state"]["targets"].keys() == after["state"]["targets"].keys(), "Target selection changed")
    changes = []
    for scope in ("head", "index", "files", "directories", "targets"):
        a, b = before["state"][scope], after["state"][scope]
        if scope in ("files", "directories", "targets"):
            for path in sorted(a.keys() | b.keys()):
                if a.get(path) != b.get(path):
                    changes.append({"scope": scope, "path": path,
                                    "before": a.get(path), "after": b.get(path)})
        elif a != b:
            changes.append({"scope": scope, "path": None, "before": a, "after": b})
    expected_changes = []
    if expected is not None:
        keys(expected, ("baseline_sha256", "changes"))
        require(expected["baseline_sha256"] == before["sha256"], "Expected manifest baseline mismatch")
        require(type(expected["changes"]) is list)
        seen = set()
        for change in expected["changes"]:
            keys(change, ("scope", "path", "before", "after"))
            require(change["scope"] in ("files", "directories", "targets"),
                    "HEAD and index changes cannot be exempted")
            valid_path(change["path"])
            identity = (change["scope"], change["path"])
            require(identity not in seen, "Duplicate expected delta")
            seen.add(identity)
            require(change in changes, "Expected delta not observed exactly")
            expected_changes.append(change)
    dirty = protected_paths(before["state"])
    protected = [d for d in changes if d["scope"] in ("files", "targets") and d["path"] in dirty]
    unexpected = [d for d in changes if d not in expected_changes]
    return {"status": "STOP" if unexpected or protected else "PASS", "changes": changes,
            "unexpected": unexpected, "protected_changes": protected}


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise BaselineError("Invalid CLI arguments; use --help")


def main(argv=None):
    def positive_int(value):
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a positive integer") from exc
        if result <= 0:
            raise argparse.ArgumentTypeError("must be a positive integer")
        return result

    def positive_float(value):
        try:
            result = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a positive number") from exc
        if result <= 0:
            raise argparse.ArgumentTypeError("must be a positive number")
        return result

    parser = JsonParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture")
    cap.add_argument("--repo", required=True)
    cap.add_argument("--target", action="append", default=[])
    cap.add_argument("--max-seconds", type=positive_float, default=DEFAULT_MAX_SECONDS)
    cap.add_argument("--max-bytes", type=positive_int, default=DEFAULT_MAX_BYTES)
    cap.add_argument("--max-files", type=positive_int, default=DEFAULT_MAX_FILES,
                     help="maximum inventory entries, counting files and directories")
    chk = commands.add_parser("check")
    chk.add_argument("--repo", required=True)
    chk.add_argument("--snapshot", required=True)
    chk.add_argument("--expected", help="JSON manifest of exact, baseline-bound expected deltas")
    chk.add_argument("--max-seconds", type=positive_float, default=DEFAULT_MAX_SECONDS)
    chk.add_argument("--max-bytes", type=positive_int, default=DEFAULT_MAX_BYTES)
    chk.add_argument("--max-files", type=positive_int, default=DEFAULT_MAX_FILES,
                     help="maximum inventory entries, counting files and directories")
    try:
        args = parser.parse_args(argv)
        if args.command == "capture":
            result = capture(args.repo, args.target, max_seconds=args.max_seconds,
                             max_bytes=args.max_bytes, max_files=args.max_files)
        else:
            before = validate(load_json(args.snapshot))
            require(before["state"]["repo"] == str(Path(args.repo).absolute()), "Repository mismatch")
            after = capture(args.repo, before["state"]["targets"], max_seconds=args.max_seconds,
                            max_bytes=args.max_bytes, max_files=args.max_files)
            result = compare(before, after, load_json(args.expected) if args.expected else None)
        print(canonical(result).decode("ascii"), end="")
        return 1 if result.get("status") == "STOP" else 0
    except (BaselineError, OSError, ValueError, RecursionError) as exc:
        print(canonical({"status": "STOP", "error": str(exc)}).decode("ascii"), end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
