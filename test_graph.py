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
        self.write_pin()

    def write_policy(self, allows, configuration: str = "", root_patches=None) -> None:
        path = self.rules / "policy.toml"
        checker.write_policy(path, ["vault", "api"], allows, root_patches=root_patches)
        if configuration:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(configuration)

    def write_pin(self) -> None:
        helper = checker.trusted_helper("vendor_manifests")
        (self.rules / helper.PIN).write_text(helper.pin_json(self.root), encoding="utf-8")

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

    def test_baked_reach_producer_edges_have_exact_kinds(self) -> None:
        protected = checker.load_policy(Path(__file__).with_name("policy.toml"))
        members = [
            "api", "client", "e2e", "frontend-core", "host", "host-play",
            "nav-bake", "nav-executor", "nav-planner", "panel", "script",
            "script-js", "tui",
        ]
        allows = [
            {"from": src, "to": dst, "kinds": sorted(row.kinds), "reason": "protected policy"}
            for (src, dst), row in protected.allowed.items()
            if src in members and dst in members
        ]
        admitted = [
            ("nav-bake", "api", "normal"),
            ("nav-bake", "client", "normal"),
            ("nav-bake", "nav-planner", "normal"),
            ("host-play", "nav-bake", "build"),
            ("host-play", "nav-bake", "dev"),
            ("host-play", "nav-planner", "build"),
            ("panel", "nav-bake", "dev"),
            ("frontend-core", "nav-bake", "dev"),
            ("tui", "nav-bake", "dev"),
            ("e2e", "nav-bake", "normal"),
        ]
        refused = [
            (source, "nav-bake", "normal")
            for source in (
                "frontend-core", "host", "host-play", "panel", "nav-planner",
                "nav-executor", "script", "script-js", "tui",
            )
        ] + [
            (source, "nav-bake", "build")
            for source in ("frontend-core", "panel", "tui")
        ]
        for index, (source, target, kind) in enumerate(admitted + refused):
            with self.subTest(source=source, target=target, kind=kind):
                root = self.root / str(index)
                checker.write_workspace(root, members)
                table = {
                    "normal": "dependencies", "dev": "dev_dependencies",
                    "build": "build_dependencies",
                }[kind]
                for member in members:
                    tables = {table: {target: {"path": f"../{target}"}}} if member == source else {}
                    checker.write_crate(root, member, **tables)
                checker.write_policy(self.rules / "policy.toml", members, allows)
                self.write_baseline(root)
                errors = checker.check_graph_tree(root)
                if (source, target, kind) in admitted:
                    self.assertEqual(errors, [])
                else:
                    self.assertTrue(
                        any("disallowed crate edge" in error for error in errors), errors
                    )

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



    def required_optional_fixture(self, *, dev: bool, optional: bool) -> None:
        """Allow normal and dev vault -> api rows in one configuration."""
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["optional", "normal", "dev"], "reason": "fixture"}],
            f"""
[[configuration]]
id = "fixture"
packages = ["vault"]
features = []
default_features = true
dev = {str(dev).lower()}
status = "enforced"
owner = "T1"
forbidden_features = []
optional_dependencies = ["vault/api"]
""",
        )
        checker.write_workspace(self.root, ["vault", "api"])
        normal = {"path": "../api"}
        if optional:
            normal["optional"] = True
        checker.write_crate(
            self.root,
            "vault",
            deps={"api": normal},
            dev_dependencies={"api": {"path": "../api"}},
        )
        checker.write_crate(self.root, "api")

    def test_dev_row_does_not_defeat_required_optional_dependency_without_dev(self) -> None:
        self.required_optional_fixture(dev=False, optional=True)
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_dev_row_defeats_required_optional_dependency_with_dev(self) -> None:
        self.required_optional_fixture(dev=True, optional=True)
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("required optional dependency: fixture: vault/api" in error for error in errors), errors)

    def test_non_optional_normal_row_defeats_required_optional_dependency_beside_a_dev_row(self) -> None:
        self.required_optional_fixture(dev=False, optional=False)
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
        self.write_policy(allows, root_patches={"backend": "vendor/backend"})
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
        # A patch or replace entry must also be listed in [root_patches].
        # That refusal fires before the path identity check. A workspace
        # dependency still fails on the unlisted path identity.
        for heading, key, needle in (
            ("replace", '"other:0.1.0"', "is not in the protected root patch list"),
            ("workspace.dependencies", "other", "unlisted path package"),
            ("patch.crates-io", "other", "is not in the protected root patch list"),
        ):
            with self.subTest(heading=heading):
                root_manifest.write_text(
                    '[workspace]\nmembers = ["crates/vault", "crates/api"]\n'
                    f'\n[{heading}]\n{key} = {{ path = "vendor/unlisted" }}\n',
                    encoding="utf-8",
                )
                errors = checker.check_graph_tree(self.root)
                self.assertTrue(any(needle in error for error in errors), errors)

    def test_git_dependency_is_refused_and_names_file_and_key(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        member_tables = (
            ("plain", "crates/vault/Cargo.toml",
             '\n[dependencies.ext]\ngit = "https://example.invalid/ext.git"\n'),
            ("target", "crates/vault/Cargo.toml",
             "\n[target.'cfg(unix)'.dependencies]\n"
             'ext = { git = "https://example.invalid/ext.git" }\n'),
            ("dev", "crates/vault/Cargo.toml",
             '\n[dev-dependencies]\next = { git = "https://example.invalid/ext.git" }\n'),
        )
        for label, where, text in member_tables:
            with self.subTest(table=label):
                root = workspace(self.root / f"git-member-{label}")
                with (root / where).open("a", encoding="utf-8") as stream:
                    stream.write(text)
                errors = checker.check_graph_tree(root)
                self.assertTrue(any(
                    f"git source refused: {where}: entry 'ext' uses the `git` key" in error
                    for error in errors
                ), errors)
        # An unused workspace dependency is refused too.
        root = workspace(self.root / "git-workspace-dep")
        with (root / "Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write(
                '\n[workspace.dependencies]\next = { git = "https://example.invalid/ext.git" }\n'
            )
        errors = checker.check_graph_tree(root)
        self.assertTrue(any(
            "git source refused: Cargo.toml: entry 'ext' uses the `git` key" in error
            for error in errors
        ), errors)

    def test_git_patch_and_replace_are_refused(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        for label, text in (
            ("patch", '\n[patch.crates-io]\napi = { git = "https://example.invalid/api.git" }\n'),
            ("replace", '\n[replace]\n"api:0.0.0" = { git = "https://example.invalid/api.git" }\n'),
        ):
            with self.subTest(table=label):
                root = workspace(self.root / f"git-{label}")
                with (root / "Cargo.toml").open("a", encoding="utf-8") as stream:
                    stream.write(text)
                errors = checker.check_graph_tree(root)
                self.assertTrue(any(
                    "git source refused: Cargo.toml:" in error and "`git` key" in error
                    for error in errors
                ), errors)

    def test_unlisted_root_path_patch_is_refused_and_listed_one_passes(self) -> None:
        # This is the reduced shape of the round-5 y1/y2/y3 trees. A root
        # path patch for a local package lets any external crate name it.
        allows = [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        self.write_policy(allows)
        workspace(self.root)
        with (self.root / "Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[patch.crates-io]\napi = { path = "crates/api" }\n')
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any(
            "root [patch.crates-io] entry 'api' in Cargo.toml is not in the protected "
            "root patch list" in error for error in errors
        ), errors)
        self.write_policy(allows, root_patches={"api": "crates/api"})
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_registry_root_replace_is_refused(self) -> None:
        self.write_policy(
            [{"from": "vault", "to": "api", "kinds": ["normal"], "reason": "fixture"}]
        )
        workspace(self.root)
        with (self.root / "Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[replace]\n"api:0.0.0" = { version = "0.1" }\n')
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any(
            "root [replace] entry 'api:0.0.0' in Cargo.toml is not in the protected "
            "root patch list" in error for error in errors
        ), errors)

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

    def test_cargo_config_patch_pbkdf2_copy_to_api_is_refused(self) -> None:
        self.write_policy([])
        workspace(self.root, kind="none")
        vault = self.root / "crates/vault/Cargo.toml"
        with vault.open("a", encoding="utf-8") as stream:
            stream.write('\n[dependencies]\npbkdf2 = "0.12.2"\n')
        shadow = self.root / "vendor/dear-imgui-wgpu-0.15.1/shadow-pbkdf2"
        shadow.mkdir(parents=True)
        (shadow / "Cargo.toml").write_text(
            '[package]\nname = "pbkdf2"\nversion = "0.12.2"\n'
            '[dependencies.api]\npath = "../../../crates/api"\n',
            encoding="utf-8",
        )
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])
        config = self.root / ".cargo/config.toml"
        config.parent.mkdir()
        config.write_text(
            '[patch.crates-io]\npbkdf2 = { path = '
            '"vendor/dear-imgui-wgpu-0.15.1/shadow-pbkdf2" }\n',
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("candidate .cargo/config.toml is forbidden" in error
                            and "274bot-arch" in error for error in errors), errors)

    def test_cargo_config_patch_imgui_copy_to_seat_model_is_refused(self) -> None:
        checker.write_workspace(self.root, ["vault", "api", "seat-model"])
        for name in ("vault", "api", "seat-model"):
            checker.write_crate(self.root, name)
        policy = self.rules / "policy.toml"
        checker.write_policy(policy, ["vault", "api", "seat-model"], [{
            "from": "vault", "to": "dear-imgui-wgpu", "kinds": ["normal"], "reason": "fixture"
        }], root_patches={"dear-imgui-wgpu": "vendor/dear-imgui-wgpu-0.15.1"})
        policy.write_text(policy.read_text(encoding="utf-8").replace(
            "[workspace]", '[workspace]\npath_packages = { '
            'dear-imgui-wgpu = "vendor/dear-imgui-wgpu-0.15.1/Cargo.toml" }'
        ), encoding="utf-8")
        original = self.root / "vendor/dear-imgui-wgpu-0.15.1"
        original.mkdir(parents=True)
        (original / "Cargo.toml").write_text(
            '[package]\nname = "dear-imgui-wgpu"\nversion = "0.15.1"\n',
            encoding="utf-8",
        )
        with (self.root / "Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[patch.crates-io]\ndear-imgui-wgpu = { path = '
                         '"vendor/dear-imgui-wgpu-0.15.1" }\n')
        with (self.root / "crates/vault/Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[dependencies]\ndear-imgui-wgpu = "0.15"\n')
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])
        shadow = original / "shadow-imgui"
        shadow.mkdir()
        (shadow / "Cargo.toml").write_text(
            (original / "Cargo.toml").read_text(encoding="utf-8")
            + '[dependencies.seat-model]\npath = "../../../crates/seat-model"\n',
            encoding="utf-8",
        )
        config = self.root / ".cargo/config.toml"
        config.parent.mkdir()
        config.write_text(
            '[patch.crates-io]\ndear-imgui-wgpu = { path = '
            '"vendor/dear-imgui-wgpu-0.15.1/shadow-imgui" }\n',
            encoding="utf-8",
        )
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("candidate .cargo/config.toml is forbidden" in error
                            for error in errors), errors)

    def test_cargo_configs_are_refused_in_nested_and_symlink_locations(self) -> None:
        self.write_policy([])
        workspace(self.root, kind="none")
        for directory in ("", "vendor/fr-client-rust", "vendor/fr-client-rust/crates/client-play"):
            for cargo, filename in (
                (".cargo", "config"), (".cargo", "config.toml"),
                (".cargo", "Config.toml"), (".Cargo", "config.toml"),
                (".CARGO", "CONFIG"), (".CaRgO", "cOnFiG.ToMl"),
                (".Cargo/nested", "CONFIG.TOML"),
            ):
                for symlink in (False, True):
                    with self.subTest(directory=directory, cargo=cargo, filename=filename, symlink=symlink):
                        config = self.root / directory / cargo / filename
                        config.parent.mkdir(parents=True, exist_ok=True)
                        if symlink:
                            config.symlink_to(self.root / "missing-config")
                        else:
                            config.write_text("[paths]\n", encoding="utf-8")
                        errors = checker.check_graph_tree(self.root)
                        self.assertTrue(any(
                            f"candidate {config.relative_to(self.root)} is forbidden" in error
                            for error in errors
                        ), errors)
                        config.unlink()

    def test_case_variant_cargo_directory_symlink_is_refused(self) -> None:
        self.write_policy([])
        workspace(self.root, kind="none")
        data = self.root / "config-data"
        data.mkdir()
        (data / "Config.toml").write_text("[build]\n", encoding="utf-8")
        (self.root / ".Cargo").symlink_to(data, target_is_directory=True)
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("candidate .Cargo/Config.toml is forbidden" in error
                            for error in errors), errors)

    def test_case_variant_cargo_toml_is_refused_in_product_and_vendored_trees(self) -> None:
        self.write_policy([])
        workspace(self.root, kind="none")
        self.write_baseline(self.root)
        # Exact Cargo.toml names alone pass.
        self.assertEqual(checker.check_graph_tree(self.root), [])
        scenarios = (
            # o22 analog: a product manifest variant with a hidden edge
            # and a git source.
            (
                "crates/vault/cargo.toml",
                '[package]\nname = "vault"\nversion = "0.0.0"\n'
                '[dependencies]\napi = { path = "../api" }\n'
                'ext = { git = "https://example.invalid/ext.git" }\n',
            ),
            # o24 analog: a product manifest variant with a hidden
            # feature request.
            (
                "crates/api/cargo.toml",
                '[package]\nname = "api"\nversion = "0.0.0"\n'
                '[dependencies]\nvault = { path = "../vault", '
                'features = ["probe"] }\n',
            ),
            # o23 analog: a vendored manifest variant with a hidden
            # edge into the product tree.
            (
                "vendor/fr-client-rust/crates/client/cargo.toml",
                '[package]\nname = "client"\nversion = "0.0.0"\n'
                '[dependencies]\nvault = { path = "../../../../crates/vault" }\n',
            ),
            ("crates/vault/CARGO.TOML", "[package]\n"),
            ("crates/vault/CaRgO.ToMl", "[package]\n"),
            ("cargo.toml", "[workspace]\n"),
        )
        for relative, content in scenarios:
            for symlink in (False, True):
                with self.subTest(relative=relative, symlink=symlink):
                    candidate = self.root / relative
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    if symlink:
                        candidate.symlink_to(self.root / "missing-manifest")
                    else:
                        candidate.write_text(content, encoding="utf-8")
                    errors = checker.check_graph_tree(self.root)
                    self.assertTrue(any(
                        f"candidate {candidate.relative_to(self.root)} is forbidden" in error
                        and "exact spelling Cargo.toml" in error
                        for error in errors
                    ), errors)
                    candidate.unlink()
        # Removal returns the tree to exact Cargo.toml names alone.
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def client_play_fixture(self) -> Path:
        workspace(self.root, kind="none")
        self.write_policy([{
            "from": "client-play", "to": "client", "kinds": ["normal"], "reason": "fixture"
        }])
        policy = self.rules / "policy.toml"
        policy.write_text(policy.read_text(encoding="utf-8").replace(
            "[workspace]", '[workspace]\npath_packages = { '
            'client = "vendor/fr-client-rust/crates/client/Cargo.toml", '
            'client-play = "vendor/fr-client-rust/crates/client-play/Cargo.toml" }'
        ), encoding="utf-8")
        vendor = self.root / "vendor/fr-client-rust"
        client = vendor / "crates/client/Cargo.toml"
        client.parent.mkdir(parents=True)
        client.write_text(
            '[package]\nname = "client"\nversion = "0.1.0"\n'
            '[features]\naudio = []\nwindow = []\nheaded-fixture = []\ntest-support = []\n',
            encoding="utf-8",
        )
        play = vendor / "crates/client-play/Cargo.toml"
        play.parent.mkdir()
        play.write_text(
            '[package]\nname = "client-play"\nversion = "0.1.0"\n'
            '[features]\ndefault = ["window", "audio"]\n'
            'audio = ["client/audio"]\nwindow = ["client/window"]\n'
            '[dependencies]\nclient = { path = "../client" }\n',
            encoding="utf-8",
        )
        (vendor / "Cargo.toml").write_text(
            '[workspace]\nmembers = ["crates/client", "crates/client-play"]\n',
            encoding="utf-8",
        )
        self.write_pin()
        self.write_baseline(self.root)
        return play

    def assert_pin_refusal(self, filename: str) -> None:
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("vendored Cargo.toml pin differs" in error
                            and filename in error and "operator commit" in error
                            for error in errors), errors)

    def test_vendored_workspace_edits_need_pin_update(self) -> None:
        self.client_play_fixture()
        manifest = self.root / "vendor/fr-client-rust/Cargo.toml"
        original = manifest.read_text(encoding="utf-8")
        for addition in (
            'exclude = ["crates/client"]\n',
            'default-members = ["crates/probe"]\n',
            '\n[package]\nname = "probe"\nversion = "0.1.0"\n',
        ):
            with self.subTest(addition=addition):
                manifest.write_text(original + addition, encoding="utf-8")
                self.assert_pin_refusal("vendor/fr-client-rust/Cargo.toml")
        for members in ('["crates/*"]', '["node_modules/*"]', '["../../crates/api"]'):
            with self.subTest(members=members):
                manifest.write_text("[workspace]\nmembers = " + members + "\n", encoding="utf-8")
                self.assert_pin_refusal("vendor/fr-client-rust/Cargo.toml")

    def test_vendored_inheritance_cannot_redirect_to_product(self) -> None:
        self.client_play_fixture()
        client = self.root / "vendor/fr-client-rust/crates/client/Cargo.toml"
        with client.open("a", encoding="utf-8") as stream:
            stream.write('\n[dependencies]\napiish = { workspace = true }\n')
        with (self.root / "Cargo.toml").open("a", encoding="utf-8") as stream:
            stream.write('\n[workspace.dependencies]\n'
                         'apiish = { path = "crates/api", package = "api" }\n')
        self.assert_pin_refusal("crates/client/Cargo.toml")
        # An operator cannot emit a pin that permits ambiguous inheritance.
        with self.assertRaisesRegex(ValueError, "vendored dependency inheritance is forbidden"):
            self.write_pin()

    def test_vendored_added_and_removed_manifests_are_named(self) -> None:
        self.client_play_fixture()
        removed = self.root / "vendor/fr-client-rust/crates/client-play/Cargo.toml"
        removed.unlink()
        added = self.root / "vendor/fr-client-rust/node_modules/probe/Cargo.toml"
        added.parent.mkdir(parents=True)
        added.write_text('[package]\nname = "probe"\nversion = "0.1.0"\n', encoding="utf-8")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("crates/client-play/Cargo.toml (removed)" in error
                            and "node_modules/probe/Cargo.toml (added)" in error
                            for error in errors), errors)

    def test_missing_or_candidate_manifest_pin_fails_closed(self) -> None:
        self.client_play_fixture()
        pin = self.rules / "vendor-manifests.json"
        saved = pin.read_text(encoding="utf-8")
        pin.unlink()
        self.assertTrue(checker.check_graph_tree(self.root))
        pin.write_text(saved, encoding="utf-8")
        candidate = self.root / "tools/architecture/vendor-manifests.json"
        candidate.parent.mkdir(parents=True)
        candidate.write_text(saved, encoding="utf-8")
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("candidate tools/architecture/vendor-manifests.json is forbidden" in error
                            for error in errors), errors)

    def test_unchanged_vendored_workspace_is_clean(self) -> None:
        self.client_play_fixture()
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_unreached_client_play_default_feature_request_needs_operator_change(self) -> None:
        play = self.client_play_fixture()
        play.write_text(play.read_text(encoding="utf-8").replace(
            'default = ["window", "audio"]',
            'default = ["window", "audio", "probe-cross"]\n'
            'probe-cross = ["client/headed-fixture"]'
        ), encoding="utf-8")
        self.assert_pin_refusal("crates/client-play/Cargo.toml")
        self.write_pin()
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("graph provenance/activation widened" in error
                            and "client-play" in error and "feature-edge" in error
                            and "headed-fixture" in error for error in errors), errors)
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_unreached_client_play_optional_dependency_needs_operator_change(self) -> None:
        play = self.client_play_fixture()
        play.write_text(play.read_text(encoding="utf-8").replace(
            'default = ["window", "audio"]',
            'default = ["window", "audio", "dep:serde"]'
        ) + '\n[dependencies.serde]\nversion = "=1.0.219"\noptional = true\n', encoding="utf-8")
        self.assert_pin_refusal("crates/client-play/Cargo.toml")
        self.write_pin()
        errors = checker.check_graph_tree(self.root)
        self.assertTrue(any("graph provenance/activation widened" in error
                            and "client-play" in error and "dependency" in error
                            and "serde" in error for error in errors), errors)
        self.write_baseline(self.root)
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_unchanged_unreached_client_play_is_clean(self) -> None:
        play = self.client_play_fixture()
        self.assertEqual(checker.check_graph_tree(self.root), [])
        # Even a purely local feature changes protected manifest bytes.
        play.write_text(play.read_text(encoding="utf-8").replace(
            'default = ["window", "audio"]',
            'default = ["window", "audio", "probe-noop"]\nprobe-noop = []'
        ), encoding="utf-8")
        self.assert_pin_refusal("crates/client-play/Cargo.toml")
        self.write_pin()
        self.assertEqual(checker.check_graph_tree(self.root), [])

    def test_root_is_required(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            checker.main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
