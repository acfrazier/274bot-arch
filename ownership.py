#!/usr/bin/env python3
"""Exact source-path ownership-map enforcement.

The product-owned ownership.json is loaded from the checked tree and validated
against source paths present in that same tree.

Every ``tools/seat-model/**`` source path is owned by T1 as physical custodian.
T2 owner-integrates row-8a changes with T1 acknowledgment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCHEMA_VERSION = 1
VALID_OWNERS = frozenset({"T1", "T2", "T3", "T4", "T5"})
TOP_FIELDS = frozenset({"version", "contract", "paths"})
ROW_FIELDS = frozenset({"path", "owner"})

SOURCE_SUFFIXES = frozenset({".rs", ".js", ".cjs", ".ts", ".fbs", ".py", ".sh", ".rs2"})

OWNERSHIP_RELATIVE = Path("tools/architecture/ownership.json")


def ownership_path(root: Path) -> Path:
    return Path(root) / OWNERSHIP_RELATIVE


def _traverses_symlink(root: Path, relative: Path) -> bool:
    component = Path(root)
    for part in relative.parts:
        component = component / part
        if component.is_symlink():
            return True
    return False


def is_source_file(path: Path) -> bool:
    return path.suffix in SOURCE_SUFFIXES



def is_excluded_rel(rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return True
    for part in parts:
        if part in (".git", "target", "node_modules"):
            return True
    if len(parts) >= 2 and parts[0] == "vendor" and parts[1] == "dear-imgui-wgpu-0.15.1":
        return True
    return False


def _census_sources(root: Path) -> tuple[list[str], list[str]]:
    """Inventory source files; symlink dirs/files that could hide sources fail closed.

    Non-source symlinks (e.g. the root ``AGENTS.md`` pointer) are ignored.
    """
    found: list[str] = []
    scan_errors: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dp = Path(dirpath)
        for d in list(dirnames):
            if d in (".git", "target", "node_modules"):
                dirnames.remove(d)
                continue
            full = dp / d
            if full.is_symlink():
                try:
                    rel = full.relative_to(root).as_posix() + "/"
                except ValueError:
                    rel = d + "/"
                scan_errors.append(f"source symlink not allowed: {rel}")
                dirnames.remove(d)
        try:
            rel_dir = dp.relative_to(root)
        except ValueError:
            dirnames[:] = []
            continue
        if rel_dir.parts[:2] == ("vendor", "dear-imgui-wgpu-0.15.1"):
            dirnames[:] = []
            continue
        if "compat-js" in rel_dir.parts and "node_modules" in rel_dir.parts:
            dirnames[:] = []
            continue
        for fn in filenames:
            fp = dp / fn
            if fp.suffix not in SOURCE_SUFFIXES:
                continue
            try:
                rel = fp.relative_to(root)
            except ValueError:
                continue
            if is_excluded_rel(rel):
                continue
            if fp.is_symlink():
                scan_errors.append(f"source symlink not allowed: {rel.as_posix()}")
                continue
            found.append(rel.as_posix())
    found.sort()
    scan_errors.sort()
    return found, scan_errors


def census_sources(root: Path) -> list[str]:
    found, _ = _census_sources(Path(root))
    return found

def _no_dup_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def validate_path_string(p: object) -> str | None:
    if not isinstance(p, str) or not p:
        return "invalid path: must be a nonempty relative posix path"
    if p.startswith("/") or "\\" in p or "\x00" in p:
        return f"invalid path {p!r}: absolute paths and backslashes are forbidden"
    for ch in ("*", "?", "[", "]", "{", "}", "!", "`", "$"):
        if ch in p:
            return f"invalid path {p!r}: wildcards and expansions are forbidden"
    if "//" in p or p.endswith("/") or p.startswith("./") or "/./" in p:
        return f"invalid path {p!r}: path is not normalized"
    parts = p.split("/")
    for part in parts:
        if not part or part in (".", ".."):
            return f"invalid path {p!r}: escapes and empty segments are forbidden"
    return None


def validate_map(data: object) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {}, ["ownership: top level must be an object"]
    for key in data:
        if key not in TOP_FIELDS:
            errors.append(f"ownership: unknown field {key!r}")
    version = data.get("version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(f"ownership: version must be {SCHEMA_VERSION}, got {version!r}")
    contract = data.get("contract")
    if not isinstance(contract, str) or not contract.strip():
        errors.append("ownership: contract must be a nonempty string")
    raw_paths = data.get("paths")
    if not isinstance(raw_paths, list):
        errors.append("ownership: paths must be a list")
        return {}, errors
    mapping: dict[str, str] = {}
    seen: set[str] = set()
    for i, row in enumerate(raw_paths):
        where = f"ownership: paths[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{where}: must be an object")
            continue
        for key in row:
            if key not in ROW_FIELDS:
                errors.append(f"{where}: unknown field {key!r}")
        if set(row.keys()) != ROW_FIELDS:
            errors.append(f"{where}: must contain exactly path and owner")
            continue
        path = row["path"]
        owner = row["owner"]
        path_error = validate_path_string(path)
        if path_error is not None:
            errors.append(f"{where}: {path_error}")
            continue
        if owner not in VALID_OWNERS:
            errors.append(f"{where}: unknown owner {owner!r} for path {path!r}")
            continue
        if path in seen:
            errors.append(f"ownership: duplicate path {path!r}")
            continue
        seen.add(path)
        mapping[path] = owner
    return mapping, errors


def load_ownership_file(json_path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        text = json_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, [f"ownership: missing file {json_path}"]
    except OSError as exc:
        return {}, [f"ownership: cannot read {json_path}: {exc}"]
    try:
        data = json.loads(text, object_pairs_hook=_no_dup_object)
    except ValueError as exc:
        return {}, [f"ownership: invalid JSON in {json_path}: {exc}"]
    return validate_map(data)


def check_tree(root: Path) -> list[str]:
    root = Path(root)
    if _traverses_symlink(root, OWNERSHIP_RELATIVE):
        mapping, errors = {}, [
            f"ownership: {OWNERSHIP_RELATIVE.as_posix()} must not traverse a symlink"
        ]
    else:
        mapping, errors = load_ownership_file(ownership_path(root))
    errors = list(errors)
    sources, scan_errors = _census_sources(root)
    errors.extend(scan_errors)
    for path in sources:
        if path not in mapping:
            errors.append(f"missing ownership: {path}")
    for path in sorted(mapping):
        full = root / path
        if not full.is_file():
            errors.append(f"stale ownership: {path} (owner {mapping[path]})")
        elif full.suffix not in SOURCE_SUFFIXES:
            errors.append(f"not a source path: {path} (owner {mapping[path]})")
    errors.sort()
    return errors




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_tree = sub.add_parser("check-tree", help="check coverage/stale rows for one tree")
    p_tree.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    errors = check_tree(args.root)
    for err in errors:
        print(err)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
