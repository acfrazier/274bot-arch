"""Crate graph rules are loaded from the checker repository."""

import json
import tempfile
import unittest
from pathlib import Path

import check as checker


def workspace(root: Path, *, kind: str = "normal", feature: bool = False) -> Path:
    checker.write_workspace(root, ["vault", "api"])
    tables = {}
    spec = {"path": "../api"}
    if kind == "optional":
        spec["optional"] = True
    table = {
        "normal": "dependencies",
        "optional": "dependencies",
        "dev": "dev_dependencies",
        "target": "target.'cfg(unix)'.dependencies",
    }.get(kind)
    if table:
        tables[table] = {"api": spec}
    checker.write_crate(root, "vault", **tables)
    checker.write_crate(root, "api")
    if feature:
        with (root / "crates/vault/Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[features]\ndefault = ["probe"]\nprobe = ["dep:api"]\n')
    return root


class GraphPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="architecture-graph-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace"
        self.rules = Path(self.temp.name) / "rules"
        self.rules.mkdir()
        (self.rules / "graph-provenance.json").write_text(
            '{"schema_version": 1, "records": []}\n', encoding="utf-8"
        )
        self.previous_rules = checker.RULES_DIR
        checker.RULES_DIR = self.rules
        self.addCleanup(setattr, checker, "RULES_DIR", self.previous_rules)

    def write_policy(self, allows, configuration: str = "") -> None:
        path = self.rules / "policy.toml"
        checker.write_policy(path, ["vault", "api"], allows)
        if configuration:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(configuration)

    def write_baseline(self, root: Path) -> None:
        baseline = checker.emit_provenance_baseline(root)
        (self.rules / "graph-provenance.json").write_text(baseline, encoding="utf-8")

    def test_allowed_edge(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        workspace(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_disallowed_edge(self) -> None:
        self.write_policy([])
        workspace(self.root)
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge: vault -> api (normal)" in error for error in errors), errors)

    def test_edge_kind_is_exact(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        workspace(self.root, kind="target")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge kind" in error for error in errors), errors)

    def test_candidate_policy_cannot_allow_an_edge(self) -> None:
        self.write_policy([])
        workspace(self.root)
        candidate_policy = self.root / "tools/architecture/policy.toml"
        candidate_policy.parent.mkdir(parents=True)
        checker.write_policy(
            candidate_policy,
            ["vault", "api"],
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "candidate"}],
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge: vault -> api (normal)" in error for error in errors), errors)

    def test_optional_edge_does_not_use_normal_allowance(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        workspace(self.root, kind="optional")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge kind" in error for error in errors), errors)

    def test_forbidden_supported_feature(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["optional"], "reason": "fixture"}],
            """
[[configuration]]
id = "fixture"
packages = ["vault"]
features = []
default_features = true
dev = false
status = "enforced"
owner = "T1"
forbidden_features = ["vault/probe"]
optional_dependencies = []
""",
        )
        workspace(self.root, kind="optional", feature=True)
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("forbidden supported feature: fixture: vault/probe" in error for error in errors), errors)

    def test_required_optional_dependency(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}],
            """
[[configuration]]
id = "fixture"
packages = ["vault"]
features = []
default_features = true
dev = false
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = ["vault/api"]
""",
        )
        workspace(self.root)
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("required optional dependency: fixture: vault/api" in error for error in errors), errors)



    def test_exceptional_provenance_widening_is_rejected(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["optional"], "reason": "fixture"}],
            """
[[configuration]]
id = "fixture"
packages = ["vault"]
features = []
default_features = true
dev = false
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = []
""",
        )
        baseline = workspace(self.root / "baseline", kind="optional", feature=True)
        baseline_manifest = baseline / "crates/vault/Cargo.toml"
        baseline_manifest.write_text(
            baseline_manifest.read_text(encoding="utf-8").replace(
                'default = ["probe"]', "default = []"
            ),
            encoding="utf-8",
        )
        self.write_baseline(baseline)

        candidate = workspace(self.root / "candidate", kind="optional", feature=True)
        candidate_manifest = candidate / "crates/vault/Cargo.toml"
        candidate_manifest.write_text(
            candidate_manifest.read_text(encoding="utf-8").replace(
                'default = ["probe"]', "default = []"
            ),
            encoding="utf-8",
        )
        candidate_manifest.write_text(
            candidate_manifest.read_text(encoding="utf-8").replace(
                "default = []", 'default = ["probe"]'
            ),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(candidate)
        self.assertTrue(
            any("exceptional provenance/activation widened" in error for error in errors),
            errors,
        )

    def test_candidate_policy_cannot_activate_optional_dependency(self) -> None:
        optional_allow = [
            {"from": "vault", "to": "api", "kinds": ["optional"], "reason": "fixture"}
        ]
        protected_configuration = """
[[configuration]]
id = "fixture"
packages = ["vault"]
features = []
default_features = false
dev = false
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = []
"""
        self.write_policy(optional_allow, protected_configuration)
        workspace(self.root, kind="optional", feature=True)
        manifest = self.root / "crates/vault/Cargo.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                'default = ["probe"]', "default = []"
            ),
            encoding="utf-8",
        )
        self.write_baseline(self.root)

        candidate_policy = self.root / "tools/architecture/policy.toml"
        candidate_policy.parent.mkdir(parents=True)
        checker.write_policy(candidate_policy, ["vault", "api"], optional_allow)
        with candidate_policy.open("a", encoding="utf-8") as stream:
            stream.write("""
[[configuration]]
id = "candidate-activation"
packages = ["vault"]
features = ["vault/probe"]
default_features = false
dev = false
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = []
""")
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_missing_provenance_baseline_fails_closed(self) -> None:
        self.write_policy([])
        workspace(self.root)
        (self.rules / "graph-provenance.json").unlink()
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(
            any("cannot load protected graph provenance baseline" in error for error in errors),
            errors,
        )

    def test_provenance_baseline_schema_is_strict(self) -> None:
        self.write_policy([])
        workspace(self.root)
        baseline = self.rules / "graph-provenance.json"
        baseline.write_text(
            json.dumps({"schema_version": 1, "records": [], "extra": True}),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("fields must be exactly" in error for error in errors), errors)
        baseline.write_text(
            json.dumps({"schema_version": 1, "records": [["unknown"]]}),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("unknown or malformed record" in error for error in errors), errors)

    def test_duplicate_provenance_records_are_rejected(self) -> None:
        self.write_policy([])
        workspace(self.root)
        record = ["exceptional-edge", "vault", "api", "optional", "", "dependencies", True, []]
        (self.rules / "graph-provenance.json").write_text(
            json.dumps({"schema_version": 1, "records": [record, record]}),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("duplicate graph provenance record" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
