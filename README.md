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

`policy.toml` and `graph-provenance.json` are loaded beside the checker.
Ownership, inventories, and foreign-type classifications come only from the
candidate's `tools/architecture/` directory. A candidate `policy.toml` or
`graph-provenance.json` in that directory is an error, not an override.

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
A non-member cannot impersonate a member through `package = "<member>"`.

Manifest scanning gives a deterministic cross-platform permission union.
It needs no registry cache, lockfile repair, network access, or Cargo resolver
behavior. `cargo metadata --offline --locked` would depend on the local
registry cache and would not provide this all-target declaration check.
Unsupported or unresolved local identities fail closed.

## Changing rules

Prepare a reviewed `274bot-arch` commit for any of these changes:

- a new crate edge, including a new target cfg or cross-crate feature request;
- a new edge kind;
- a migration allowance;
- optional-dependency activation in a supported configuration;
- a vendored path package or its protected manifest binding;
- a checker change.

Edit `policy.toml` where required. In that same arch commit, regenerate the
baseline against the candidate with one command:

```bash
python3 -B check.py --emit-provenance-baseline /path/to/candidate > graph-provenance.json
```

Review the policy and baseline diff together. Give the operator the arch
commit or bundle. The operator publishes it to `274bot-arch` `main` before
the product change lands. Update product architecture documentation for a
boundary change, and run the checker against the merged product tree.

The plain JSON baseline protects cross-crate edge declarations, cross-crate
feature requests, and optional-dependency activation. It does not record
purely local feature names. A local feature that activates no optional
dependency and no cross-crate edge needs no operator commit. Ordinary code,
ownership, seam-type, and inventory changes also need no operator commit.

The baseline only grows without operator action: removed edges retain permission, so a later candidate can restore them without another arch commit.

There are no receipts, hashes, signatures, approvals, or epochs for the baseline.
