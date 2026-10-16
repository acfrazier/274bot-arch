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
        self.write_baseline(self.root)
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
        self.assertTrue(any("candidate tools/architecture/policy.toml is forbidden" in error for error in errors), errors)

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
            any("graph provenance/activation widened" in error for error in errors),
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
default_features = true
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
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "default = []", 'default = ["probe"]'
            ),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(
            any("candidate tools/architecture/policy.toml is forbidden" in error for error in errors),
            errors,
        )

    def test_emitted_baseline_accepts_feature_activation(self) -> None:
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
        workspace(self.root, kind="optional", feature=True)
        self.write_baseline(self.root)
        records = json.loads(
            (self.rules / "graph-provenance.json").read_text(encoding="utf-8")
        )["records"]
        self.assertTrue(any(record[0] == "isolated-activation" and record[3] == "dependency"
                            for record in records))
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
        record = ["edge", "vault", "api", "optional", "", "dependencies", True, []]
        (self.rules / "graph-provenance.json").write_text(
            json.dumps({"schema_version": 1, "records": [record, record]}),
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("duplicate graph provenance record" in error for error in errors), errors)

    def test_dependency_table_spellings_good_and_bad(self) -> None:
        for table, kind in checker.DEP_TABLES:
            for prefix in ("", "target.'cfg(any())'."):
                actual_kind = "target" if prefix and kind == "normal" else kind
                with self.subTest(table=prefix + table):
                    root = self.root / (prefix + table)
                    checker.write_workspace(root, ["vault", "api"])
                    checker.write_crate(root, "vault", **{
                        prefix + table: {"api": {"path": "../api"}}
                    })
                    checker.write_crate(root, "api")
                    self.write_policy([])
                    errors = checker.check_graph_tree(root)
                    self.assertTrue(any(
                        f"disallowed crate edge: vault -> api ({actual_kind})" in error
                        for error in errors
                    ), errors)
                    self.write_policy([{
                        "from": "vault", "to": "api", "kinds": [actual_kind], "reason": "fixture"
                    }])
                    self.write_baseline(root)
                    self.assertEqual(checker.check_graph_tree(root), [])

    def vendor_fixture(self, *, allowed: bool, dependency: str = "") -> None:
        checker.write_workspace(self.root, ["vault", "api"])
        checker.write_crate(self.root, "vault")
        checker.write_crate(self.root, "api")
        manifest = self.root / "vendor/backend/Cargo.toml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            '[package]\nname = "backend"\nversion = "0.1.0"\n' + dependency,
            encoding="utf-8",
        )
        allows = [{"from": "vault", "to": "backend", "kinds": ["normal"], "reason": "fixture"}]
        if allowed:
            allows.append({"from": "backend", "to": "api", "kinds": ["normal"], "reason": "fixture"})
        self.write_policy(allows)
        policy = self.rules / "policy.toml"
        # Write the protected binding before loading endpoint permissions.
        policy.write_text(policy.read_text(encoding="utf-8").replace(
            "[workspace]", '[workspace]\npath_packages = { backend = "vendor/backend/Cargo.toml" }'
        ), encoding="utf-8")

    def test_vendor_patch_manifest_good_and_bad(self) -> None:
        self.vendor_fixture(
            allowed=False, dependency='\n[dependencies.api]\npath = "../../crates/api"\n'
        )
        root_manifest = self.root / "Cargo.toml"
        with root_manifest.open("a", encoding="utf-8") as stream:
            stream.write('\n[patch.crates-io]\nbackend = { path = "vendor/backend" }\n')
        vault = self.root / "crates/vault/Cargo.toml"
        with vault.open("a", encoding="utf-8") as stream:
            stream.write('\n[dependencies]\nbackend = "0.1"\n')
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge: backend -> api (normal)" in error
                            for error in errors), errors)
        policy = self.rules / "policy.toml"
        with policy.open("a", encoding="utf-8") as stream:
            stream.write('\n[[allow]]\nfrom = "backend"\nto = "api"\nkinds = ["normal"]\nreason = "fixture"\n')
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_replace_and_unused_workspace_path_require_listed_identity(self) -> None:
        self.vendor_fixture(allowed=False)
        root_manifest = self.root / "Cargo.toml"
        with root_manifest.open("a", encoding="utf-8") as stream:
            stream.write('\n[replace]\n"backend:0.1.0" = { path = "vendor/backend" }\n')
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])
        for heading, key in (("replace", '"other:0.1.0"'), ("workspace.dependencies", "other"),
                             ("patch.crates-io", "other")):
            with self.subTest(heading=heading):
                root_manifest.write_text(
                    '[workspace]\nmembers = ["crates/vault", "crates/api"]\n'
                    f'\n[{heading}]\n{key} = {{ path = "vendor/unlisted" }}\n',
                    encoding="utf-8",
                )
                errors = checker.check_graph_tree(self.root)
                self.assertTrue(any("unlisted path package" in error for error in errors), errors)

    def test_nonmember_dependency_closure_good_and_bad(self) -> None:
        self.vendor_fixture(allowed=False, dependency='\n[dependencies]\nother = { path = "../other" }\n')
        other = self.root / "vendor/other/Cargo.toml"
        other.parent.mkdir()
        other.write_text('[package]\nname = "other"\nversion = "0.1.0"\n', encoding="utf-8")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("unlisted path package" in error for error in errors), errors)
        policy = self.rules / "policy.toml"
        policy.write_text(policy.read_text(encoding="utf-8").replace(
            'path_packages = { backend = "vendor/backend/Cargo.toml" }',
            'path_packages = { backend = "vendor/backend/Cargo.toml", other = "vendor/other/Cargo.toml" }'
        ), encoding="utf-8")
        with policy.open("a", encoding="utf-8") as stream:
            stream.write('\n[[allow]]\nfrom = "backend"\nto = "other"\nkinds = ["normal"]\nreason = "fixture"\n')
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_member_path_spoofs_good_and_bad(self) -> None:
        for alias in ("api", "notapi"):
            for listed in (False, True):
                with self.subTest(alias=alias, listed=listed):
                    root = self.root / f"{alias}-{listed}"
                    checker.write_workspace(root, ["vault", "api"])
                    checker.write_crate(root, "vault", {
                        alias: {"package": "api", "path": "../fake-api"}
                    })
                    checker.write_crate(root, "api")
                    checker.write_crate(root, "fake-api")
                    fake = root / "crates/fake-api/Cargo.toml"
                    fake.write_text(
                        '[package]\nname = "api"\nversion = "0.1.0"\n'
                        '\n[dependencies]\nvault = { path = "../vault" }\n',
                        encoding="utf-8",
                    )
                    self.write_policy([{
                        "from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"
                    }])
                    if listed:
                        policy = self.rules / "policy.toml"
                        policy.write_text(policy.read_text(encoding="utf-8").replace(
                            "[workspace]", '[workspace]\npath_packages = { fake = "crates/fake-api/Cargo.toml" }'
                        ), encoding="utf-8")
                    errors = checker.check_graph_tree(root)
                    needle = "path package identity disagrees" if listed else "unlisted path package"
                    self.assertTrue(any(needle in error for error in errors), errors)
                    # The same key/rename is legitimate only at the real member manifest.
                    self.write_policy([{
                        "from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"
                    }])
                    vault = root / "crates/vault/Cargo.toml"
                    vault.write_text(vault.read_text(encoding="utf-8").replace("../fake-api", "../api"),
                                     encoding="utf-8")
                    self.write_baseline(root)
                    self.assertEqual(checker.check_graph_tree(root), [])

    def test_local_feature_needs_no_operator_change(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}],
            """
[[configuration]]
id = "fixture"
packages = ["vault", "api"]
features = []
default_features = true
dev = true
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = []
""",
        )
        workspace(self.root)
        self.write_baseline(self.root)
        manifest = self.root / "crates/api/Cargo.toml"
        with manifest.open("a", encoding="utf-8") as stream:
            stream.write('\n[features]\ndefault = ["probe-noop"]\nprobe-noop = []\n')
        self.assertEqual(checker.check_graph_tree(self.root), [])
        # A feature request across the same existing crate edge is protected.
        vault = self.root / "crates/vault/Cargo.toml"
        with vault.open("a", encoding="utf-8") as stream:
            stream.write('\n[features]\ndefault = ["api/probe-noop"]\n')
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("graph provenance/activation widened" in error for error in errors), errors)

    def test_candidate_baseline_is_refused_even_without_graph_changes(self) -> None:
        self.write_policy([])
        workspace(self.root, kind="none")
        candidate = self.root / "tools/architecture/graph-provenance.json"
        candidate.parent.mkdir(parents=True)
        candidate.write_text('{"schema_version": 1, "records": []}', encoding="utf-8")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("candidate tools/architecture/graph-provenance.json is forbidden" in error
                            for error in errors), errors)

    def test_candidate_runner_is_not_executed(self) -> None:
        self.write_policy([])
        workspace(self.root)
        runner = self.root / "tools/architecture/run.sh"
        runner.parent.mkdir(parents=True)
        runner.write_text('#!/bin/sh\nexit 0\n', encoding="utf-8")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge: vault -> api (normal)" in error
                            for error in errors), errors)
        # A benign candidate can carry the same local convenience script.
        self.write_policy([{
            "from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"
        }])
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_member_rename_cannot_target_listed_nonmember(self) -> None:
        self.vendor_fixture(allowed=False)
        vault = self.root / "crates/vault/Cargo.toml"
        with vault.open("a", encoding="utf-8") as stream:
            stream.write('\n[dependencies]\nnotapi = { package = "api", path = "../../vendor/backend" }\n')
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("requests package 'api'" in error for error in errors), errors)

    def test_listed_package_inherits_its_own_workspace_paths(self) -> None:
        self.vendor_fixture(allowed=False, dependency='\n[dependencies]\napi = { workspace = true }\n')
        vendor_workspace = self.root / "vendor/Cargo.toml"
        vendor_workspace.write_text(
            '[workspace]\nmembers = ["backend"]\n[workspace.dependencies]\n'
            'api = { path = "../crates/api" }\n', encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("disallowed crate edge: backend -> api (normal)" in error
                            for error in errors), errors)
        policy = self.rules / "policy.toml"
        with policy.open("a", encoding="utf-8") as stream:
            stream.write('\n[[allow]]\nfrom = "backend"\nto = "api"\nkinds = ["normal"]\nreason = "fixture"\n')
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_root_is_required(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            checker.main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
