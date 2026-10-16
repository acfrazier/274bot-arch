#!/usr/bin/env python3
"""Pin every Cargo.toml below the protected client submodule."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tomllib

TREE = Path("vendor/fr-client-rust")
PIN = "vendor-manifests.json"


def manifest_digest(manifests):
    """Hash sorted UTF-8 paths and exact bytes, each with an eight-byte length."""
    digest = hashlib.sha256()
    for name, content in sorted(manifests.items()):
        for value in (name.encode("utf-8"), content.encode("utf-8")):
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
    return digest.hexdigest()


def snapshot(root):
    tree = root / TREE
    if tree.is_symlink() or tree.resolve() != tree:
        raise ValueError(f"vendored manifest tree must not traverse a symlink: {TREE}")
    manifests = {}
    if not tree.exists():
        return manifests
    if not tree.is_dir():
        raise ValueError(f"vendored manifest tree is not a directory: {TREE}")

    def walk_error(error):
        raise error

    for directory, children, files in os.walk(tree, onerror=walk_error, followlinks=False):
        for child in children:
            path = Path(directory) / child
            if path.is_symlink():
                raise ValueError(f"vendored manifest directory must not be a symlink: {path.relative_to(root)}")
        if "Cargo.toml" in files:
            path = Path(directory) / "Cargo.toml"
            if path.is_symlink():
                raise ValueError(f"vendored manifest must not be a symlink: {path.relative_to(root)}")
            manifests[path.relative_to(tree).as_posix()] = path.read_bytes().decode("utf-8")
    return manifests


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate vendored manifest pin key: {key}")
        result[key] = value
    return result


def validate_manifests(manifests):
    if not isinstance(manifests, dict):
        raise ValueError("vendored manifest pin must contain a manifest map")
    for name, content in manifests.items():
        path = Path(name)
        if (path.is_absolute() or ".." in path.parts or path.name != "Cargo.toml"
                or path.as_posix() != name or not isinstance(content, str)):
            raise ValueError(f"invalid vendored manifest pin entry: {name}")
        document = tomllib.loads(content)
        groups = [document, *document.get("target", {}).values()]
        for group in groups:
            for table in ("dependencies", "dev-dependencies", "dev_dependencies",
                          "build-dependencies", "build_dependencies"):
                for alias, spec in group.get(table, {}).items():
                    if isinstance(spec, dict) and spec.get("workspace") is True:
                        raise ValueError(
                            f"vendored dependency inheritance is forbidden: {TREE / name}: {alias} workspace = true"
                        )


def pin_json(root):
    manifests = snapshot(root)
    validate_manifests(manifests)
    return json.dumps({"sha256": manifest_digest(manifests), "manifests": manifests},
                      ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check_pin(root, path):
    if path.is_symlink():
        raise ValueError(f"protected 274bot-arch/{PIN} must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    if not isinstance(raw, dict) or set(raw) != {"sha256", "manifests"}:
        raise ValueError("vendored manifest pin fields must be exactly sha256, manifests")
    expected = raw["manifests"]
    validate_manifests(expected)
    if raw["sha256"] != manifest_digest(expected):
        raise ValueError("protected vendored manifest pin digest disagrees with its content")
    actual = snapshot(root)
    if manifest_digest(actual) != raw["sha256"]:
        differences = [
            f"{TREE / name} ({'added' if name not in expected else 'removed' if name not in actual else 'changed'})"
            for name in sorted(expected.keys() | actual.keys())
            if expected.get(name) != actual.get(name)
        ]
        raise ValueError(
            "vendored Cargo.toml pin differs: " + ", ".join(differences)
            + f". An operator commit to 274bot-arch must update {PIN}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="product tree whose vendored manifests to read")
    parser.add_argument("--emit-pin", action="store_true", help="print the digest and expected contents as JSON")
    args = parser.parse_args()
    try:
        if args.emit_pin:
            print(pin_json(args.tree.resolve()), end="")
        else:
            print(manifest_digest(snapshot(args.tree.resolve())))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"cannot read vendored manifests: {error}\n")


if __name__ == "__main__":
    main()
