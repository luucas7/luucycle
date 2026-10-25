# Git baseline capture and comparison

`scripts/git_baseline.py` observes a checkout without cleaning, staging, committing
or restoring it. A dirty checkout is valid input. Capture before the first builder,
retain the original snapshot and its digest outside the checkout, and compare the
same repository and targets before accepting the resulting changes.

## Capture and check

Use an already authorized artifact root outside the checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/git_baseline.py" capture --repo '<repo-root>' --target 'path/to/file' --target 'path/to/not-yet-created-file' > '<artifact-root>/baseline.json'
PYTHONDONTWRITEBYTECODE=1 python3 -B "<skill-root>/scripts/git_baseline.py" check --repo '<repo-root>' --snapshot '<artifact-root>/baseline.json'
```

Each complete observation is bounded by defaults of 120 seconds, 1 GiB read or
enumerated from Git, and 100,000 filesystem inventory entries (files and
directories). Set `--max-seconds`, `--max-bytes`, and `--max-files` on both
commands to choose tighter or larger bounds. Capture spends the same cumulative
budget across its two full stability passes; check spends it on its fresh
two-pass observation. A limit breach returns exit 2 with `status: STOP` and names
the exceeded limit. No partial artifact is emitted and no ignored path is skipped
to make a bounded result look exhaustive. Choose bounds that cover the whole
checkout, including ignored files and dependency trees, or stop without claiming
a complete baseline.

Require capture exit 0 before using the artifact. Capture records HEAD, raw and
semantic index, tracked/untracked/ignored physical file contents and modes,
directory inventory, and explicit target presence or absence. Source contents
are hashed, not printed. Preserve the original snapshot's externally recorded
SHA-256; its internal digest is an integrity check, not authentication or a backup.

A target must designate a file or absent file, not a directory. Empty and dot
paths both designate the checkout directory and stop. Symlinked metadata or
snapshot sources, special files, submodules/nested repositories, unsafe paths,
unreadable files and unstable observations fail closed. Split indexes are
unsupported: any `sharedindex.*` metadata, including stale backing files or
symlinks, causes STOP before index enumeration. Keep this explicit limitation
rather than following external metadata or automatically converting the index.
The implementation uses
POSIX directory handles; portability beyond the tested Linux environment remains
unverified. Existing file symlinks are inventoried without following their targets.

## Expected changes and preservation

`check` returns PASS only when every observed delta is accounted for and no
protected initial change was touched. It returns exit 1 for a valid comparison
with STOP, or exit 2 for an invalid/incomplete observation. Retain the differences
for review; always preserve the working tree instead of resetting it to obtain PASS.

An optional `--expected '<manifest.json>'` accepts exactly:

```json
{"baseline_sha256":"<original-snapshot-internal-sha256>","changes":[]}
```

Populate `changes` with the exact observed delta objects (`scope`, `path`,
`before`, `after`) from the comparison and review their content. Regular file
records contain `kind`, permission `mode`, `size`, `sha256` and `git_oid`; file
kinds and fields must match the actual snapshot. Directory and target deltas
are separate entries. The manifest is baseline-bound and checks exact deltas,
not broad path allowlists. HEAD/index changes cannot be exempted.

Initial staged, unstaged, untracked and ignored content is protected even when
listed in an expected manifest. An authorized edit to an already dirty target
therefore remains STOP for preservation review; the tool cannot determine whether
its original hunks survived. Review against retained original evidence and report
that limit separately. Never infer preservation solely from a path being allowed.

## Verification limits

The collector uses repeated inventories and per-file stability checks within the
configured time, byte, and entry limits. These are
not atomic locks: adversarial changes that revert between observations, or writes
after the last read, remain outside proof. Snapshots contain hashes, not recovery
copies. Full ignored-file hashing can be expensive in dependency/build trees;
choose a bounded checkout or stop with the cost rather than silently excluding
files and claiming exhaustive coverage.

Audit without artifact permission must retain observations in permitted existing
records or memory; it does not create a snapshot file merely because capture is
read-only with respect to the checkout. Validate capture/check behavior with
`tests/test_git_baseline.py`, keeping temporary repositories under authorized
scratch storage.
