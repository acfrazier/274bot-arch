# 274bot-arch

Operator-owned architecture checker and source-of-truth rules for 274bot.

## Running

The checker requires Python 3.11 or newer. Product CI pins Python 3.14.8.
It requires `rust-analyzer 0.3.3081-standalone` on `PATH`, with SHA-256
`fd89304c85f6c1996b036ea8f2c9ad9d3e25a197dbd713661c7fe51ec9dc8e49`.

From this repository:

```bash
python3 -B check.py --self-test
python3 -B check.py --root /path/to/274bot
```

`--root` is required for a tree check. The self-test does not read a product tree.
The protected product workflow clones `https://github.com/acfrazier/274bot-arch.git`
`main`, at depth 1, into `$RUNNER_TEMP`. The workflow step checks the parser
pin, runs the cloned checker's self-test, then checks `$GITHUB_WORKSPACE`.
CI never executes `tools/architecture/run.sh` or any other candidate-tree
script to judge the candidate. The token guard protects the workflow itself.

For local convenience only, use the product runner:

```bash
tools/architecture/run.sh
tools/architecture/run.sh --root /path/to/tree
```

With no `--root`, that runner checks its product checkout. `ARCH_REPO` selects
the checker source locally. The default remote fetches `main`. A local clone
uses its selected `HEAD` for pre-push proof. `ARCH_CACHE_DIR` selects the
bare-Git cache, defaulting to `${XDG_CACHE_HOME:-$HOME/.cache}/274bot-arch`.
The runner archives the selected checker commit, checks the parser pin, runs
the self-test, then checks the product. CI does not use this runner.

`policy.toml`, `graph-provenance.json`, and `vendor-manifests.json` are loaded beside the checker.
Ownership, inventories, and foreign-type classifications come only from the
candidate's `tools/architecture/` directory. Candidate copies of protected rules
in that directory are errors, not overrides.

## Graph identity

The checker reads manifests without Cargo resolution. It scans all target
cfgs, dependency-table spellings, and protected path packages. A path package
is identified by its canonical `Cargo.toml` path, not its dependency key or
claimed package name. A non-member path package must appear in
`policy.toml` `[workspace.path_packages]`. Each label binds one package name
to one tree-relative manifest. Symlink substitutions are refused.

The current list covers the vendored client, client-play, and dear-imgui-wgpu.
Every listed manifest is scanned, even when unused. Path dependencies,
`workspace.dependencies`, `[patch]`, and `[replace]` must resolve to members
or listed manifests. Edges from a listed package require ordinary protected
`[[allow]]` permissions, including edges back into the product workspace.

The checker refuses a `git` key in any dependency table, target table,
`[workspace.dependencies]`, `[patch.*]`, or `[replace]` entry.
The refusal names the manifest file and the entry.
The checker never reads a git crate's manifest.
A git crate could carry a crate edge or a feature request into a local package.
Vendored manifests need no separate rule. The pin below already freezes them.

Only root `[patch.*]` and `[replace]` entries listed by name and path in
`policy.toml` `[root_patches]` may appear in the product root.
The list now holds only `dear-imgui-wgpu` at `vendor/dear-imgui-wgpu-0.15.1`.
A root patch makes a local package reachable from every external crate.
Any other root patch or replacement needs an operator commit that adds it.
Registry dependencies stay allowed. A crates.io crate cannot name a local path package without a root patch, and the root patch list covers that route.
A non-member cannot impersonate a member through `package = "<member>"`.
Product workspace `members`, `default-members`, and `exclude` entries must
resolve to protected manifests. The client workspace uses the exact pin below.
Dependency aliases are tracked by package name, not by alias or version.

The checker refuses `.cargo/config` and `.cargo/config.toml` anywhere in the
candidate tree, including vendored trees and symlinks. Directory and file names
are matched without ASCII case distinctions. These files can override the
graph that `274bot-arch` protects.
Unicode look-alike names are outside this refusal because Cargo on Linux does not read them.

The checker refuses any file whose name matches `cargo.toml` without ASCII
case distinctions but is not exactly `Cargo.toml`.
This rule covers the whole candidate tree, including vendored trees and symlinks.
On a case-insensitive file system, that file replaces the scanned `Cargo.toml`.
The macOS and Windows release builds use such file systems.

Default-feature and dev-dependency activation is checked for every protected
member and listed path package. Named configurations add their own activation
checks. A package does not escape these checks when no configuration reaches it.

Manifest scanning gives a deterministic cross-platform permission union.
It needs no registry cache, lockfile repair, network access, or Cargo resolver
behavior. `cargo metadata --offline --locked` would depend on the local
registry cache and would not provide this all-target declaration check.
Unsupported or unresolved local identities fail closed.

### Vendored client manifests

Every `Cargo.toml` below `vendor/fr-client-rust/` is a protected input.
`vendor-manifests.json` stores their expected paths and exact UTF-8 contents.
One SHA-256 digest covers the sorted sequence of path and file-byte pairs.
Each path and content field has an eight-byte big-endian byte length before it.
The digest is identity data for a protected input, like policy data, not bookkeeping.

The checker refuses added, removed, or changed manifests and names each difference.
A case variant of `Cargo.toml` in that tree is refused by name and never enters the pin.
An operator commit to this repository must update the pin before that product change lands.
The checker does not interpret the client workspace's member lists, exclusions, globs, or inheritance.
The pinned set has no `workspace = true` dependencies.
The pin command and checker refuse a pin that introduces such dependencies.
Product workspace checks remain unchanged.
Directory symlinks below `vendor/fr-client-rust/` are refused.
This applies to every directory in that tree, not only to manifest paths.

One limit stays with review. A product build script can rewrite a vendored
manifest on disk during a CI job, between steps.
The checker reads committed manifests only. It does not run build scripts.
A new `build.rs` needs an ownership row, so a reviewer sees it.

Print the digest for a product tree:

```bash
python3 -B vendor_manifests.py /path/to/274bot
```

After fork review, generate the complete replacement pin in this repository:

```bash
python3 -B vendor_manifests.py --emit-pin /path/to/274bot > vendor-manifests.json
```

Review its changed paths and contents, then commit it with any required policy changes.
A fork pointer change needs no pin update when all vendored manifests remain byte-identical.


## Changing rules

Prepare a reviewed `274bot-arch` commit for any of these changes:

- a new crate edge, including a new target cfg or cross-crate feature request;
- a new edge kind;
- a migration allowance;
- optional-dependency activation in a protected package or supported configuration;
- a vendored path package or its protected manifest binding;
- any added, removed, or changed client `Cargo.toml`, including comments and local features;
- a root `[patch.*]` or `[replace]` entry, listed by name and path in `[root_patches]`;
- a checker change.

Edit `policy.toml` where required. First merge current `dev` into the branch
being merged. In the same arch commit, regenerate the baseline from that
merged branch tree:

```bash
python3 -B check.py --emit-provenance-baseline /path/to/merged-branch > graph-provenance.json
```

Review the policy and baseline diff together. Review removed records.
Retain records that other active branches still need.
Give the operator the arch commit or bundle.
The operator publishes it to `274bot-arch` `main` before the product change lands.
Update product architecture documentation for a boundary change.
Run the checker against the merged product tree.

The plain JSON baseline protects cross-crate edge declarations, cross-crate
feature requests, and optional-dependency activation. It does not record
purely local feature names. Outside the pinned client manifests, a local feature
that activates no optional dependency or cross-crate edge needs no operator commit.
Ordinary code, ownership, seam-type, and inventory changes also need no operator commit.

The baseline only grows without operator action: removed edges retain permission, so a later candidate can restore them without another arch commit.

There are no receipts, hashes, signatures, approvals, or epochs for the baseline.
