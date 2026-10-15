"""Effective graph and supported-feature policy checks.

All target cfgs are included. This is a cross-platform permission union, not a
host-only Cargo resolution. No candidate build scripts or binaries are run.
"""
import json
from collections import defaultdict
from pathlib import Path


def dependency_records(checker, root):
    _, by_name, by_path, ws_deps = checker.discover_workspace(root)
    manifests = {name: checker.load_toml(path / "Cargo.toml") for name, path in by_name.items()}
    records = []
    for name, manifest in manifests.items():
        tables = [("", key, kind, manifest.get(key, {})) for key, kind in checker.DEP_TABLES]
        for cfg, target in manifest.get("target", {}).items():
            if not isinstance(target, dict):
                raise ValueError("unsupported Cargo target table")
            tables.extend((" ".join(cfg.split()), key, "target" if kind == "normal" else kind, target.get(key, {}))
                          for key, kind in checker.DEP_TABLES)
        for cfg, table_name, table_kind, table in tables:
            for alias, value in table.items():
                spec = checker.spec_map(value)
                dst, is_path = checker.resolve_dep_name(alias, spec, ws_deps, by_name[name], root, by_path)
                merged = dict(checker.workspace_dep_lookup(ws_deps, alias)) if spec.get("workspace") else {}
                inherited_features = merged.get("features", [])
                merged.update(spec)
                features = sorted(set(inherited_features) | set(spec.get("features", [])))
                records.append({
                    "from": name, "to": dst, "alias": alias, "kind": checker.classify_kind(table_kind, spec),
                    "cfg": cfg, "table": table_name, "optional": spec.get("optional") is True,
                    "default_features": merged.get("default-features", True),
                    "features": features, "local": is_path or dst in by_name,
                })
    return manifests, records


def feature_activation(manifests, records, config):
    """Compute optional dependencies and transitive feature requests to a fixpoint."""
    enabled = defaultdict(set)
    active = set(config["packages"])
    requested_deps = set()
    activated = set()
    if config["default_features"]:
        for package in active:
            enabled[package].add("default")
    for request in config["features"]:
        if "/" not in request:
            raise ValueError(f"configuration feature must be package/feature: {request}")
        package, feature = request.split("/", 1)
        if package not in active:
            raise ValueError(f"configuration feature package not selected: {request}")
        enabled[package].add(feature)
    previous = None
    while True:
        state = (frozenset(active), frozenset((p, f) for p, fs in enabled.items() for f in fs),
                 frozenset(requested_deps), frozenset(activated))
        if state == previous:
            break
        previous = state
        for package in sorted(active):
            features = manifests.get(package, {}).get("features", {})
            own = [r for r in records if r["from"] == package]
            dep_names = {r["alias"] for r in own}
            suppressed = {item[4:] for values in features.values() for item in values if item.startswith("dep:")}
            for feature in list(enabled[package]):
                if feature not in features:
                    if feature == "default":
                        continue
                    if feature in dep_names and feature not in suppressed:
                        requested_deps.add((package, feature))
                        continue
                    raise ValueError(f"unknown supported feature: {package}/{feature}")
                for item in features[feature]:
                    if item.startswith("dep:"):
                        if item[4:] not in dep_names:
                            raise ValueError(f"unknown optional dependency: {package}/{item}")
                        requested_deps.add((package, item[4:]))
                    elif "/" in item:
                        dep, child_feature = item.split("/", 1)
                        weak = dep.endswith("?")
                        dep = dep.removesuffix("?")
                        matching = [r for r in own if r["alias"] == dep]
                        if not matching:
                            raise ValueError(f"unknown dependency feature: {package}/{item}")
                        if not weak:
                            requested_deps.add((package, dep))
                        if not weak or (package, dep) in activated:
                            for row in matching:
                                if row["to"] in manifests:
                                    enabled[row["to"]].add(child_feature)
                    else:
                        enabled[package].add(item)
        for row in records:
            if row["from"] not in active or (row["kind"] == "dev" and not config["dev"]):
                continue
            if row["optional"] and (row["from"], row["alias"]) not in requested_deps:
                continue
            activated.add((row["from"], row["alias"]))
            if row["to"] in manifests:
                active.add(row["to"])
                enabled[row["to"]].update(row["features"])
                if row["default_features"]:
                    enabled[row["to"]].add("default")
    result = {("feature", package, feature) for package, fs in enabled.items()
              if package in active for feature in fs}
    result.update(("dependency", r["from"], r["to"], r["kind"], r["cfg"], r["table"])
                  for r in records if (r["from"], r["alias"]) in activated
                  and (r["kind"] != "dev" or config["dev"]))
    return result


PROVENANCE_BASELINE_FILENAME = "graph-provenance.json"
PROVENANCE_SCHEMA_VERSION = 1
PROVENANCE_TABLES = frozenset({"dependencies", "dev-dependencies", "build-dependencies"})


def graph_state(checker, root):
    """Return protected graph policy and its exceptional provenance state."""
    policy = checker.load_policy(checker.RULES_DIR / "policy.toml")
    manifests, records = dependency_records(checker, root)
    migration_pairs = {(row["from"], row["to"]) for row in policy.migrations.values()}
    exceptional = [row for row in records if row["local"] and (
        (row["from"], row["to"]) in migration_pairs
        or row["kind"] in {"optional", "dev", "build"}
    )]
    provenance = {
        (
            "exceptional-edge",
            row["from"],
            row["to"],
            row["kind"],
            row["cfg"],
            row["table"],
            row["default_features"],
            tuple(row["features"]),
        )
        for row in exceptional
    }
    exceptional_pairs = {(row["from"], row["to"]) for row in exceptional}
    for config in policy.configurations:
        for selected in config["packages"]:
            isolated = dict(
                config,
                packages=[selected],
                features=[
                    feature for feature in config["features"]
                    if feature.startswith(selected + "/")
                ],
            )
            for item in feature_activation(manifests, records, isolated):
                if item[0] == "dependency" and (item[1], item[2]) in exceptional_pairs:
                    provenance.add(("isolated-activation", config["id"], selected, *item[1:]))
                elif item[0] == "feature" and item[2] != "default":
                    provenance.add(("feature-activation", config["id"], selected, *item[1:]))

        activation = feature_activation(manifests, records, config)
        for row in exceptional:
            key = ("dependency", row["from"], row["to"], row["kind"], row["cfg"], row["table"])
            if key in activation:
                provenance.add(("activation", config["id"], *key[1:]))
        if config["status"] == "enforced":
            for forbidden in config["forbidden_features"]:
                package, feature = forbidden.split("/", 1)
                if ("feature", package, feature) in activation:
                    raise ValueError(f"forbidden supported feature: {config['id']}: {forbidden}")
            for requirement in config["optional_dependencies"]:
                package, dependency = requirement.split("/", 1)
                matched = [row for row in records
                           if row["from"] == package and row["to"] == dependency]
                if not matched or any(not row["optional"] for row in matched):
                    raise ValueError(f"required optional dependency: {config['id']}: {requirement}")
    return policy, provenance


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if type(value) in (str, bool):
        return value
    raise ValueError("graph provenance contains an unsupported value")


def _provenance_record(checker, raw):
    if type(raw) is not list or not raw or not isinstance(raw[0], str):
        raise ValueError("graph provenance record must be a tagged array")
    tag = raw[0]

    def text(index, *, allow_empty=False):
        if (index >= len(raw) or not isinstance(raw[index], str)
                or (not allow_empty and not raw[index].strip())):
            raise ValueError(f"graph provenance {tag!r} has invalid text field")
        return raw[index]

    def edge_fields(kind_index, cfg_index, table_index):
        if text(kind_index) not in checker.KINDS:
            raise ValueError(f"graph provenance {tag!r} has invalid edge kind")
        text(cfg_index, allow_empty=True)
        if text(table_index) not in PROVENANCE_TABLES:
            raise ValueError(f"graph provenance {tag!r} has invalid dependency table")

    if tag == "exceptional-edge" and len(raw) == 8:
        text(1)
        text(2)
        edge_fields(3, 4, 5)
        if type(raw[6]) is not bool:
            raise ValueError("graph provenance exceptional-edge has invalid default_features")
        features = raw[7]
        if (type(features) is not list
                or any(not isinstance(item, str) or not item.strip() for item in features)
                or len(features) != len(set(features))):
            raise ValueError("graph provenance exceptional-edge has invalid features")
        return (tag, raw[1], raw[2], raw[3], raw[4], raw[5], raw[6], tuple(features))
    if tag == "isolated-activation" and len(raw) == 8:
        text(1)
        text(2)
        text(3)
        text(4)
        edge_fields(5, 6, 7)
        return tuple(raw)
    if tag == "feature-activation" and len(raw) == 5:
        return (tag, *(text(index) for index in range(1, 5)))
    if tag == "activation" and len(raw) == 7:
        text(1)
        text(2)
        text(3)
        edge_fields(4, 5, 6)
        return tuple(raw)
    raise ValueError(f"graph provenance has unknown or malformed record: {tag!r}")


def _no_duplicate_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def provenance_baseline_json(provenance):
    records = [_jsonable(record) for record in provenance]
    records.sort(key=lambda record: json.dumps(
        record, ensure_ascii=False, separators=(",", ":")
    ))
    return json.dumps(
        {"schema_version": PROVENANCE_SCHEMA_VERSION, "records": records},
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def load_provenance_baseline(checker):
    path = checker.RULES_DIR / PROVENANCE_BASELINE_FILENAME
    if path.is_symlink():
        raise ValueError(f"protected graph provenance baseline must not be a symlink: {path}")
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_object,
        )
    except (OSError, UnicodeError, RecursionError, ValueError) as error:
        raise ValueError(f"cannot load protected graph provenance baseline {path}: {error}") from error
    if type(raw) is not dict or set(raw) != {"schema_version", "records"}:
        raise ValueError("graph provenance baseline fields must be exactly schema_version, records")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != PROVENANCE_SCHEMA_VERSION:
        raise ValueError(f"graph provenance baseline schema_version must be {PROVENANCE_SCHEMA_VERSION}")
    if type(raw["records"]) is not list:
        raise ValueError("graph provenance baseline records must be an array")
    records = set()
    for record in raw["records"]:
        normalized = _provenance_record(checker, record)
        if normalized in records:
            raise ValueError(f"duplicate graph provenance record: {normalized!r}")
        records.add(normalized)
    return records


def emit_provenance_baseline(checker, root):
    policy, provenance = graph_state(checker, root)
    errors = checker.check_graph(root, policy)
    if errors:
        raise ValueError("cannot emit baseline for graph with policy errors: " + "; ".join(errors))
    return provenance_baseline_json(provenance)


def check_tree(checker, root: Path):
    try:
        policy, provenance = graph_state(checker, root)
        errors = checker.check_graph(root, policy)
        protected = load_provenance_baseline(checker)
        errors.extend(
            f"exceptional provenance/activation widened: {record}"
            for record in sorted(provenance - protected, key=repr)
        )
        return errors
    except (OSError, ValueError, TypeError, KeyError, SystemExit) as exc:
        return [f"invalid graph input: {exc}"]
