# 274bot-arch

Operator-owned architecture checker and source-of-truth rules for 274bot.

## Running

The checker requires Python 3.11 or newer (`tomllib` is part of the standard
library). Product CI pins Python 3.14.8. It also requires
`rust-analyzer 0.3.3081-standalone` on `PATH` (SHA-256
`fd89304c85f6c1996b036ea8f2c9ad9d3e25a197dbd713661c7fe51ec9dc8e49`); the
product runner verifies both its version and digest before starting the checker.

From this repository:

```bash
python3 -B check.py --self-test
python3 -B check.py --root /path/to/274bot
```

For the product's normal local and CI path, run its
`tools/architecture/run.sh` from the product checkout:

```bash
tools/architecture/run.sh
tools/architecture/run.sh --root /path/to/tree
```

With no `--root`, the product runner checks the product checkout containing
the script. `ARCH_REPO` selects the checker source: the default remote always
fetches `main`; a local clone uses its selected `HEAD` for pre-push proof.
`ARCH_CACHE_DIR` selects the bare-Git fetch cache and defaults to
`${XDG_CACHE_HOME:-$HOME/.cache}/274bot-arch`.

The runner archives the selected checker commit to a temporary directory,
runs its disposable graph self-test, then checks the product tree.
The protected graph policy (`policy.toml`) and `graph-provenance.json` are
loaded beside the checker; `policy.toml` keeps workspace, allowance, migration,
and feature-configuration rows together. Ownership, inventories, and foreign
type classifications are loaded only from the checked product tree's
`tools/architecture/` directory; checker-side copies are never fallbacks.

`graph-provenance.json` is plain generated data that protects exceptional
dependency provenance and supported-feature/optional-dependency activation.
Update it only when a reviewed change adds optional-dependency activation or
exceptional provenance; do not update it for ordinary code, ownership,
inventory, seam-type, or effective-edge changes without either of those
additions. From this repository, regenerate it against the reviewed tree with
`python3 -B check.py --emit-provenance-baseline /path/to/tree > graph-provenance.json`,
review the diff, and have the operator commit it with any required policy
change. There are no hashes, signatures, approvals, or epochs for the baseline.

## Rule-change and rollout order

The checker extraction is staged as three reviewable changes: first copy the
live checker, protected graph policy, and provenance baseline; second add the
narrow `PhantomData` marker rule and fixtures; third, after the first two
changes are proved, remove the product's `tools/architecture/*.py` ownership
rows and assign `tools/architecture/run.sh` to T1. Keep ownership, inventory,
and foreign-type data in the product tree beside the runner.

Roll out in this order:

1. The operator pushes the reviewed checker and rule changes to the
   `274bot-arch` repository's `main`.
2. The operator pushes the product runner and workflow change.
3. Main merges the product `arch-simplify` branch into `dev`.

Until the product merge, older `dev` branches still contain and own the old
checker tooling; their architecture findings describe that old tree. Do not
apply the new ownership migration to those branches. Final `main` acceptance
must run the simplified checker against the merged product, not against an
older `dev` branch.
