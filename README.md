# 274bot-arch

Operator-owned architecture checker and protected rules for 274bot.

## Running

The checker requires Python 3.11 or newer. Product CI pins Python 3.14.8. The
syntax-aware source checks require `rust-analyzer 0.3.3081-standalone` on
`PATH`, with SHA-256
`fd89304c85f6c1996b036ea8f2c9ad9d3e25a197dbd713661c7fe51ec9dc8e49`.

From this repository:

```bash
python3 -B check.py --self-test
python3 -B check.py --root /path/to/274bot
```

`--root` is required for a product-tree check. The self-test uses disposable
fixtures and does not read a product tree.

The protected product workflow fetches `274bot-arch` `main` at depth 1, checks
the parser pin, runs the checker's self-test, then checks the candidate tree.
It does not run checker scripts from the candidate. The checker and protected
rules are operator-controlled; only the operator publishes reviewed changes to
`274bot-arch` `main`.

## Checks

The graph checker reads Cargo manifests directly, without Cargo resolution. It
checks the protected workspace and path-package identities, all dependency
kinds and target cfgs, and exact edge-kind permissions in `policy.toml`. It
also evaluates default/dev activation and supported configurations, including
forbidden features and required optional dependencies. Unresolved local package
identities fail closed.

An `allow.features` table can restrict explicit dependency features by edge
kind. Such an edge must set `default-features = false`. The bake and planner
normal API edges allow no feature request; their dev edges allow only
`embedded-game-data`, not API raw packet recorders. Inherited workspace feature
requests are checked too.

Graph source hygiene rejects candidate copies of protected `policy.toml` and
`vendor-manifests.json`, Cargo configuration files that could override the
protected graph, and case variants of `Cargo.toml`. Git-sourced dependencies,
patches, and replacements are refused. Root path patches and replacements must
be explicitly listed in `policy.toml`.

The source checker performs syntax-aware navigation and API seam checks using
the pinned `rust-analyzer`. It enforces the protected script navigation/import
and frontend-core seam boundaries, with semantic foreign-type classification.
It does not use a graph-provenance baseline or a source-file ownership census.

Ownership classes are inferred from source, not an exhaustive type registry.
`seam-exceptions.json` contains only the 27 exact previously admitted findings,
with reasons: 15 owning findings and 12 test-nav imports. The narrow built-in
test whitelist is unchanged. Candidate inventory rows cannot admit a violation.
Those existing findings are one later cleanup item, not new permission.

## What remains

- Protected crate-edge kinds and features: audit catch R1.
- Foreign navigation/client boundaries, including macro paths and test imports:
  R2, R4, R5 and R6.
- No whole-crate adapter re-export through `frontend-core`: R3.
  The manifest identifies a crate root without parsing its body. Type exports
  still resolve their actual definitions.
- Owning/borrowed/scalar seam rules, including owning Clone and public fields:
  R6.
- Operator-only rules and protected-copy CI: R3's attempted checker edit.

Per-file ownership, provenance baselines, thread-local inventories and release
checker branches are removed. The client manifest pin stays because the product
has no existing `cargo-deny` source rule; this cut adds no new tool.

## Vendored client manifests

Every `Cargo.toml` below `vendor/fr-client-rust/` is pinned by exact path and
UTF-8 contents in `vendor-manifests.json`. Added, removed, or changed manifests
are reported. The checker does not interpret the client workspace's member
lists, exclusions, globs, or inheritance; its manifest pin is a separate
protected input. Directory symlinks below that tree are refused.

Print the digest for a product tree:

```bash
python3 -B vendor_manifests.py /path/to/274bot
```

To prepare a replacement pin for operator review:

```bash
python3 -B vendor_manifests.py --emit-pin /path/to/274bot > vendor-manifests.json
```

Review the changed paths and contents. The operator must publish any approved
pin update to `274bot-arch` `main` before the corresponding product change
lands. The checker reads committed manifests only; it does not run build
scripts that might rewrite them during a CI job.

## Changing protected rules

Submit a reviewed proposal to the operator for changes to the graph allowlist,
supported configurations, vendored path-package bindings, client-manifest pin,
or checker. Include the reason for each permission or boundary change and
coordinate publication with the product change. The operator reviews and
publishes approved changes to `274bot-arch` `main` before they are relied on by
the product.

There is no graph-provenance baseline or baseline-emission command. Product
trees cannot publish or extend protected checker rules.
