"""Behavioral fixtures for syntax-aware seam and navigation inventories."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
INVENTORIES_PATH = HERE / "inventories.py"
INVENTORIES_SPEC = importlib.util.spec_from_file_location("inventories", INVENTORIES_PATH)
if INVENTORIES_SPEC is None or INVENTORIES_SPEC.loader is None:
    raise ImportError(f"cannot load inventory checker from {INVENTORIES_PATH}")
inventories = importlib.util.module_from_spec(INVENTORIES_SPEC)
sys.modules[INVENTORIES_SPEC.name] = inventories
INVENTORIES_SPEC.loader.exec_module(inventories)


VIEWS_PATH = "crates/frontend-core/src/views.rs"

F0_API_FOREIGN_TYPES = (
    "api::identity::RequestId",
    "api::identity::Scope",
    "api::identity::Settlement",
    "api::identity::SlotKey",
    "api::lifecycle::IntentCommand",
    "api::lifecycle::IntentGeneration",
    "api::lifecycle::MemoryMode",
    "api::lifecycle::WorldChoice",
    "api::process_condition::ConditionId",
    "api::process_condition::ProcessCapability",
    "api::process_condition::UnavailableTerminal",
)

F0_API_FOREIGN_ALIASES = {
    "PinRequestId": "RequestId",
    "PinScope": "Scope",
    "PinSettlement": "Settlement<u8, u8>",
    "PinSlotKey": "SlotKey",
    "PinIntentCommand": "IntentCommand",
    "PinIntentGeneration": "IntentGeneration",
    "PinMemoryMode": "MemoryMode",
    "PinWorldChoice": "WorldChoice",
    "PinConditionId": "ConditionId",
    "PinProcessCapability": "ProcessCapability",
    "PinUnavailableTerminal": "UnavailableTerminal",
}

F0_API_IMPORTS = (
    "use api::identity::{RequestId, Scope, Settlement, SlotKey};\n"
    "use api::lifecycle::{IntentCommand, IntentGeneration, MemoryMode, WorldChoice};\n"
    "use api::process_condition::{ConditionId, ProcessCapability, UnavailableTerminal};\n"
)

# Structural copies of the F0 API definitions (crates/api at f0-core).  The
# workspace crate supplies these types; only the std type needs a data row.
F0_API_CRATE = {
    "crates/api/src/lib.rs": (
        "pub mod identity;\n"
        "pub mod lifecycle;\n"
        "pub mod process_condition;\n"
        "pub mod selected;\n"
        "#[cfg(test)]\n"
        "mod tests;\n"
    ),
    # Only the production module tree is parsed; this test-only file is not Rust.
    "crates/api/src/tests.rs": "fn broken() }\n",
    "crates/api/src/selected.rs": "#[derive(Clone, Copy)]\npub struct RunKey(u64);\n",
    "crates/api/src/identity.rs": (
        "use std::num::NonZeroU64;\n"
        "use crate::selected::RunKey;\n"
        "#[derive(Clone, Copy)]\npub struct ProcessIncarnation(NonZeroU64);\n"
        "#[derive(Clone, Copy)]\npub struct SlotKey(NonZeroU64);\n"
        "#[derive(Clone, Copy)]\n"
        "pub struct SessionKey {\n    slot: SlotKey,\n    incarnation: ProcessIncarnation,\n}\n"
        "#[derive(Clone, Copy)]\n"
        "pub struct ExecutionId {\n    run: RunKey,\n    sequence: NonZeroU64,\n}\n"
        "#[derive(Clone, Copy)]\npub struct RequestId(NonZeroU64);\n"
        "#[derive(Clone, Copy)]\n"
        "pub enum Scope {\n    Process,\n    Slot(SlotKey),\n    Session(SessionKey),\n"
        "    Run(RunKey),\n    Execution(ExecutionId),\n}\n"
        "#[derive(Clone, Copy)]\npub enum Cancellation {\n    Operator,\n    Superseded,\n}\n"
        "#[derive(Clone)]\n"
        "pub enum Settlement<T, E> {\n    Completed(T),\n    Failed(E),\n"
        "    Cancelled(Cancellation),\n}\n"
    ),
    "crates/api/src/lifecycle.rs": (
        "#[derive(Clone, Copy)]\npub enum MemoryMode {\n    High,\n    Low,\n}\n"
        "#[derive(Clone, Copy)]\npub enum WorldChoice {\n    Automatic,\n    World(u16),\n}\n"
        "#[derive(Clone, Copy)]\npub struct IntentGeneration(u64);\n"
        "#[derive(Clone, Copy)]\n"
        "pub struct IntentCommand {\n    generation: IntentGeneration,\n"
        "    cancellation: IntentGeneration,\n}\n"
    ),
    "crates/api/src/process_condition.rs": (
        "use crate::identity::{ProcessIncarnation, RequestId, Scope};\n"
        "#[derive(Clone, Copy)]\npub enum ProcessServiceCode {\n    Runtime,\n    Store,\n}\n"
        "#[derive(Clone, Copy)]\n"
        "pub enum ProcessCapability {\n    Render,\n    Script,\n    Store,\n    Login,\n}\n"
        "#[derive(Clone, Copy)]\n"
        "pub struct ConditionId {\n    incarnation: ProcessIncarnation,\n"
        "    service: ProcessServiceCode,\n}\n"
        "#[derive(Clone, Copy)]\n"
        "pub struct UnavailableTerminal {\n    condition: ConditionId,\n    request: RequestId,\n"
        "    scope: Scope,\n}\n"
    ),
}


def _foreign(path: str, classification: str = "scalar") -> dict[str, str]:
    return {"path": path, "classification": classification, "reason": "fixture foreign type"}


def _foreign_data(*rows: dict[str, Any]) -> str:
    return json.dumps({"schema_version": 1, "foreign_types": list(rows)}, indent=2) + "\n"


def _seam(
    symbol: str, classification: str, path: str = VIEWS_PATH
) -> dict[str, str]:
    return {
        "id": f"seam_type|{path}|{symbol}",
        "path": path,
        "symbol": symbol,
        "classification": classification,
        "owner": "T3",
        "reason": "fixture seam classification",
    }


def _record(
    category: str,
    path: str,
    symbol: str,
    cfg_or_target: str,
    classification: str,
    *,
    owner: str = "T5",
) -> dict[str, str]:
    endpoint = "T3.1" if owner == "T3" else "T5.1"
    record_id = "|".join((category, path, cfg_or_target, symbol, classification))
    return {
        "id": record_id,
        "category": category,
        "path": path,
        "symbol": symbol,
        "cfg_or_target": cfg_or_target,
        "owner": owner,
        "reason": "fixture baseline debt",
        "removal_endpoint": endpoint,
        "classification": classification,
    }


def _write_fixture(
    root: Path,
    *,
    views: str,
    frontend_lib: str = "pub mod views;\n",
    frontend_files: dict[str, str] | None = None,
    script_files: dict[str, str] | None = None,
    seam_types: tuple[tuple[str, str], ...] = (),
    additional_seam_types: tuple[dict[str, str], ...] = (),
    violations: tuple[dict[str, str], ...] = (),
    test_exceptions: tuple[dict[str, str], ...] = (),
    foreign_types: str | None = None,
    workspace_files: dict[str, str] | None = None,
    script_manifest: str | None = None,
    script_aux: tuple[Path, ...] = inventories.SCRIPT_AUX_RELATIVE[:1],
) -> Path:
    for crate in ("script", "frontend-core"):
        crate_root = root / "crates" / crate
        crate_root.mkdir(parents=True)
        manifest = (
            script_manifest
            if crate == "script" and script_manifest is not None
            else f'[package]\nname = "{crate}"\nversion = "0.0.0"\nedition = "2021"\n'
        )
        if crate == "script" and script_manifest is None:
            manifest += '\n[dependencies]\nnav = { path = "../nav" }\n'
        (crate_root / "Cargo.toml").write_text(manifest, encoding="utf-8")
    frontend_src = root / "crates" / "frontend-core" / "src"
    frontend_src.mkdir()
    (frontend_src / "lib.rs").write_text(frontend_lib, encoding="utf-8")
    (root / VIEWS_PATH).write_text(views, encoding="utf-8")
    for relative, contents in (frontend_files or {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    script_src = root / "crates" / "script" / "src"
    script_src.mkdir()
    (root / "crates" / "script" / "tests").mkdir()
    fixture_files = dict(script_files or {})
    fixture_files.setdefault("crates/script/src/lib.rs", "")
    for relative, contents in fixture_files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    for relative in script_aux:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// generated fixture input\n", encoding="utf-8")
    rule_dir = root / inventories.DATA_DIR_RELATIVE
    rule_dir.mkdir(parents=True, exist_ok=True)
    inventory = {
        "schema_version": 1,
        "seam_types": [
            _seam(symbol, classification) for symbol, classification in seam_types
        ] + list(additional_seam_types),
        "violations": list(violations),
        "test_exceptions": list(test_exceptions),
    }
    inventory_path = rule_dir / inventories.INVENTORY_RELATIVE
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    if foreign_types is not None:
        foreign_path = rule_dir / inventories.FOREIGN_TYPES_RELATIVE
        foreign_path.write_text(foreign_types, encoding="utf-8")
    if workspace_files is not None:
        # A root manifest makes every crates/<name> directory a workspace member.
        extra = sorted({Path(relative).parts[1] for relative in workspace_files})
        members = ", ".join(
            f'"crates/{crate}"' for crate in ["frontend-core", "script", *extra]
        )
        (root / "Cargo.toml").write_text(
            f'[workspace]\nresolver = "2"\nmembers = [{members}]\n', encoding="utf-8"
        )
        for crate in extra:
            manifest = root / "crates" / crate / "Cargo.toml"
            if f"crates/{crate}/Cargo.toml" not in workspace_files:
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(
                    f'[package]\nname = "{crate}"\nversion = "0.0.0"\nedition = "2021"\n',
                    encoding="utf-8",
                )
        for relative, contents in workspace_files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
    return root


class InventoryBehaviorTests(unittest.TestCase):
    def fixture(self, **kwargs: Any) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="f0-inventory-")
        self.addCleanup(temporary.cleanup)
        return _write_fixture(Path(temporary.name), **kwargs)

    def clean_fixture(self, **kwargs: Any) -> Path:
        kwargs.setdefault("views", self.baseline_views())
        kwargs.setdefault(
            "seam_types", (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        )
        return self.fixture(**kwargs)

    @staticmethod
    def baseline_views() -> str:
        return """\
#[derive(Clone, Copy)]
pub struct FleetCounts {
    pub total: u64,
}

pub struct FleetView<'a> {
    pub label: &'a str,
}
"""

    def test_clean_scalar_and_borrowed_seams_are_accepted(self) -> None:
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        self.assertEqual(inventories.check_tree(root), [])

    def test_candidate_rule_files_are_used(self) -> None:
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        candidate_rules = root / inventories.DATA_DIR_RELATIVE
        (candidate_rules / "inventories.json").write_text("not checker rules", encoding="utf-8")
        (candidate_rules / "foreign_types.json").write_text("not checker rules", encoding="utf-8")
        errors = inventories.check_tree(root)
        self.assertTrue(any("inventory: cannot load tools/architecture/inventories.json" in error for error in errors), errors)
        self.assertTrue(any("foreign types: cannot load tools/architecture/foreign_types.json" in error for error in errors), errors)

    def test_value_reexports_and_module_self_import_are_not_seam_types(self) -> None:
        log_file_path = "crates/frontend-core/src/log_file.rs"
        root = self.fixture(
            views=self.baseline_views(),
            frontend_lib=(
                "pub mod views;\n"
                "pub mod map_bake;\n"
                "mod log_file;\n"
                "pub use map_bake::{MAP_BAKE_TITLE, MAP_BAKE_WARNING, "
                "MAP_BAKE_RENDER, bake};\n"
                "pub use log_file::{self};\n"
            ),
            frontend_files={
                "crates/frontend-core/src/map_bake.rs": (
                    'pub const MAP_BAKE_TITLE: &str = "Map";\n'
                    'pub static MAP_BAKE_WARNING: &str = "warning";\n'
                    "pub fn MAP_BAKE_RENDER() {}\n"
                    "pub fn bake() {}\n"
                ),
                log_file_path: (
                    "use std::time::{self, Duration};\n"
                    "#[derive(Clone, Copy)]\n"
                    "pub struct LogClock { tick: time::Duration }\n"
                    "pub const LOG_FILE_BUFFER_SIZE: usize = 0;\n"
                ),
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            additional_seam_types=(_seam("LogClock", "scalar", log_file_path),),
        )
        errors = inventories.check_tree(root)
        print(f"GOOD value re-exports and module self-import: {errors}")
        self.assertEqual(errors, [])

    def test_registered_foreign_reexports_are_in_the_seam_inventory(self) -> None:
        frontend_paths = {
            "capacity": "crates/frontend-core/src/capacity.rs",
            "log": "crates/frontend-core/src/log.rs",
            "walk_permissions": "crates/frontend-core/src/walk_permissions.rs",
        }
        root = self.fixture(
            views=self.baseline_views(),
            frontend_lib=(
                "pub mod views;\n"
                "pub mod capacity;\n"
                "pub mod log;\n"
                "pub mod walk_permissions;\n"
            ),
            frontend_files={
                frontend_paths["capacity"]: (
                    "pub use host::{CapacityWarning, RenderPolicyLabel};\n"
                ),
                frontend_paths["log"]: (
                    "pub use api::hostlog::{Level, Record, Source};\n"
                ),
                frontend_paths["walk_permissions"]: (
                    "pub use host_play::DangerLevel;\n"
                ),
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            additional_seam_types=(
                _seam("CapacityWarning", "scalar", frontend_paths["capacity"]),
                _seam("RenderPolicyLabel", "scalar", frontend_paths["capacity"]),
                _seam("Level", "scalar", frontend_paths["log"]),
                _seam("Record", "borrowed", frontend_paths["log"]),
                _seam("Source", "scalar", frontend_paths["log"]),
                _seam(
                    "DangerLevel", "scalar", frontend_paths["walk_permissions"]
                ),
            ),
        )
        errors = inventories.check_tree(root)
        print(f"GOOD trusted foreign seam re-exports: {errors}")
        self.assertEqual(errors, [])

    def test_glob_imports_close_local_ownership_through_foreign_types(self) -> None:
        frontend_paths = {
            "operations": "crates/frontend-core/src/operations.rs",
            "session": "crates/frontend-core/src/session.rs",
        }
        root = self.fixture(
            views=self.baseline_views(),
            frontend_lib=(
                "pub mod views;\n"
                "pub mod operations;\n"
                "pub mod session;\n"
            ),
            frontend_files={
                frontend_paths["operations"]: (
                    "#[derive(Clone, Copy)]\n"
                    "pub struct OperationId(u64);\n"
                ),
                frontend_paths["session"]: (
                    "use crate::operations::OperationId;\n"
                    "use std::thread::JoinHandle;\n"
                    "use std::sync::atomic::{AtomicBool, AtomicU64};\n"
                    "mod native_settings {\n"
                    "    use super::*;\n"
                    "    pub(crate) struct NativeCopyCancellation {\n"
                    "        operation: OperationId,\n"
                    "        state: std::sync::Arc<()>,\n"
                    "    }\n"
                    "}\n"
                    "pub struct SessionOwner {\n"
                    "    cancellation: native_settings::NativeCopyCancellation,\n"
                    "    writer: JoinHandle<()>,\n"
                    "    catalog: script::CatalogDiff,\n"
                    "    cancelled: AtomicBool,\n"
                    "    generation: AtomicU64,\n"
                    "    card: script::CompiledId,\n"
                    "}\n"
                ),
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            additional_seam_types=(
                _seam("OperationId", "scalar", frontend_paths["operations"]),
                _seam("SessionOwner", "owning", frontend_paths["session"]),
            ),
        )
        errors = inventories.check_tree(root)
        print(f"GOOD glob-import and foreign ownership closure: {errors}")
        self.assertEqual(errors, [])

    def test_cfg_import_alternatives_collapse_or_fail_closed(self) -> None:
        seam_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("CfgClock", "scalar"),
        )
        same_target = self.fixture(
            views=self.baseline_views()
            + (
                "\n#[cfg(unix)]\nuse std::time::Duration as ClockValue;\n"
                "#[cfg(windows)]\nuse std::time::Duration as ClockValue;\n"
                "#[derive(Clone, Copy)]\npub struct CfgClock { delay: ClockValue }\n"
            ),
            seam_types=seam_types,
        )
        different_targets = self.fixture(
            views=self.baseline_views()
            + (
                "\n#[cfg(unix)]\nuse std::time::Duration as ClockValue;\n"
                "#[cfg(windows)]\nuse std::time::Instant as ClockValue;\n"
                "#[derive(Clone, Copy)]\npub struct CfgClock { delay: ClockValue }\n"
            ),
            seam_types=seam_types,
        )
        good_errors = inventories.check_tree(same_target)
        bad_errors = inventories.check_tree(different_targets)
        print(f"GOOD same-target cfg alternatives: {good_errors}")
        print(f"BAD ambiguous cfg alternatives: {bad_errors}")
        self.assertEqual(good_errors, [])
        self.assertTrue(
            any("ambiguous cfg/alternative seam field type" in error for error in bad_errors)
        )

    def test_unregistered_public_field_and_clone_debt_fails_closed(self) -> None:
        root = self.fixture(
            views=self.baseline_views()
            + "\n#[derive(Clone)]\npub struct FleetRow { pub name: String }\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("FleetRow", "owning"),
            ),
        )
        errors = inventories.check_tree(root)
        self.assertTrue(any("unregistered inventory violation" in error for error in errors))

    def test_external_test_module_and_cfg_all_keep_test_provenance(self) -> None:
        path = "crates/script/src/tests.rs"
        external_import = _record(
            "test_nav_implementation_import",
            path,
            "nav::world::WorldState",
            "cfg(test)::module:tests",
            "use_import",
        )
        cfg_function = "cfg(test)::module:tests::function:feature_probe"
        macro_area = _record(
            "test_nav_implementation_import",
            path,
            "nav::arrival::ArrivalKind::Area",
            cfg_function,
            "macro_token_path",
        )
        macro_reach = _record(
            "test_nav_implementation_import",
            path,
            "nav::arrival::ArrivalKind::Reach",
            cfg_function,
            "macro_token_path",
        )
        root = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": "#[cfg(test)]\nmod tests;\n",
                path: "use nav::world::WorldState;\n"
                "#[cfg(all(test, feature = \"load\"))]\n"
                "fn feature_probe() {\n"
                "    assert_eq!(nav::arrival::ArrivalKind::Area, "
                "nav::arrival::ArrivalKind::Reach);\n"
                "}\n",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            violations=(external_import, macro_area, macro_reach),
        )
        self.assertEqual(inventories.check_tree(root), [])

    def test_macro_definitions_dynamic_includes_and_cfg_attr_provenance(self) -> None:
        macro_root = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": "macro_rules! hidden { () => { nav::world::WorldState }; }\n",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        macro_errors = inventories.check_tree(macro_root)
        self.assertTrue(any("raw navigation path in macro definition" in error for error in macro_errors))

        include_root = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": 'include!(concat!("hidden", ".rs"));\n',
                "crates/script/src/hidden.rs": "pub fn hidden() {}\n",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        include_errors = inventories.check_tree(include_root)
        self.assertTrue(any("include!" in error for error in include_errors))

        cfg_attr_root = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": "#[cfg_attr(feature = \"load\", cfg(test))]\n"
                "mod tests;\n",
                "crates/script/src/tests.rs": "",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        cfg_attr_errors = inventories.check_tree(cfg_attr_root)
        self.assertTrue(
            any("cfg_attr may not alter cfg" in error for error in cfg_attr_errors),
            cfg_attr_errors,
        )
        harmless = self.clean_fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": '#[cfg_attr(feature = "load", allow(dead_code))]\nmod tests;\n',
                "crates/script/src/tests.rs": "",
            },
        )
        self.assertEqual(inventories.check_tree(harmless), [])

    def test_trusted_seam_class_cannot_be_rewritten(self) -> None:
        candidate = self.fixture(
            views="#[derive(Clone, Copy)]\npub struct FleetView { pub value: u32 }\n",
            seam_types=(("FleetView", "scalar"),),
        )
        errors = inventories.check_tree(candidate)
        self.assertTrue(
            any("trusted seam classification is borrowed" in error for error in errors),
            errors,
        )

    def test_raw_navigation_paths_and_aliases_fail_closed(self) -> None:
        path = "crates/script/src/lib.rs"
        seam_types = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        qualified = self.fixture(
            views=self.baseline_views(),
            script_files={path: "pub fn leak() -> nav::world::WorldState { loop {} }\n"},
            seam_types=seam_types,
        )
        alias = self.fixture(
            views=self.baseline_views(),
            script_files={
                path: "pub type RawState = nav::world::WorldState;\n"
                "pub fn leak() -> RawState { loop {} }\n"
            },
            seam_types=seam_types,
        )
        qualified_errors = inventories.check_tree(qualified)
        alias_errors = inventories.check_tree(alias)
        self.assertTrue(any("qualified_path" in error for error in qualified_errors), qualified_errors)
        self.assertTrue(any("public_signature" in error for error in qualified_errors), qualified_errors)
        self.assertTrue(any("public_type_alias" in error for error in alias_errors), alias_errors)
        self.assertTrue(any("public_signature" in error for error in alias_errors), alias_errors)

    def test_baked_atlas_storage_stays_outside_script_facade(self) -> None:
        manifest = (
            '[package]\nname = "script"\nversion = "0.0.0"\n'
            'edition = "2021"\n[dependencies]\n'
            'nav-planner = { path = "../nav-planner" }\n'
        )
        for module in ("reachability", "atlas", "movement"):
            with self.subTest(module=module):
                errors = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=manifest,
                        script_files={
                            "crates/script/src/lib.rs":
                                f"pub fn leak() -> nav_planner::{module}::Raw {{ loop {{}} }}\n"
                        },
                    )
                )
                self.assertTrue(
                    any("production_nav_implementation_import" in error for error in errors),
                    errors,
                )
                self.assertTrue(any("public_signature" in error for error in errors), errors)

    def test_script_js_crate_is_scanned_for_raw_navigation_imports(self) -> None:
        path = "crates/script-js/src/x.rs"
        root = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script-js/src/lib.rs": "mod x;\n",
                path: "use nav::router::Route;\n",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        errors = inventories.check_tree(root)
        self.assertTrue(
            any("production_nav_implementation_import" in error and path in error for error in errors),
            errors,
        )

    def test_script_js_roots_are_optional_when_the_crate_is_absent(self) -> None:
        self.assertIn(Path("crates/script-js/src"), inventories.SCRIPT_SRC_RELATIVE)
        self.assertIn(Path("crates/script-js/tests"), inventories.SCRIPT_TESTS_RELATIVE)
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        self.assertFalse((root / "crates/script-js").exists())
        self.assertEqual(inventories.check_tree(root), [])

    def test_script_aux_path_may_move_to_the_js_crate(self) -> None:
        moved = Path("crates/script-js/schema/generated/isolate_generated.rs")
        self.assertIn(moved, inventories.SCRIPT_AUX_RELATIVE)
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            script_aux=(moved,),
        )
        self.assertFalse((root / inventories.SCRIPT_AUX_RELATIVE[0]).exists())
        self.assertTrue((root / moved).is_file())
        self.assertEqual(inventories.check_tree(root), [])

    def test_planner_roots_follow_manifest_and_keep_contract(self) -> None:
        path = "crates/script/src/lib.rs"
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        cases = (
            ("nav", "nav", "../nav", "nav"),
            ("nav-planner", "nav-planner", "../nav-planner", "nav_planner"),
        )
        for key, package, relative_path, root in cases:
            with self.subTest(crate_root=root):
                manifest = (
                    '[package]\nname = "script"\nversion = "0.0.0"\n'
                    'edition = "2021"\n[dependencies]\n'
                    f'{key} = {{ package = "{package}", path = "{relative_path}" }}\n'
                )
                raw = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=manifest,
                        script_files={
                            path: f"pub fn leak() -> {root}::router::Route {{ loop {{}} }}\n"
                        },
                    )
                )
                self.assertTrue(
                    any(
                        "production_nav_implementation_import" in error
                        and f"{root}::router::Route" in error
                        for error in raw
                    ),
                    raw,
                )
                contract = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=manifest,
                        script_files={path: f"use {root}::contract::RouteView;\n"},
                    )
                )
                self.assertEqual(contract, [])

    def test_planner_cargo_alias_and_module_alias_remain_raw(self) -> None:
        manifest = (
            '[package]\nname = "script"\nversion = "0.0.0"\nedition = "2021"\n'
            '[dependencies]\nnavp = { package = "nav-planner", version = "0.0.0" }\n'
        )
        alias_errors = inventories.check_tree(
            self.clean_fixture(
                script_manifest=manifest,
                script_files={
                    "crates/script/src/lib.rs": "use navp::router::Route;\n"
                },
            )
        )
        self.assertTrue(
            any("production_nav_implementation_import" in error and "navp::router::Route" in error
                for error in alias_errors),
            alias_errors,
        )

        module_alias_errors = inventories.check_tree(
            self.clean_fixture(
                script_manifest=(
                    '[package]\nname = "script"\nversion = "0.0.0"\n'
                    'edition = "2021"\n[dependencies]\n'
                    'nav-planner = { path = "../nav-planner" }\n'
                ),
                script_files={
                    "crates/script/src/lib.rs": (
                        "use nav_planner::router as r;\n"
                        "pub fn leak() -> r::Route { loop {} }\n"
                    )
                },
            )
        )
        self.assertTrue(
            any("production_nav_implementation_import" in error for error in module_alias_errors),
            module_alias_errors,
        )
        self.assertTrue(
            any("public_signature" in error for error in module_alias_errors),
            module_alias_errors,
        )

    def test_both_planner_spellings_in_macro_definitions_are_rejected(self) -> None:
        for key, package, relative_path, root in (
            ("nav", "nav", "../nav", "nav"),
            ("nav-planner", "nav-planner", "../nav-planner", "nav_planner"),
        ):
            with self.subTest(crate_root=root):
                errors = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=(
                            '[package]\nname = "script"\nversion = "0.0.0"\n'
                            'edition = "2021"\n[dependencies]\n'
                            f'{key} = {{ package = "{package}", path = "{relative_path}" }}\n'
                        ),
                        script_files={
                            "crates/script/src/lib.rs": (
                                f"macro_rules! hidden {{ () => {{ {root}::world::WorldState }}; }}\n"
                            )
                        },
                    )
                )
                self.assertTrue(
                    any("raw navigation path in macro definition is unsupported" in error
                        for error in errors),
                    errors,
                )

    def test_crate_root_aliases_and_extern_crate_fail_closed(self) -> None:
        cases = (
            (
                "nav",
                '[dependencies]\nnav = { path = "../nav" }\n',
                "use nav as p;\nfn f() { let _ = p::executor_adapter::plan_owned_leg; }\n",
                "bare nav crate root import is unsupported",
            ),
            (
                "nav_planner",
                '[dependencies]\nnav-planner = { path = "../nav-planner" }\n',
                "use nav_planner::{self as p};\n",
                "bare nav crate root import is unsupported",
            ),
            (
                "nav_planner",
                '[dependencies]\nnav-planner = { path = "../nav-planner" }\n',
                "use nav_planner;\n",
                "bare nav crate root import is unsupported",
            ),
            (
                "nav_planner",
                '[dependencies]\nnav-planner = { path = "../nav-planner" }\n',
                "extern crate nav_planner as p;\n",
                "extern crate nav_planner is unsupported for a nav crate",
            ),
            (
                "nav_executor",
                "",
                "extern crate nav_executor;\n",
                "extern crate nav_executor is unsupported for a nav crate",
            ),
        )
        for root, dependencies, source, expected in cases:
            with self.subTest(root=root, source=source):
                errors = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=(
                            '[package]\nname = "script"\nversion = "0.0.0"\n'
                            'edition = "2021"\n'
                            + dependencies
                        ),
                        script_files={"crates/script/src/lib.rs": source},
                    )
                )
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_executor_imports_are_never_test_exceptions(self) -> None:
        runner = "crates/script/src/gatherer/runner.rs"
        lib = '#[path = "gatherer/runner.rs"]\nmod runner;\nuse nav_executor::Traveller;\n'
        errors = inventories.check_tree(
            self.clean_fixture(
                script_files={
                    "crates/script/src/lib.rs": lib,
                    runner: "#[cfg(test)] mod tests { use nav_executor::TravelOutcome; }\n",
                    "crates/script/tests/path_schema.rs": "use nav_executor::Traveller;\n",
                }
            )
        )
        for path in (runner, "crates/script/tests/path_schema.rs"):
            self.assertTrue(
                any(
                    "test_nav_implementation_import" in error and path in error
                    for error in errors
                ),
                errors,
            )
        self.assertTrue(
            any(
                "production_nav_implementation_import" in error
                and "crates/script/src/lib.rs" in error
                for error in errors
            ),
            errors,
        )
        self.assertFalse(any("unregistered test import exception" in error for error in errors))

        registered = self.fixture(
            views=self.baseline_views(),
            script_files={
                "crates/script/src/lib.rs": '#[path = "gatherer/runner.rs"]\nmod runner;\n',
                runner: "#[cfg(test)] mod tests {}\n",
            },
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            test_exceptions=(
                _record(
                    "test_import_exception",
                    runner,
                    "nav_executor::Traveller",
                    "cfg(test)::tests",
                    "exact_test_fixture_oracle_import",
                ),
            ),
        )
        registered_errors = inventories.check_tree(registered)
        self.assertTrue(
            any("test exception may not name the executor crate" in error
                for error in registered_errors),
            registered_errors,
        )

    def test_executor_adapter_is_raw_and_not_a_planner_trusted_type(self) -> None:
        manifest = (
            '[package]\nname = "script"\nversion = "0.0.0"\nedition = "2021"\n'
            '[dependencies]\nnav-planner = { path = "../nav-planner" }\n'
            'nav_executor = { package = "nav-executor", path = "../nav-executor" }\n'
        )
        direct = inventories.check_tree(
            self.clean_fixture(
                script_manifest=manifest,
                script_files={
                    "crates/script/src/lib.rs": (
                        "use nav_planner::executor_adapter::plan_leg_count;\n"
                    )
                },
            )
        )
        self.assertTrue(
            any("production_nav_implementation_import" in error for error in direct),
            direct,
        )
        reexport = inventories.check_tree(
            self.clean_fixture(
                script_manifest=manifest,
                script_files={
                    "crates/script/src/lib.rs": (
                        "pub use nav_planner::executor_adapter::plan_leg_count;\n"
                    )
                },
            )
        )
        self.assertTrue(
            any("public_reexport" in error for error in reexport),
            reexport,
        )

        views = self.baseline_views() + (
            "#[derive(Clone, Copy)]\n"
            "pub struct ExecutorView { pub state: nav_executor::WorldState }\n"
        )
        executor_view = self.fixture(
            views=views,
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("ExecutorView", "scalar"),
            ),
            workspace_files={
                "crates/nav-executor/src/lib.rs": (
                    "#[derive(Clone, Copy)]\npub struct WorldState(pub u64);\n"
                )
            },
            script_manifest=manifest,
        )
        self.assertEqual(inventories.check_tree(executor_view), [])

    def test_macro_root_aliases_fail_but_resolved_macro_paths_are_recorded(self) -> None:
        manifest = (
            '[package]\nname = "script"\nversion = "0.0.0"\nedition = "2021"\n'
            '[dependencies]\nnav-planner = { path = "../nav-planner" }\n'
        )
        cases = (
            "macro_rules! m { () => { use nav_planner as p; p::router::Route }; }\n",
            "macro_rules! m { () => { use nav_planner::{router::Route}; }; }\n",
        )
        for source in cases:
            with self.subTest(source=source):
                errors = inventories.check_tree(
                    self.clean_fixture(
                        script_manifest=manifest,
                        script_files={"crates/script/src/lib.rs": source},
                    )
                )
                self.assertTrue(
                    any("bare or unresolved nav crate root in macro tokens is unsupported" in error
                        for error in errors),
                    errors,
                )

        resolved = inventories.check_tree(
            self.clean_fixture(
                script_manifest=manifest,
                script_files={
                    "crates/script/src/lib.rs": (
                        "macro_rules! m { ($item:path) => { let _: Option<$item> = None; }; }\n"
                        "fn f() { m!(nav_planner::router::Route); }\n"
                    )
                },
            )
        )
        self.assertTrue(any("macro_token_path" in error for error in resolved), resolved)

    def test_stale_test_import_exception_is_rejected(self) -> None:
        path = "crates/script/src/gatherer/runner.rs"
        exception = _record(
            "test_import_exception",
            path,
            "nav::collision::WorldCollision",
            "cfg(test)::tests",
            "exact_test_fixture_oracle_import",
        )
        root_module = '#[path = "gatherer/runner.rs"]\nmod runner;\n'
        script_files = {
            "crates/script/src/lib.rs": root_module,
            path: "#[cfg(test)]\nmod tests {}\n",
        }
        good = self.fixture(
            views=self.baseline_views(),
            script_files=script_files,
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        bad = self.fixture(
            views=self.baseline_views(),
            script_files=script_files,
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
            test_exceptions=(exception,),
        )
        self.assertEqual(inventories.check_tree(good), [])
        errors = inventories.check_tree(bad)
        self.assertTrue(any("stale test import exception" in error for error in errors), errors)

    def test_enum_payload_ownership_is_detected(self) -> None:
        enum_source = self.baseline_views() + (
            "\n#[derive(Clone, Copy)]\n"
            "pub enum ScalarUnit { Empty }\n"
            "#[derive(Clone, Copy)]\n"
            "pub struct ArrayClock(pub [u8; 12]);\n"
            "#[derive(Clone)]\n"
            "pub enum EnumPayloads {\n"
            "    Wrapped(String),\n"
            "    Unit,\n"
            "    Mixed { borrowed: &'static str, owned: Vec<u8> },\n"
            "}\n"
        )
        errors = inventories.check_tree(
            self.fixture(
                views=enum_source,
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("ScalarUnit", "scalar"),
                    ("ArrayClock", "scalar"),
                    ("EnumPayloads", "owning"),
                ),
            )
        )
        for symbol in (
            "EnumPayloads::Wrapped::0",
            "EnumPayloads::Mixed::borrowed",
            "EnumPayloads::Mixed::owned",
        ):
            with self.subTest(symbol=symbol):
                self.assertTrue(any(symbol in error for error in errors), errors)
        self.assertTrue(any("owning_derived_clone" in error for error in errors), errors)
        self.assertFalse(
            any(
                "owning_derived_clone" in error and "ScalarUnit" in error
                for error in errors
            )
        )

    def test_marked_walk_is_owning_by_foreign_type_closure(self) -> None:
        fields = (
            "prepared",
            "destination",
            "options",
            "arms",
        )
        violations = tuple(
            _record(
                "owning_public_field",
                VIEWS_PATH,
                f"MarkedWalk::{field}",
                "production",
                "public_field_of_owning_view",
                owner="T3",
            )
            for field in fields
        )
        root = self.fixture(
            views=self.baseline_views()
            + "use host_play::walk_map::{ActionError, MapContext, MapWalkPlan};\n"
            + "use host_play::WalkArms;\n"
            + "use nav::router::FindOptions;\n"
            + "use nav::tile::Tile;\n"
            + "pub struct MarkedWalk<'a> {\n"
            + "    pub prepared: Result<(MapContext, MapWalkPlan), ActionError>,\n"
            + "    pub destination: Option<Tile>,\n"
            + "    pub options: FindOptions,\n"
            + "    pub arms: &'a WalkArms,\n"
            + "}\n"
            + "pub struct BorrowedStatus<'a> {\n"
            + "    pub conditions: &'a api::process_condition::ProcessConditions,\n"
            + "}\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("MarkedWalk", "owning"),
                ("BorrowedStatus", "borrowed"),
            ),
            violations=violations,
        )
        errors = inventories.check_tree(root)
        print(f"GOOD MarkedWalk closure-derived owning classification: {errors}")
        self.assertEqual(errors, [])


    def test_f0_api_workspace_types_are_classified_from_definitions(self) -> None:
        aliases = "".join(
            f"pub type {alias} = {target};\n"
            for alias, target in F0_API_FOREIGN_ALIASES.items()
        )
        views = self.baseline_views() + F0_API_IMPORTS + aliases
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        # Settlement is Clone but not Copy, so like any local non-Copy type it is owning.
        expected = {
            alias: "owning" if alias == "PinSettlement" else "scalar"
            for alias in F0_API_FOREIGN_ALIASES
        }
        std_row = _foreign("std::num::NonZeroU64")

        def errors(classes: dict[str, str], data: str | None) -> list[str]:
            return inventories.check_tree(
                self.fixture(
                    views=views,
                    seam_types=base_seams + tuple(classes.items()),
                    foreign_types=data,
                    workspace_files=F0_API_CRATE,
                )
            )

        honest = errors(expected, _foreign_data(std_row))
        all_scalar = errors(
            {alias: "scalar" for alias in F0_API_FOREIGN_ALIASES}, _foreign_data(std_row)
        )
        without_std_row = errors(expected, None)
        with_api_rows = errors(
            expected,
            _foreign_data(std_row, *(_foreign(path) for path in F0_API_FOREIGN_TYPES)),
        )
        print(f"GOOD F0 API types classified from definitions: {honest}")
        print(f"BAD Settlement registered scalar: {all_scalar}")
        print(f"BAD std payload without a data row: {without_std_row}")
        print(f"BAD data rows naming F0 API types: {with_api_rows}")
        self.assertEqual(honest, [])
        self.assertEqual(
            all_scalar,
            [
                "seam classification disagrees with syntax: "
                f"{VIEWS_PATH}::PinSettlement is owning, registry says scalar"
            ],
        )
        self.assertIn(
            "crates/api/src/identity.rs::RequestId: unresolved imported seam field type NonZeroU64",
            without_std_row,
        )
        for index, path in enumerate(F0_API_FOREIGN_TYPES, start=1):
            self.assertIn(
                f"foreign types: foreign_types[{index}] names workspace type {path}; "
                "workspace types are classified from their definitions",
                with_api_rows,
            )
        self.assertIn(
            "crates/api/src/identity.rs::RequestId: unresolved imported seam field type NonZeroU64",
            with_api_rows,
        )

    def test_workspace_definition_classification_is_checked_from_syntax(self) -> None:
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        uses = "pub type UsesRequest = api::identity::RequestId;\n"
        copy_id = "#[derive(Clone, Copy)]\npub struct RequestId(u64);\n"

        def tree(identity: str, extra: tuple[tuple[str, str], ...]) -> Path:
            return self.fixture(
                views=self.baseline_views() + uses,
                seam_types=seams + extra,
                workspace_files={
                    "crates/api/src/lib.rs": "pub mod identity;\n",
                    "crates/api/src/identity.rs": identity,
                },
            )

        self.assertEqual(
            inventories.check_tree(tree(copy_id, (("UsesRequest", "scalar"),))),
            [],
        )
        drifts = {
            "owned field": "#[derive(Clone)]\npub struct RequestId(Vec<u8>);\n",
            "alias retarget": "pub type RequestId = Vec<u8>;\n",
        }
        for label, identity in drifts.items():
            with self.subTest(drift=label):
                stale = tree(identity, (("UsesRequest", "scalar"),))
                stale_errors = inventories.check_tree(stale)
                self.assertTrue(
                    any(
                        "UsesRequest is owning, registry says scalar" in error
                        for error in stale_errors
                    ),
                    stale_errors,
                )
                updated = tree(identity, (("UsesRequest", "owning"),))
                self.assertEqual(inventories.check_tree(updated), [])

    def test_workspace_paths_resolve_to_the_defining_item(self) -> None:
        api_lib = (
            "pub mod identity;\n"
            "pub mod prelude {\n    pub use crate::identity::RequestId as Rid;\n}\n"
            "pub use identity::RequestId;\n"
            "pub type AliasId = identity::RequestId;\n"
            "mod chain_a {\n    pub use super::chain_b::Hop;\n}\n"
            "mod chain_b {\n    pub use crate::identity::RequestId as Hop;\n}\n"
            "pub use chain_a::Hop;\n"
            '#[path = "../generated/ids.rs"]\n'
            "pub mod generated;\n"
        )
        # A crate type sharing a baseline frontend name, and an explicit Clone in
        # another crate, must not touch frontend-core's own rules.
        api_extra = (
            "pub struct Phase(String);\n"
            "pub struct Holder(String);\n"
            "impl Clone for Holder {\n"
            "    fn clone(&self) -> Self {\n"
            "        Holder(self.0.clone())\n"
            "    }\n"
            "}\n"
        )
        views = self.baseline_views() + (
            "use api::identity::RequestId as Renamed;\n"
            "pub type ViaRenamed = Renamed;\n"
            "pub type ViaReexport = api::RequestId;\n"
            "pub type ViaPrelude = api::prelude::Rid;\n"
            "pub type ViaAlias = api::AliasId;\n"
            "pub type ViaChain = api::Hop;\n"
            "pub type ViaPathModule = api::generated::GeneratedId;\n"
            "pub use api::identity::RequestId as ExportedId;\n"
            "pub type ViaPhase = api::identity::Phase;\n"
            "pub struct Holder {\n    inner: String,\n}\n"
        )
        symbols = (
            "ExportedId",
            "ViaAlias",
            "ViaChain",
            "ViaPathModule",
            "ViaPrelude",
            "ViaReexport",
            "ViaRenamed",
        )
        fixed = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("ViaPhase", "owning"),
            ("Holder", "owning"),
        )
        definitions = {
            "scalar": "#[derive(Clone, Copy)]\npub struct RequestId(u64);\n",
            "owning": "#[derive(Clone)]\npub struct RequestId(String);\n",
        }
        for classification, identity in definitions.items():
            with self.subTest(definition=classification):
                other = "owning" if classification == "scalar" else "scalar"
                results = {}
                for registered in (classification, other):
                    results[registered] = inventories.check_tree(
                        self.fixture(
                            views=views,
                            seam_types=fixed + tuple((symbol, registered) for symbol in symbols),
                            workspace_files={
                                "crates/api/src/lib.rs": api_lib,
                                "crates/api/src/identity.rs": identity + api_extra,
                                "crates/api/generated/ids.rs": (
                                    "pub use crate::identity::RequestId as GeneratedId;\n"
                                ),
                            },
                        )
                    )
                print(f"GOOD workspace paths, {classification} definition: {results[classification]}")
                print(f"BAD workspace paths registered {other}: {results[other]}")
                self.assertEqual(results[classification], [])
                self.assertEqual(
                    results[other],
                    [
                        "seam classification disagrees with syntax: "
                        f"{VIEWS_PATH}::{symbol} is {classification}, registry says {other}"
                        for symbol in symbols
                    ],
                )

    def test_workspace_resolution_fails_closed(self) -> None:
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Uses", "scalar"))
        api_manifest = '[package]\nname = "api"\nversion = "0.0.0"\nedition = "2024"\n'
        cases: dict[str, tuple[dict[str, str], str, str]] = {
            "use cycle": (
                {
                    "crates/api/src/lib.rs": (
                        "mod a {\n    pub use super::b::Loop;\n}\n"
                        "mod b {\n    pub use super::a::Loop;\n}\n"
                        "pub use a::Loop;\n"
                    )
                },
                "api::Loop",
                f"{VIEWS_PATH}::Uses: unresolved",
            ),
            "type cycle": (
                {
                    "crates/api/src/lib.rs": (
                        "#[derive(Clone, Copy)]\npub struct Ping {\n    pong: Pong,\n}\n"
                        "#[derive(Clone, Copy)]\npub struct Pong {\n    ping: Ping,\n}\n"
                    )
                },
                "api::Ping",
                "recursive type ownership cannot be resolved",
            ),
            "missing item": (
                {"crates/api/src/lib.rs": "pub mod identity;\n", "crates/api/src/identity.rs": ""},
                "api::identity::Missing",
                f"{VIEWS_PATH}::Uses: unresolved public seam field type api::identity::Missing",
            ),
            "macro in consulted module": (
                {
                    "crates/api/src/lib.rs": "pub mod identity;\n",
                    "crates/api/src/identity.rs": (
                        "macro_rules! id {\n    ($name:ident) => {\n"
                        "        pub struct $name(String);\n    };\n}\n"
                        "id!(Hidden);\n"
                        "#[derive(Clone, Copy)]\npub struct RequestId(u64);\n"
                    ),
                },
                "api::identity::RequestId",
                "crates/api/src/identity.rs: item-generating macro syntax is unsupported "
                "(consulted for a seam field type)",
            ),
            "pre-2018 crate-relative path": (
                {
                    "crates/api/src/lib.rs": "pub mod identity;\npub mod selected;\n",
                    "crates/api/src/selected.rs": "#[derive(Clone, Copy)]\npub struct RunKey(u64);\n",
                    "crates/api/src/identity.rs": (
                        "#[derive(Clone, Copy)]\npub struct RequestId(selected::RunKey);\n"
                    ),
                },
                "api::identity::RequestId",
                "crates/api/src/identity.rs::RequestId: unresolved public seam field type "
                "selected::RunKey",
            ),
            "unlisted std payload": (
                {
                    "crates/api/src/lib.rs": (
                        "#[derive(Clone, Copy)]\npub struct RequestId(std::num::NonZeroU32);\n"
                    )
                },
                "api::RequestId",
                "crates/api/src/lib.rs::RequestId: unresolved public seam field type "
                "std::num::NonZeroU32",
            ),
            "unparseable module": (
                {
                    "crates/api/src/lib.rs": "pub mod identity;\n",
                    "crates/api/src/identity.rs": "pub struct RequestId(u64) }\n",
                },
                "api::identity::RequestId",
                f"{VIEWS_PATH}::Uses: workspace crate api: crates/api/src/identity.rs: "
                "unsupported or malformed Rust syntax",
            ),
            "no library target": (
                {"crates/tool/src/main.rs": "fn main() {}\n"},
                "tool::Thing",
                f"{VIEWS_PATH}::Uses: workspace crate tool has no library target",
            ),
            "unsupported edition": (
                {
                    "crates/api/Cargo.toml": api_manifest,
                    "crates/api/src/lib.rs": "#[derive(Clone, Copy)]\npub struct RequestId(u64);\n",
                },
                "api::RequestId",
                f"{VIEWS_PATH}::Uses: crates/api/Cargo.toml: parser adapter requires edition 2021",
            ),
        }
        for label, (files, target, expected) in cases.items():
            with self.subTest(case=label):
                errors = inventories.check_tree(
                    self.fixture(
                        views=self.baseline_views() + f"pub type Uses = {target};\n",
                        seam_types=seams,
                        workspace_files=files,
                    )
                )
                print(f"BAD workspace resolution ({label}): {errors}")
                self.assertTrue(any(expected in error for error in errors), errors)
                self.assertIn(f"stale seam type classification: {VIEWS_PATH}::Uses", errors)

    def test_builtin_entry_keeps_precedence_over_workspace_definition(self) -> None:
        # A built-in path keeps precedence even when the workspace definition
        # says otherwise.
        root = self.fixture(
            views=self.baseline_views()
            + "pub type Diff = script::CatalogDiff;\npub type Compiled = script::CompiledId;\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("Diff", "owning"),
                ("Compiled", "scalar"),
            ),
            script_files={
                "crates/script/src/lib.rs": (
                    "#[derive(Clone, Copy)]\npub struct CatalogDiff(u8);\n"
                    "pub struct CompiledId(pub &'static str);\n"
                )
            },
            workspace_files={},
        )
        errors = inventories.check_tree(root)
        print(f"GOOD built-in precedence over workspace definitions: {errors}")
        self.assertEqual(errors, [])

    def test_workspace_manifest_is_read_strictly(self) -> None:
        cases = {
            "glob member": ('[workspace]\nmembers = ["crates/*"]\n', "unsupported workspace member crates/*"),
            "escaping member": ('[workspace]\nmembers = ["../outside"]\n', "unsupported workspace member ../outside"),
            "non-string member": ("[workspace]\nmembers = [7]\n", "workspace members must be an array of strings"),
            "missing member manifest": (
                '[workspace]\nmembers = ["crates/absent"]\n',
                "crates/absent/Cargo.toml must be a regular file",
            ),
            "invalid TOML": ("[workspace\n", "workspace crates: "),
        }
        for label, (manifest, expected) in cases.items():
            with self.subTest(case=label):
                root = self.fixture(
                    views=self.baseline_views(),
                    seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
                )
                (root / "Cargo.toml").write_text(manifest, encoding="utf-8")
                errors = inventories.check_tree(root)
                print(f"BAD workspace manifest ({label}): {errors}")
                self.assertTrue(
                    any(error.startswith("workspace crates: ") and expected in error for error in errors),
                    errors,
                )

    def test_std_leaf_names_defined_in_the_workspace_are_classified_from_definitions(self) -> None:
        # Wonder eprime-r3 F1: a workspace type named like a std scalar or
        # transparent container is classified from its definition.  Its name
        # alone never skips the payload.
        names = sorted(
            set(inventories.STD_TRANSPARENT_TYPE_MODULES) | inventories.KNOWN_SCALAR_TYPES
        )
        self.assertEqual(len(names), 24)
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("AttackView", "borrowed"))
        disagrees = (
            f"seam classification disagrees with syntax: {VIEWS_PATH}::AttackView "
            "is owning, registry says borrowed"
        )

        def holder(payload: str) -> str:
            return (
                "#[derive(Clone)]\npub struct AttackView {\n"
                f"    pub label: &'static str,\n    pub payload: {payload},\n}}\n"
            )

        for name in names:
            for spelling, (imports, payload) in {
                "qualified": ("", f"api::{name}"),
                "imported": (f"use api::{name};\n", name),
                "glob": ("use api::*;\n", name),
            }.items():
                with self.subTest(name=name, spelling=spelling):
                    errors = inventories.check_tree(
                        self.fixture(
                            views=imports + self.baseline_views() + holder(payload),
                            seam_types=seams,
                            workspace_files={
                                "crates/api/src/lib.rs": (
                                    f"#[derive(Clone)]\npub struct {name}(pub Vec<u8>);\n"
                                )
                            },
                        )
                    )
                    self.assertIn(disagrees, errors)
        wrapper = "#[derive(Clone)]\npub struct Wrapping(pub Vec<u8>);\n"
        shapes: dict[str, tuple[str, str, str, str]] = {
            "enum": (
                "#[derive(Clone)]\npub enum Option {\n    Some(Vec<u8>),\n    None,\n}\n",
                "",
                "api::Option",
                disagrees,
            ),
            "type alias": ("pub type Wrapping = Vec<u8>;\n", "", "api::Wrapping", disagrees),
            "renamed import": (
                "#[derive(Clone)]\npub struct Payload(pub Vec<u8>);\n",
                "use api::Payload as Wrapping;\n",
                "Wrapping",
                disagrees,
            ),
            "glob import": (wrapper, "use api::*;\n", "Wrapping", disagrees),
            "local definition": (
                wrapper,
                "#[derive(Clone)]\npub struct Option(pub Vec<u8>);\n",
                "Option",
                disagrees,
            ),
            "generic argument": (wrapper, "", "Option<api::Wrapping>", disagrees),
            "union": (
                "pub union Wrapping {\n    pub bytes: std::mem::ManuallyDrop<Vec<u8>>,\n}\n",
                "",
                "api::Wrapping",
                "crates/api/src/lib.rs: unsupported public seam type syntax (UNION)",
            ),
        }
        for label, (api, imports, payload, expected) in shapes.items():
            with self.subTest(shape=label):
                errors = inventories.check_tree(
                    self.fixture(
                        views=imports + self.baseline_views() + holder(payload),
                        seam_types=seams,
                        workspace_files={"crates/api/src/lib.rs": api},
                    )
                )
                print(f"BAD std-named workspace payload ({label}): {errors}")
                self.assertIn(expected, errors)
        # A generic parameter is a one-segment path: `api::T` is the workspace
        # type even inside an item with a parameter named `T`.
        generic = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone)]\npub struct AttackView<T> {\n"
                "    pub label: &'static str,\n    pub payload: api::T,\n    pub extra: Option<T>,\n}\n",
                seam_types=seams,
                workspace_files={
                    "crates/api/src/lib.rs": "#[derive(Clone)]\npub struct T(pub Vec<u8>);\n"
                },
            )
        )
        print(f"BAD workspace path ending in a generic parameter name: {generic}")
        self.assertIn(disagrees, generic)

    def test_std_leaf_items_keep_the_shortcut_and_their_generic_arguments(self) -> None:
        views = (
            "use std::cmp;\nuse std::num::Wrapping;\n"
            + self.baseline_views()
            + "#[derive(Clone, Copy)]\n"
            "pub struct StdLeaves {\n"
            "    pub a: Option<u64>,\n"
            "    pub b: Result<u64, bool>,\n"
            "    pub c: Wrapping<u64>,\n"
            "    pub d: std::num::Wrapping<u8>,\n"
            "    pub e: core::num::Wrapping<u8>,\n"
            "    pub f: cmp::Reverse<u64>,\n"
            "    pub g: std::marker::PhantomData<u64>,\n"
            "    pub h: core::task::Poll<u64>,\n"
            "    pub i: std::ops::ControlFlow<u64, u8>,\n"
            "    pub j: std::primitive::u64,\n"
            "    pub k: char,\n"
            "}\n"
            "pub struct StdOwning {\n"
            "    wrapped: Option<api::Wrapper>,\n"
            "    bytes: std::num::Wrapping<Vec<u8>>,\n"
            "}\n"
        )
        root = self.fixture(
            views=views,
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("StdLeaves", "scalar"),
                ("StdOwning", "owning"),
            ),
            workspace_files={
                "crates/api/src/lib.rs": "#[derive(Clone)]\npub struct Wrapper(pub Vec<u8>);\n"
            },
        )
        errors = inventories.check_tree(root)
        print(f"GOOD std leaf items: {errors}")
        self.assertEqual(errors, [])

    def test_phantom_data_accepts_function_pointer_marker(self) -> None:
        marker_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("MarkerView", "scalar"),
        )
        cases = {
            "std marker": (
                self.baseline_views()
                + "#[derive(Clone, Copy)]\n"
                + "pub struct MarkerView { marker: std::marker::PhantomData<fn() -> u64> }\n"
            ),
            "generic marker": (
                self.baseline_views()
                + "#[derive(Clone, Copy)]\n"
                + "pub struct MarkerView<F> { marker: std::marker::PhantomData<fn() -> F> }\n"
            ),
            "core marker alias": (
                "use core::marker::PhantomData as Marker;\n"
                + self.baseline_views()
                + "#[derive(Clone, Copy)]\n"
                + "pub struct MarkerView { marker: Marker<fn() -> u64> }\n"
            ),
        }
        for label, views in cases.items():
            with self.subTest(marker=label):
                errors = inventories.check_tree(
                    self.fixture(views=views, seam_types=marker_types)
                )
                self.assertEqual(errors, [])

    def test_function_pointer_markers_inside_containers_and_references(self) -> None:
        cases = (
            ("Vec<Marker<fn() -> u64>>", "owning"),
            ("&'static Marker<fn() -> u64>", "borrowed"),
        )
        for field_type, classification in cases:
            with self.subTest(field_type=field_type):
                errors = inventories.check_tree(
                    self.fixture(
                        views=(
                            "use std::marker::PhantomData as Marker;\n"
                            + self.baseline_views()
                            + f"pub struct MarkerView {{ marker: {field_type} }}\n"
                        ),
                        seam_types=(
                            ("FleetCounts", "scalar"),
                            ("FleetView", "borrowed"),
                            ("MarkerView", classification),
                        ),
                    )
                )
                self.assertEqual(errors, [])

    def test_workspace_phantom_data_name_is_not_a_marker(self) -> None:
        for field_type in (
            "PhantomData<fn() -> u64>",
            "Vec<PhantomData<fn() -> u64>>",
            "&'static PhantomData<fn() -> u64>",
        ):
            with self.subTest(field_type=field_type):
                errors = inventories.check_tree(
                    self.fixture(
                        views=(
                            "use api::PhantomData;\n"
                            + self.baseline_views()
                            + f"pub struct MarkerView {{ marker: {field_type} }}\n"
                        ),
                        seam_types=(
                            ("FleetCounts", "scalar"),
                            ("FleetView", "borrowed"),
                            ("MarkerView", "scalar"),
                        ),
                        workspace_files={
                            "crates/api/src/lib.rs": "pub struct PhantomData<T>(T);\n"
                        },
                    )
                )
                self.assertTrue(
                    any("unsupported field type syntax (FN_PTR_TYPE)" in error for error in errors),
                    errors,
                )

    def test_leaf_names_that_are_not_the_std_item_fail_closed(self) -> None:
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Uses", "scalar"))
        cases = {
            "non-workspace crate": (
                "",
                "other::Wrapping<u64>",
                f"{VIEWS_PATH}::Uses: unresolved public seam field type other::Wrapping",
            ),
            "non-std import": (
                "use other::Option;\n",
                "Option<u64>",
                f"{VIEWS_PATH}::Uses: unresolved imported seam field type Option",
            ),
            "non-prelude name without import": (
                "",
                "Wrapping<u64>",
                f"{VIEWS_PATH}::Uses: unresolved public seam field type Wrapping",
            ),
            "prelude name under an unindexed glob": (
                "use other::*;\n",
                "u64",
                f"{VIEWS_PATH}::Uses: ambiguous cfg/alternative seam field type u64",
            ),
            "crate-relative name": (
                "",
                "crate::Option<u64>",
                f"{VIEWS_PATH}::Uses: unresolved public seam field type crate::Option",
            ),
        }
        for label, (imports, target, expected) in cases.items():
            with self.subTest(case=label):
                errors = inventories.check_tree(
                    self.fixture(
                        views=imports + self.baseline_views() + f"pub type Uses = {target};\n",
                        seam_types=seams,
                    )
                )
                print(f"BAD non-std leaf path ({label}): {errors}")
                self.assertIn(expected, errors)
                self.assertIn(f"stale seam type classification: {VIEWS_PATH}::Uses", errors)
        generic = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone, Copy)]\npub struct Held<Wrapping = Vec<u8>>(Wrapping);\n",
                seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Held", "scalar")),
            )
        )
        print(f"BAD generic parameter named like a std leaf: {generic}")
        self.assertIn(f"{VIEWS_PATH}::Held: generic type defaults are unsupported (Wrapping)", generic)

    def test_workspace_std_named_payload_classification_is_checked(self) -> None:
        api = (
            "#[derive(Clone, Copy)]\npub struct Plain(pub u64);\n"
            "#[derive(Clone)]\npub struct Wrapping(pub Vec<u8>);\n"
        )

        def tree(payload: str, registered: str) -> Path:
            temporary = tempfile.TemporaryDirectory(prefix="f0-std-leaf-")
            self.addCleanup(temporary.cleanup)
            return _write_fixture(
                Path(temporary.name),
                views=self.baseline_views()
                + "#[derive(Clone)]\npub struct AttackView {\n"
                f"    pub label: &'static str,\n    pub payload: api::{payload},\n}}\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("AttackView", registered),
                ),
                workspace_files={"crates/api/src/lib.rs": api},
            )

        self.assertEqual(inventories.check_tree(tree("Plain", "borrowed")), [])
        errors = inventories.check_tree(tree("Wrapping", "borrowed"))
        self.assertTrue(
            any("AttackView is owning, registry says borrowed" in error for error in errors),
            errors,
        )

    def test_workspace_crate_names_cannot_shadow_other_crates(self) -> None:
        # Wonder eprime-r3 F3: seam resolution reads a path's first segment as
        # the workspace crate of that name.  A member may not take a sysroot or
        # keyword name, and no manifest may declare another crate under a
        # member's name (the vendored `client` path dependency, for example).
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        for name in ("std", "core", "alloc", "proc_macro", "test", "crate", "self", "super", "Self"):
            with self.subTest(member=name):
                errors = inventories.check_tree(
                    self.fixture(
                        views=self.baseline_views(),
                        seam_types=seams,
                        workspace_files={f"crates/{name}/src/lib.rs": ""},
                    )
                )
                print(f"BAD reserved workspace crate name {name}: {errors}")
                self.assertIn(
                    f"workspace crates: crates/{name}/Cargo.toml: workspace crate name {name} "
                    "is reserved",
                    errors,
                )
        package = '[package]\nname = "{}"\nversion = "0.0.0"\nedition = "2021"\n'
        uses = "pub type Uses = api::T;\n"
        api = "#[derive(Clone, Copy)]\npub struct T(pub u64);\n"
        cases: dict[str, tuple[str, dict[str, str], str | None]] = {
            "workspace dependency": (
                '[workspace.dependencies]\nclient = { path = "vendor/client" }\n',
                {},
                "Cargo.toml: [workspace.dependencies] client is not workspace crate client",
            ),
            "member dependency": (
                "",
                {"crates/api/Cargo.toml": package.format("api") + '[dependencies]\nclient = "1"\n'},
                "crates/api/Cargo.toml: [dependencies] client is not workspace crate client",
            ),
            "target dev-dependency": (
                "",
                {
                    "crates/api/Cargo.toml": package.format("api")
                    + "[target.'cfg(unix)'.dev-dependencies]\n"
                    + 'client = { git = "https://example.invalid/client" }\n'
                },
                "crates/api/Cargo.toml: [target.cfg(unix).dev-dependencies] client is not "
                "workspace crate client",
            ),
            "reserved dependency key": (
                "",
                {
                    "crates/api/Cargo.toml": package.format("api")
                    + '[dependencies]\nstd = { package = "evil", version = "1" }\n'
                },
                "crates/api/Cargo.toml: [dependencies] std is a reserved crate name",
            ),
            "dependencies on the members themselves": (
                '[workspace.dependencies]\napi = { path = "crates/api" }\n'
                'vendored = { path = "vendor/client" }\n',
                {
                    "crates/frontend-core/Cargo.toml": package.format("frontend-core")
                    + '[dependencies]\napi = { workspace = true }\nvendored = { workspace = true }\n',
                    "crates/client/Cargo.toml": package.format("client")
                    + '[dependencies]\napi = { path = "../api" }\n'
                    + '[build-dependencies]\nfrontend-core = { path = "../frontend-core" }\n',
                },
                None,
            ),
        }
        for label, (workspace_extra, manifests, expected) in cases.items():
            with self.subTest(case=label):
                root = self.fixture(
                    views=self.baseline_views() + uses,
                    seam_types=seams + (("Uses", "scalar"),),
                    workspace_files={"crates/api/src/lib.rs": api, "crates/client/src/lib.rs": ""},
                )
                manifest = root / "Cargo.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8") + workspace_extra, encoding="utf-8"
                )
                for relative, contents in manifests.items():
                    (root / relative).write_text(contents, encoding="utf-8")
                errors = inventories.check_tree(root)
                print(f"workspace crate name collision ({label}): {errors}")
                if expected is None:
                    self.assertEqual(errors, [])
                else:
                    self.assertTrue(
                        any(
                            error.startswith("workspace crates: ") and expected in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_inventory_reads_never_traverse_a_symlink(self) -> None:
        # Wonder eprime-r3 F2: no path component below the tree root may be a
        # symlink, for crate directories as for the foreign-type data file.
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Uses", "scalar"))

        def tree() -> Path:
            return self.fixture(
                views=self.baseline_views() + "pub type Uses = api::T;\n",
                seam_types=seams,
                workspace_files={
                    "crates/api/src/lib.rs": "#[derive(Clone, Copy)]\npub struct T(pub u64);\n"
                },
            )

        self.assertEqual(inventories.check_tree(tree()), [])
        cases = {
            "crates/api": "workspace crates: crates/api/Cargo.toml must not traverse a symlink",
            "crates/api/src": "workspace crates: crates/api/src/lib.rs must not traverse a symlink",
            "crates/frontend-core": "crates/frontend-core/src: symlinked Rust input is unsupported",
            "crates/frontend-core/src": (
                "crates/frontend-core/src: symlinked Rust input is unsupported"
            ),
            "crates/script": "crates/script/src: symlinked Rust input is unsupported",
            "tools": "inventory: tools/architecture/inventories.json must not traverse a symlink",
        }
        for linked, expected in cases.items():
            with self.subTest(linked=linked):
                root = tree()
                outside = tempfile.TemporaryDirectory(prefix="f0-outside-")
                self.addCleanup(outside.cleanup)
                moved = Path(outside.name) / "moved"
                (root / linked).rename(moved)
                (root / linked).symlink_to(moved, target_is_directory=True)
                errors = inventories.check_tree(root)
                print(f"BAD symlinked {linked}: {errors}")
                self.assertIn(expected, errors)

    def test_foreign_rows_may_not_name_workspace_types(self) -> None:
        views = self.baseline_views() + "pub type UsesHandle = client::session::Handle;\n"
        for workspace_path in ("api::identity::RequestId", "frontend_core::views::FleetCounts"):
            with self.subTest(row=workspace_path):
                root = self.fixture(
                    views=views,
                    seam_types=(
                        ("FleetCounts", "scalar"),
                        ("FleetView", "borrowed"),
                        ("UsesHandle", "scalar"),
                    ),
                    foreign_types=_foreign_data(
                        _foreign("client::session::Handle"), _foreign(workspace_path)
                    ),
                    workspace_files={"crates/api/src/lib.rs": ""},
                )
                errors = inventories.check_tree(root)
                print(f"BAD data row naming workspace type {workspace_path}: {errors}")
                self.assertIn(
                    f"foreign types: foreign_types[1] names workspace type {workspace_path}; "
                    "workspace types are classified from their definitions",
                    errors,
                )
                self.assertIn(
                    f"{VIEWS_PATH}::UsesHandle: unresolved public seam field type "
                    "client::session::Handle",
                    errors,
                )

    def test_foreign_data_row_keeps_generic_argument_ownership(self) -> None:
        views = (
            self.baseline_views()
            + "use client::session::{Settlement, Token};\n"
            + "pub type SettledScalar = Settlement<Token, Token>;\n"
            + "pub type SettledBytes = Settlement<Vec<u8>, Token>;\n"
            + "pub type SettledCatalog = Settlement<Token, script::CatalogDiff>;\n"
            + "pub type SettledView<'a> = Settlement<&'a str, Token>;\n"
            + "#[derive(Clone, Copy)]\n"
            + "pub struct SettledHolder {\n"
            + "    settled: Settlement<Token, std::sync::mpsc::Sender<u8>>,\n"
            + "}\n"
        )
        data = _foreign_data(
            _foreign("client::session::Settlement"), _foreign("client::session::Token")
        )
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        clone_violation = (
            _record(
                "owning_derived_clone",
                VIEWS_PATH,
                "SettledHolder",
                "production",
                "derived_Clone_on_owning_view",
                owner="T3",
            ),
        )
        honest_errors = inventories.check_tree(
            self.fixture(
                views=views,
                seam_types=base_seams
                + (
                    ("SettledScalar", "scalar"),
                    ("SettledBytes", "owning"),
                    ("SettledCatalog", "owning"),
                    ("SettledView", "borrowed"),
                    ("SettledHolder", "owning"),
                ),
                violations=clone_violation,
                foreign_types=data,
            )
        )
        exempt_errors = inventories.check_tree(
            self.fixture(
                views=views,
                seam_types=base_seams
                + (
                    ("SettledScalar", "scalar"),
                    ("SettledBytes", "scalar"),
                    ("SettledCatalog", "scalar"),
                    ("SettledView", "scalar"),
                    ("SettledHolder", "scalar"),
                ),
                violations=clone_violation,
                foreign_types=data,
            )
        )
        print(f"GOOD data-row generic argument ownership: {honest_errors}")
        print(f"BAD data row as blanket scalar: {exempt_errors}")
        self.assertEqual(honest_errors, [])
        self.assertEqual(
            exempt_errors,
            [
                "seam classification disagrees with syntax: "
                f"{VIEWS_PATH}::SettledBytes is owning, registry says scalar",
                "seam classification disagrees with syntax: "
                f"{VIEWS_PATH}::SettledCatalog is owning, registry says scalar",
                "seam classification disagrees with syntax: "
                f"{VIEWS_PATH}::SettledHolder is owning, registry says scalar",
                "seam classification disagrees with syntax: "
                f"{VIEWS_PATH}::SettledView is borrowed, registry says scalar",
            ],
        )

    def test_unlisted_foreign_types_still_fail_resolution(self) -> None:
        settlement = _foreign_data(_foreign("client::session::Settlement"))
        cases = {
            "UnlistedImport": (
                "use client::session::Missing;\n"
                "#[derive(Clone, Copy)]\n"
                "pub struct UnlistedImport { id: Missing }\n",
                None,
                "unresolved imported seam field type Missing",
            ),
            "UnlistedPath": (
                "#[derive(Clone, Copy)]\n"
                "pub struct UnlistedPath { receipt: client::session::Receipt }\n",
                _foreign_data(),
                "unresolved public seam field type client::session::Receipt",
            ),
            "UnlistedLeaf": (
                "use client::session::Settlement;\n"
                "#[derive(Clone, Copy)]\n"
                "pub struct UnlistedLeaf {\n"
                "    settled: Settlement<u8, u8>,\n"
                "    other: client::other::Settlement<u8, u8>,\n"
                "}\n",
                settlement,
                "unresolved public seam field type client::other::Settlement",
            ),
            "UnlistedArgument": (
                "use client::session::Settlement;\n"
                "#[derive(Clone, Copy)]\n"
                "pub struct UnlistedArgument {\n"
                "    settled: Settlement<client::session::Missing, u8>,\n"
                "}\n",
                settlement,
                "unresolved public seam field type client::session::Missing",
            ),
        }
        for symbol, (source, data, expected) in cases.items():
            with self.subTest(symbol=symbol):
                root = self.fixture(
                    views=self.baseline_views() + source,
                    seam_types=(
                        ("FleetCounts", "scalar"),
                        ("FleetView", "borrowed"),
                        (symbol, "scalar"),
                    ),
                    foreign_types=data,
                )
                errors = inventories.check_tree(root)
                print(f"BAD unlisted foreign seam type {symbol}: {errors}")
                self.assertIn(f"{VIEWS_PATH}::{symbol}: {expected}", errors)

    def test_foreign_type_data_is_strictly_validated(self) -> None:
        valid = _foreign("client::session::Token")
        scope = "client::session::Scope"
        views = (
            self.baseline_views()
            + "#[derive(Clone, Copy)]\n"
            + "pub struct UsesToken { id: client::session::Token }\n"
        )
        depth = 100_000
        cases: dict[str, tuple[str | None, str | tuple[str, ...]]] = {
            "invalid json": ("{", "foreign types: cannot load"),
            "deep nesting": (
                '{"schema_version": 1, "foreign_types": ' + "[" * depth + "]" * depth + "}",
                (
                    "foreign types: cannot load",
                    "foreign types: foreign_types[0] has unknown or missing fields",
                ),
            ),
            "duplicate json key": (
                '{"schema_version": 1, "schema_version": 1, "foreign_types": []}',
                "duplicate JSON key 'schema_version'",
            ),
            "top-level array": ("[]", "top-level fields must be exactly"),
            "extra top-level field": (
                json.dumps({"schema_version": 1, "foreign_types": [valid], "notes": ""}),
                "top-level fields must be exactly",
            ),
            "schema version 2": (
                json.dumps({"schema_version": 2, "foreign_types": [valid]}),
                "schema_version must be integer 1",
            ),
            "boolean schema version": (
                json.dumps({"schema_version": True, "foreign_types": [valid]}),
                "schema_version must be integer 1",
            ),
            "rows not an array": (
                json.dumps({"schema_version": 1, "foreign_types": {"client::session::Token": "scalar"}}),
                "foreign_types must be an array",
            ),
            "extra row field": (_foreign_data(valid, dict(_foreign(scope), owner="T1")), "has unknown or missing fields"),
            "missing reason": (
                _foreign_data(valid, {"path": scope, "classification": "scalar"}),
                "has unknown or missing fields",
            ),
            "single segment": (_foreign_data(valid, _foreign("Scope")), ".path must be an exact external Rust type path"),
            "leading separator": (
                _foreign_data(valid, _foreign("::client::session::Scope")),
                ".path must be an exact external Rust type path",
            ),
            "crate-relative": (_foreign_data(valid, _foreign("crate::views::Scope")), ".path must be an exact external Rust type path"),
            "glob": (_foreign_data(valid, _foreign("client::session::*")), ".path must be an exact external Rust type path"),
            "generic arguments": (
                _foreign_data(valid, _foreign("client::session::Settlement<u8, u8>")),
                ".path must be an exact external Rust type path",
            ),
            "whitespace": (
                _foreign_data(valid, _foreign(" client::session::Scope")),
                ".path must be an exact external Rust type path",
            ),
            "trailing newline": (
                _foreign_data(valid, _foreign("client::session::Scope\n")),
                ".path must be an exact external Rust type path",
            ),
            "non-string path": (
                _foreign_data(valid, {"path": 7, "classification": "scalar", "reason": "x"}),
                ".path must be an exact external Rust type path",
            ),
            "unknown class": (_foreign_data(valid, _foreign(scope, "copy")), "has unknown classification"),
            "non-string class": (
                _foreign_data(valid, {"path": scope, "classification": ["scalar"], "reason": "x"}),
                "has unknown classification",
            ),
            "blank reason": (
                _foreign_data(valid, {"path": scope, "classification": "scalar", "reason": " "}),
                ".reason must be nonblank",
            ),
            "shadows built-in": (
                _foreign_data(valid, _foreign("script::CatalogDiff", "scalar")),
                "shadows built-in foreign type script::CatalogDiff",
            ),
            "duplicate path": (
                _foreign_data(valid, _foreign("client::session::Token", "owning")),
                "duplicate path client::session::Token",
            ),
            "directory": (None, "must be a regular file"),
        }
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("UsesToken", "scalar"))
        unresolved = f"{VIEWS_PATH}::UsesToken: unresolved public seam field type client::session::Token"
        for label, (content, expected) in cases.items():
            with self.subTest(case=label):
                root = self.fixture(views=views, seam_types=seams, foreign_types=content)
                if content is None:
                    (root / inventories.DATA_DIR_RELATIVE / inventories.FOREIGN_TYPES_RELATIVE).mkdir()
                errors = inventories.check_tree(root)
                print(f"BAD foreign type data ({label}): {[error[:200] for error in errors]}")
                expected_errors = (expected,) if isinstance(expected, str) else expected
                self.assertTrue(
                    any(
                        expected_error in error
                        for error in errors
                        for expected_error in expected_errors
                    ),
                    errors,
                )
                self.assertIn(unresolved, errors)
        symlinks = {
            "symlinked file": inventories.DATA_DIR_RELATIVE / inventories.FOREIGN_TYPES_RELATIVE,
            "symlinked parent directory": inventories.DATA_DIR_RELATIVE,
        }
        for label, linked in symlinks.items():
            with self.subTest(case=label):
                root = self.fixture(views=views, seam_types=seams)
                outside = root / "outside"
                outside.mkdir()
                (outside / inventories.FOREIGN_TYPES_RELATIVE.name).write_text(
                    _foreign_data(valid), encoding="utf-8"
                )
                link = root / linked
                link.parent.mkdir(parents=True, exist_ok=True)
                if linked == inventories.DATA_DIR_RELATIVE / inventories.FOREIGN_TYPES_RELATIVE:
                    link.symlink_to(outside / inventories.FOREIGN_TYPES_RELATIVE.name)
                else:
                    link.rename(outside / "original-data")
                    link.symlink_to(outside, target_is_directory=True)
                errors = inventories.check_tree(root)
                print(f"BAD foreign type data ({label}): {errors}")
                self.assertIn(
                    "foreign types: tools/architecture/foreign_types.json must not traverse a symlink",
                    errors,
                )
                self.assertIn(unresolved, errors)

    def test_deeply_nested_inventory_fails_closed(self) -> None:
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        depth = 100_000
        (root / inventories.DATA_DIR_RELATIVE / inventories.INVENTORY_RELATIVE).write_text("[" * depth + "]" * depth, encoding="utf-8")
        errors = inventories.check_tree(root)
        print(f"BAD deeply nested inventory: {[error[:200] for error in errors]}")
        self.assertTrue(
            any(
                error.startswith("inventory: cannot load tools/architecture/inventories.json")
                or error
                == (
                    "inventory schema: top-level fields must be exactly "
                    "schema_version, seam_types, violations, test_exceptions"
                )
                for error in errors
            ),
            errors,
        )

    def test_stale_foreign_type_rows_fail(self) -> None:
        views = (
            self.baseline_views()
            + "pub struct TokenView<'a> { pub id: &'a client::session::Token }\n"
        )
        root = self.fixture(
            views=views,
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("TokenView", "borrowed")),
            foreign_types=_foreign_data(
                _foreign("client::session::Token"), _foreign("client::session::Mode")
            ),
        )
        errors = inventories.check_tree(root)
        print(f"BAD stale foreign type rows: {errors}")
        self.assertEqual(
            errors,
            [
                "stale foreign type classification: client::session::Mode",
                "stale foreign type classification: client::session::Token",
            ],
        )

    def test_slot_surface_trait_is_not_a_value_seam_but_unions_fail_closed(self) -> None:
        seam_types = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        trait_root = self.fixture(
            views=self.baseline_views()
            + (
                "pub trait SlotSurface { type Io; fn released(&mut self); }\n"
                "struct HeadlessSurface;\n"
                "impl SlotSurface for HeadlessSurface {\n"
                "    type Io = ();\n"
                "    fn released(&mut self) {}\n"
                "}\n"
            ),
            frontend_lib="pub mod views;\npub use views::SlotSurface;\n",
            seam_types=seam_types,
        )
        trait_errors = inventories.check_tree(trait_root)
        union_root = self.fixture(
            views=self.baseline_views()
            + "pub union UnsupportedUnion { integer: u32, floating: f32 }\n",
            frontend_lib="pub mod views;\npub use views::UnsupportedUnion;\n",
            seam_types=seam_types,
        )
        union_errors = inventories.check_tree(union_root)
        print(f"GOOD non-value SlotSurface trait: {trait_errors}")
        print(f"BAD unsupported value union: {union_errors}")
        self.assertEqual(trait_errors, [])
        self.assertTrue(
            any("unsupported public seam type syntax (UNION)" in error for error in union_errors)
        )

    def test_candidate_cannot_select_parser_or_change_supported_edition(self) -> None:
        root = self.fixture(
            views=self.baseline_views(),
            seam_types=(("FleetCounts", "scalar"), ("FleetView", "borrowed")),
        )
        inventory_path = root / inventories.DATA_DIR_RELATIVE / inventories.INVENTORY_RELATIVE
        raw = json.loads(inventory_path.read_text(encoding="utf-8"))
        raw["parser_version"] = "attacker-selected"
        inventory_path.write_text(json.dumps(raw), encoding="utf-8")
        schema_errors = inventories.check_tree(root)
        self.assertTrue(any("top-level fields must be exactly" in error for error in schema_errors))

        raw.pop("parser_version")
        inventory_path.write_text(json.dumps(raw), encoding="utf-8")
        manifest = root / "crates" / "script" / "Cargo.toml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("2021", "2024"), encoding="utf-8")
        edition_errors = inventories.check_tree(root)
        self.assertTrue(any("parser adapter requires edition 2021" in error for error in edition_errors))



    def test_nested_use_trees_resolve_each_type_import(self) -> None:
        root = self.fixture(
            views=self.baseline_views()
            + "use api::{first::Count, second::{Width, Depth as D}};\n"
            + "#[derive(Clone, Copy)]\n"
            + "pub struct UsesNested { count: Count, width: Width, depth: D }\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("UsesNested", "scalar"),
            ),
            workspace_files={
                "crates/api/src/lib.rs": (
                    "pub mod first { #[derive(Clone, Copy)] pub struct Count(u64); }\n"
                    "pub mod second {\n"
                    "    #[derive(Clone, Copy)] pub struct Width(u64);\n"
                    "    #[derive(Clone, Copy)] pub struct Depth(u64);\n"
                    "}\n"
                )
            },
        )
        self.assertEqual(inventories.check_tree(root), [])

    def test_super_path_cannot_escape_workspace_crate_root(self) -> None:
        api_lib = "#[derive(Clone, Copy)]\npub struct Id(u64);\n"
        base = self.clean_fixture(
            views=self.baseline_views(),
            workspace_files={"crates/api/src/lib.rs": api_lib},
        )
        candidate = self.fixture(
            views=self.baseline_views() + "pub type EscapesRoot = super::super::api::Id;\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("EscapesRoot", "scalar"),
            ),
            workspace_files={"crates/api/src/lib.rs": api_lib},
        )
        self.assertEqual(inventories.check_tree(base), [])
        errors = inventories.check_tree(candidate)
        self.assertTrue(
            any("unresolved public seam field type super::super::api::Id" in error for error in errors),
            errors,
        )

    def test_public_glob_reexport_fails_closed(self) -> None:
        base = self.clean_fixture(views=self.baseline_views())
        candidate = self.clean_fixture(
            views=self.baseline_views(),
            frontend_lib="pub mod views;\npub use views::*;\n",
        )
        self.assertEqual(inventories.check_tree(base), [])
        errors = inventories.check_tree(candidate)
        self.assertTrue(
            any("public glob re-export is unsupported (views::*)" in error for error in errors),
            errors,
        )

    def test_binding_multiplicity_distinguishes_convergence_and_conflicts(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Uses", "scalar"))
        api_types = (
            "pub mod values { #[derive(Clone, Copy)] pub struct Scalar(u64); }\n"
            "pub mod owned { #[derive(Clone)] pub struct Payload(pub Vec<u8>); }\n"
            "pub mod plain { #[derive(Clone, Copy)] pub struct Payload(u64); }\n"
        )
        base = self.fixture(
            views=self.baseline_views() + "#[derive(Clone, Copy)]\npub struct Uses { value: u64 }\n",
            seam_types=base_seams,
            workspace_files={
                "crates/api/src/lib.rs": api_types
                + "#[derive(Clone, Copy)]\npub struct State { value: values::Scalar }\n"
            },
        )
        same_target = self.fixture(
            views=self.baseline_views() + "#[derive(Clone, Copy)]\npub struct Uses { value: api::State }\n",
            seam_types=base_seams,
            workspace_files={
                "crates/api/src/lib.rs": api_types
                + "#[cfg(feature = \"left\")]\n"
                "use crate::values::Scalar as Value;\n"
                "#[cfg(not(feature = \"left\"))]\n"
                "use crate::values::Scalar as Value;\n"
                "#[derive(Clone, Copy)]\npub struct State { value: Value }\n"
            },
        )
        self.assertEqual(inventories.check_tree(base), [])
        self.assertEqual(inventories.check_tree(same_target), [])

        conflict = self.fixture(
            views=self.baseline_views()
            + "#[cfg(feature = \"owned\")]\n"
            "use api::owned::Payload as Payload;\n"
            "#[cfg(not(feature = \"owned\"))]\n"
            "use api::plain::Payload as Payload;\n"
            "#[derive(Clone, Copy)]\npub struct Uses { value: Payload }\n",
            seam_types=base_seams,
            workspace_files={"crates/api/src/lib.rs": api_types},
        )
        conflict_errors = inventories.check_tree(conflict)
        self.assertTrue(
            any("ambiguous" in error and "Payload" in error for error in conflict_errors),
            conflict_errors,
        )

    def test_cfg_disjoint_local_import_collisions_refuse_d5b_and_d6(self) -> None:
        seam_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("AttackView", "borrowed"),
        )
        attack_prefix = (
            self.baseline_views()
            + "#[derive(Clone)]\npub struct AttackView {\n"
            "    pub label: &'static str,\n    pub payload: api::State,\n}\n"
        )
        cases = {
            "D5b std::num::Wrapping": (
                "#[derive(Clone, Copy)]\n"
                "pub struct State { pub label: &'static str, pub payload: u64 }\n",
                "#[cfg(feature = \"local\")]\n"
                "#[derive(Clone)]\npub struct Wrapping<T>(pub Vec<T>);\n"
                "#[cfg(not(feature = \"local\"))]\n"
                "use std::num::Wrapping;\n"
                "#[derive(Clone)]\n"
                "pub struct State { pub label: &'static str, pub payload: Wrapping<u64> }\n",
                "Wrapping",
            ),
            "D6 crate::inner::Payload": (
                "#[derive(Clone, Copy)]\n"
                "pub struct State { pub label: &'static str, pub payload: u64 }\n",
                "#[cfg(feature = \"local\")]\n"
                "#[derive(Clone)]\npub struct Payload(pub Vec<u8>);\n"
                "#[cfg(not(feature = \"local\"))]\n"
                "use crate::inner::Payload;\n"
                "pub mod inner { #[derive(Clone, Copy)] pub struct Payload(u64); }\n"
                "#[derive(Clone)]\n"
                "pub struct State { pub label: &'static str, pub payload: Payload }\n",
                "Payload",
            ),
        }
        for row, (base_api, candidate_api, collision) in cases.items():
            with self.subTest(row=row):
                base = self.fixture(
                    views=attack_prefix.replace("api::State", "u64"),
                    seam_types=seam_types,
                    workspace_files={"crates/api/src/lib.rs": base_api},
                )
                candidate = self.fixture(
                    views=attack_prefix,
                    seam_types=seam_types,
                    workspace_files={"crates/api/src/lib.rs": candidate_api},
                )
                self.assertEqual(inventories.check_tree(base), [])
                errors = inventories.check_tree(candidate)
                self.assertTrue(
                    any("ambiguous" in error and collision in error for error in errors),
                    errors,
                )

    def test_extern_crate_std_core_rebindings_refuse_k1_k3_k4_k5(self) -> None:
        seam_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("AttackView", "borrowed"),
        )
        std_view = (
            self.baseline_views()
            + "#[derive(Clone)]\npub struct AttackView {\n"
            "    pub label: &'static str,\n"
            "    pub payload: std::num::Wrapping<u64>,\n"
            "}\n"
        )
        core_view = std_view.replace("std::num", "core::num")
        wrapping_api = (
            "pub mod num {\n"
            "    #[derive(Clone)] pub struct Wrapping<T>(pub Vec<T>);\n"
            "}\n"
        )
        k4_base_api = "#[derive(Clone, Copy)]\npub struct State { payload: u64 }\n"
        k4_view = (
            self.baseline_views()
            + "#[derive(Clone)]\npub struct AttackView {\n"
            "    pub label: &'static str,\n    pub payload: api::State,\n}\n"
        )
        base = self.fixture(
            views=std_view,
            seam_types=seam_types,
            workspace_files={"crates/api/src/lib.rs": wrapping_api + k4_base_api},
        )
        self.assertEqual(inventories.check_tree(base), [])

        cases = {
            "K1 views extern crate api as std": (
                std_view.replace(
                    "#[derive(Clone)]\npub struct AttackView",
                    "extern crate api as std;\n#[derive(Clone)]\npub struct AttackView",
                ),
                "pub mod views;\n",
                wrapping_api + k4_base_api,
                "extern crate api as std shadows reserved crate name",
            ),
            "K3 crate-root extern crate api as std": (
                std_view,
                "extern crate api as std;\npub mod views;\n",
                wrapping_api + k4_base_api,
                "extern crate api as std shadows reserved crate name",
            ),
            "K5 views extern crate api as core": (
                core_view.replace(
                    "#[derive(Clone)]\npub struct AttackView",
                    "extern crate api as core;\n#[derive(Clone)]\npub struct AttackView",
                ),
                "pub mod views;\n",
                wrapping_api + k4_base_api,
                "extern crate api as core shadows reserved crate name",
            ),
            "K4 api extern crate self as std": (
                k4_view,
                "pub mod views;\n",
                "extern crate self as std;\n"
                + wrapping_api
                + "#[derive(Clone)]\npub struct State { payload: std::num::Wrapping<u64> }\n",
                "extern crate self as std shadows reserved crate name",
            ),
        }
        for row, (views, frontend_lib, api_lib, expected) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=views,
                    frontend_lib=frontend_lib,
                    seam_types=seam_types,
                    workspace_files={"crates/api/src/lib.rs": api_lib},
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_extern_crate_nonreserved_bindings_fail_closed(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        base = self.clean_fixture(views=self.baseline_views())
        cases = {
            "plain root binding": (
                self.baseline_views(),
                "extern crate api;\npub mod views;\n",
                "#[derive(Clone, Copy)]\npub struct Id(u64);\n",
                "extern crate binding api is unsupported",
                base_seams,
            ),
            "consulted private renamed binding": (
                "mod nested { extern crate api as helper; pub struct State { value: u64 } }\n"
                + self.baseline_views()
                + "pub struct Uses { value: nested::State }\n",
                "pub mod views;\n",
                "",
                "extern crate binding helper is unsupported",
                base_seams + (("Uses", "scalar"),),
            ),
            "workspace self alias": (
                self.baseline_views() + "pub type Uses = api::Id;\n",
                "pub mod views;\n",
                "extern crate self as helper;\n#[derive(Clone, Copy)]\npub struct Id(u64);\n",
                "extern crate binding helper is unsupported",
                base_seams + (("Uses", "scalar"),),
            ),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (views, frontend_lib, api_lib, expected, seams) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=views,
                    frontend_lib=frontend_lib,
                    seam_types=seams,
                    workspace_files={"crates/api/src/lib.rs": api_lib},
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)
        unconsulted = self.fixture(
            views="mod nested { extern crate api as helper; }\n" + self.baseline_views(),
            seam_types=base_seams,
        )
        self.assertEqual(inventories.check_tree(unconsulted), [])

    def test_type_namespace_nonvalues_generic_aliases_and_unnamed_items_fail_closed(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        base = self.clean_fixture(views=self.baseline_views())
        cases = {
            "generic alias": (
                self.baseline_views() + "pub type Alias<T> = Vec<T>;\n",
                base_seams + (("Alias", "scalar"),),
                "generic public type aliases are unsupported",
            ),
            "trait used as a field type": (
                self.baseline_views()
                + "pub trait Surface {}\n"
                "#[derive(Clone, Copy)]\npub struct Uses { value: Surface }\n",
                base_seams + (("Uses", "scalar"),),
                "public seam field path is a trait, not a value (Surface)",
            ),
            "const used as a field type": (
                self.baseline_views()
                + "pub const Surface: u8 = 0;\n"
                "#[derive(Clone, Copy)]\npub struct Uses { value: Surface }\n",
                base_seams + (("Uses", "scalar"),),
                "public seam field path is a value, not a type (Surface)",
            ),
            "static used as a field type": (
                self.baseline_views()
                + "pub static Surface: u8 = 0;\n"
                "#[derive(Clone, Copy)]\npub struct Uses { value: Surface }\n",
                base_seams + (("Uses", "scalar"),),
                "public seam field path is a value, not a type (Surface)",
            ),
            "function used as a field type": (
                self.baseline_views()
                + "pub fn Surface() {}\n"
                "#[derive(Clone, Copy)]\npub struct Uses { value: Surface }\n",
                base_seams + (("Uses", "scalar"),),
                "public seam field path is a value, not a type (Surface)",
            ),
            "module used as a field type": (
                self.baseline_views()
                + "pub mod Surface {}\n"
                "#[derive(Clone, Copy)]\npub struct Uses { value: Surface }\n",
                base_seams + (("Uses", "scalar"),),
                "field path resolves to module, not a type (Surface)",
            ),
            "unnamed public struct": (
                self.baseline_views() + "pub struct { value: u8 }\n",
                base_seams,
                "public struct has no supported name",
            ),
            "unnamed public enum": (
                self.baseline_views() + "pub enum { Value }\n",
                base_seams,
                "public enum has no supported name",
            ),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (views, seams, expected) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(views=views, seam_types=seams)
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)

        opaque = self.fixture(
            views=self.baseline_views()
            + "#[derive(Clone, Copy)]\npub struct Uses { value: api::Opaque }\n",
            seam_types=base_seams + (("Uses", "scalar"),),
            workspace_files={"crates/api/src/lib.rs": "extern type Opaque;\n"},
        )
        opaque_errors = inventories.check_tree(opaque)
        self.assertTrue(
            any("Opaque" in error and ("unresolved" in error or "unsupported" in error) for error in opaque_errors),
            opaque_errors,
        )

    def test_cfg_attr_binding_changes_are_refused_on_module_use_extern_and_macros(self) -> None:
        base = self.clean_fixture(views=self.baseline_views())
        cfg_attr = 'cfg_attr(feature = "probe", cfg(test))'
        path_attr = 'cfg_attr(feature = "probe", path = "alternate.rs")'
        cases = {
            "module path": (
                self.baseline_views(),
                f"#[{path_attr}]\npub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "module cfg": (
                self.baseline_views(),
                f"#[{cfg_attr}]\npub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "use path": (
                f"#[{path_attr}]\nuse std::num::Wrapping;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "use cfg": (
                f"#[{cfg_attr}]\nuse std::num::Wrapping;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "extern path": (
                f"#[{path_attr}]\nextern crate api as helper;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "extern cfg": (
                f"#[{cfg_attr}]\nextern crate api as helper;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "macro_use binding effect": (
                '#[cfg_attr(feature = "probe", macro_use)]\n'
                "extern crate api as helper;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter macro binding",
            ),
            "macro_export binding effect": (
                '#[cfg_attr(feature = "probe", macro_export)]\n'
                "macro_rules! generated { () => {}; }\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter macro binding",
            ),
            "inner module path effect": (
                self.baseline_views(),
                f"#![{path_attr}]\npub mod views;\n",
                "cfg_attr may not alter cfg or module path provenance",
            ),
            "nested macro binding effect": (
                '#[cfg_attr(feature = "probe", cfg_attr(feature = "nested", macro_use))]\n'
                "extern crate api as helper;\n" + self.baseline_views(),
                "pub mod views;\n",
                "cfg_attr may not alter macro binding",
            ),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (views, frontend_lib, expected) in cases.items():
            with self.subTest(row=row):
                candidate = self.clean_fixture(views=views, frontend_lib=frontend_lib)
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_opaque_nonpath_attribute_effects_are_not_blanket_refused(self) -> None:
        seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Opaque", "scalar"))
        declaration = "#[derive(Clone, Copy)]\npub struct Opaque(u64);\n"
        base = self.fixture(views=self.baseline_views() + declaration, seam_types=seams)
        cases = {
            "opaque item attribute": "#[opaque]\n" + declaration,
            "opaque cfg_attr effect": '#[cfg_attr(feature="x", opaque)]\n' + declaration,
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, source in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=self.baseline_views() + source,
                    seam_types=seams,
                )
                self.assertEqual(inventories.check_tree(candidate), [])

    def test_path_module_attributes_are_validated_and_confined(self) -> None:
        base = self.clean_fixture(
            views=self.baseline_views(),
            frontend_lib='#[path = "views.rs"]\npub mod views;\n',
        )
        self.assertEqual(inventories.check_tree(base), [])
        cases = {
            "source-root escape": (
                self.baseline_views(),
                'pub mod views;\n#[path = "../outside.rs"]\npub mod external;\n',
                "module path escapes frontend-core source",
            ),
            "duplicate path": (
                self.baseline_views(),
                '#[path = "views.rs"]\n#[path = "views.rs"]\npub mod views;\n',
                "duplicate module path attributes",
            ),
            "computed path": (
                self.baseline_views(),
                '#[path = concat!("views", ".rs")]\npub mod views;\n',
                "unsupported module path attribute",
            ),
        }
        for row, (views, frontend_lib, expected) in cases.items():
            with self.subTest(row=row):
                candidate = self.clean_fixture(views=views, frontend_lib=frontend_lib)
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_absolute_std_field_and_import_paths_resolve(self) -> None:
        base_seams = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("UsesAbsolute", "scalar"),
        )
        base = self.fixture(
            views=self.baseline_views() + "#[derive(Clone, Copy)]\npub struct UsesAbsolute { value: u64 }\n",
            seam_types=base_seams,
        )
        absolute_field = self.fixture(
            views=self.baseline_views()
            + "#[derive(Clone, Copy)]\npub struct UsesAbsolute { value: ::std::num::Wrapping<u64> }\n",
            seam_types=base_seams,
        )
        absolute_import = self.fixture(
            views=self.baseline_views()
            + "use ::std::num::Wrapping;\n"
            "#[derive(Clone, Copy)]\npub struct UsesAbsolute { value: Wrapping<u64> }\n",
            seam_types=base_seams,
        )
        self.assertEqual(inventories.check_tree(base), [])
        for row, candidate in {
            "absolute field": absolute_field,
            "absolute import": absolute_import,
        }.items():
            with self.subTest(row=row):
                self.assertEqual(inventories.check_tree(candidate), [])

    def test_absolute_paths_ignore_local_shadow_bindings(self) -> None:
        seams = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("AbsoluteView", "borrowed"),
        )
        api = "#[derive(Clone)] pub struct Payload(pub Vec<u8>);\n"
        shadow = "mod api { pub struct Payload(pub u64); }\n"
        for spelling in ("::api::Payload", "ExternalPayload"):
            with self.subTest(spelling=spelling):
                use = "use ::api::Payload as ExternalPayload;\n" if spelling == "ExternalPayload" else ""
                candidate = self.fixture(
                    views=self.baseline_views() + shadow + use
                    + f"#[derive(Clone)] pub struct AbsoluteView {{ pub label: &'static str, pub payload: {spelling} }}\n",
                    seam_types=seams,
                    workspace_files={"crates/api/src/lib.rs": api},
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(any("seam classification disagrees" in error for error in errors), errors)

        local_std = (
            "mod std { pub mod num { #[derive(Clone)] pub struct Wrapping<T>(pub Vec<T>); } }\n"
        )
        absolute_std = self.fixture(
            views=self.baseline_views() + local_std
            + "#[derive(Clone, Copy)] pub struct UsesStd { pub value: ::std::num::Wrapping<u64> }\n",
            seam_types=seams[:2] + (("UsesStd", "scalar"),),
        )
        self.assertEqual(inventories.check_tree(absolute_std), [])
        relative_std = self.fixture(
            views=self.baseline_views() + local_std
            + "#[derive(Clone)] pub struct UsesStd { pub value: std::num::Wrapping<u64> }\n",
            seam_types=seams[:2] + (("UsesStd", "scalar"),),
        )
        self.assertTrue(any("seam classification disagrees" in error
                            for error in inventories.check_tree(relative_std)))

    def test_consulted_generic_type_defaults_fail_closed(self) -> None:
        api_lib = (
            "#[derive(Clone)] pub struct Wrap<T = Vec<u8>> { pub label: &'static str, pub x: T }\n"
            "#[derive(Clone)] pub enum Choice<T = Vec<u8>> { Value(T) }\n"
            "#[derive(Clone)] pub struct Pair<T, U = Vec<u8>> { pub first: T, pub second: U }\n"
            "#[derive(Clone)] pub struct Unused<T = Vec<u8>> { value: T }\n"
            "#[derive(Clone)] pub struct Payload(pub Vec<u8>);\n"
            "pub struct OwnedDefault<T = Payload> { pub value: T }\n"
        )
        cases = {
            "bare struct": "api::Wrap",
            "enum default": "api::Choice",
            "partial arguments": "api::Pair<u64>",
            "workspace-owned default": "api::OwnedDefault",
        }
        for label, payload in cases.items():
            with self.subTest(case=label):
                errors = inventories.check_tree(
                    self.fixture(
                        views=self.baseline_views()
                        + f"#[derive(Clone)] pub struct AttackView {{ pub label: &'static str, pub payload: {payload} }}\n",
                        seam_types=(
                            ("FleetCounts", "scalar"),
                            ("FleetView", "borrowed"),
                            ("AttackView", "borrowed"),
                        ),
                        workspace_files={"crates/api/src/lib.rs": api_lib},
                    )
                )
                self.assertTrue(
                    any("generic type defaults are unsupported" in error for error in errors),
                    errors,
                )

        frontend_errors = inventories.check_tree(
            self.fixture(
                views=self.baseline_views(),
                frontend_lib=(
                    "pub mod views;\n"
                    "#[derive(Clone)] pub struct FrontDefault<T = Vec<u8>> { pub x: T }\n"
                ),
                frontend_files={
                    VIEWS_PATH: self.baseline_views()
                    + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: crate::FrontDefault }\n"
                },
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("AttackView", "borrowed"),
                ),
                additional_seam_types=(
                    _seam("FrontDefault", "borrowed", "crates/frontend-core/src/lib.rs"),
                ),
            )
        )
        self.assertTrue(
            any("generic type defaults are unsupported" in error for error in frontend_errors),
            frontend_errors,
        )

        direct_frontend = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone)] pub struct AttackView<T = Vec<u8>> { pub label: &'static str, pub x: T }\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("AttackView", "borrowed"),
                ),
            )
        )
        self.assertTrue(
            any("generic type defaults are unsupported" in error for error in direct_frontend),
            direct_frontend,
        )

        base = self.fixture(
            views=self.baseline_views()
            + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: api::Wrap }\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("AttackView", "borrowed"),
            ),
            workspace_files={
                "crates/api/src/lib.rs": "#[derive(Clone)] pub struct Wrap<T = u64> { pub x: T }\n"
            },
        )
        candidate = self.fixture(
            views=self.baseline_views()
            + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: api::Wrap }\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("AttackView", "borrowed"),
            ),
            workspace_files={"crates/api/src/lib.rs": api_lib},
        )
        candidate_errors = inventories.check_tree(candidate)
        self.assertTrue(
            any("generic type defaults are unsupported" in error for error in candidate_errors),
            candidate_errors,
        )

        unrelated = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone, Copy)] pub struct Unrelated { value: u64 }\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("Unrelated", "scalar"),
                ),
                workspace_files={"crates/api/src/lib.rs": api_lib},
            )
        )
        self.assertEqual(unrelated, [])

        alias_errors = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "pub type BareAlias = api::Wrap;\n"
                "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: BareAlias }\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("BareAlias", "owning"),
                    ("AttackView", "borrowed"),
                ),
                workspace_files={"crates/api/src/lib.rs": api_lib},
            )
        )
        self.assertTrue(
            any("generic type defaults are unsupported" in error for error in alias_errors),
            alias_errors,
        )

        explicit = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone, Copy)] pub struct AttackView { pub payload: api::Wrap<u64> }\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("AttackView", "borrowed"),
                ),
                workspace_files={
                    "crates/api/src/lib.rs": (
                        "#[derive(Clone, Copy)] pub struct Wrap<T: 'static> { pub x: &'static T }\n"
                    )
                },
            )
        )
        self.assertEqual(explicit, [])

    def test_frontend_glob_bindings_precede_crate_root_fallback(self) -> None:
        api = (
            "pub mod evil { #[derive(Clone)] pub struct Wrapping(pub Vec<u8>); }\n"
            "pub mod noise { #[derive(Clone, Copy)] pub struct Other(pub u64); }\n"
        )
        seam_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("AttackView", "borrowed"),
        )
        root_seam = (_seam("Wrapping", "borrowed", "crates/frontend-core/src/lib.rs"),)
        shadowed = self.fixture(
            views="use api::evil::*;\n" + self.baseline_views()
            + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: Wrapping }\n",
            frontend_lib=(
                "pub mod views;\n"
                "#[derive(Clone)] pub struct Wrapping { pub label: &'static str }\n"
            ),
            seam_types=seam_types,
            additional_seam_types=root_seam,
            workspace_files={"crates/api/src/lib.rs": api},
        )
        errors = inventories.check_tree(shadowed)
        self.assertTrue(any("seam classification disagrees" in error for error in errors), errors)

        unrelated_glob = self.fixture(
            views="use api::noise::*;\n" + self.baseline_views()
            + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: Wrapping }\n",
            frontend_lib=(
                "pub mod views;\n"
                "#[derive(Clone)] pub struct Wrapping { pub label: &'static str }\n"
            ),
            seam_types=seam_types,
            additional_seam_types=root_seam,
            workspace_files={"crates/api/src/lib.rs": api},
        )
        self.assertEqual(inventories.check_tree(unrelated_glob), [])

        multi_segment = self.fixture(
            views="use api::evil::*;\n"
            + self.baseline_views()
            + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: num::Wrapping }\n",
            frontend_lib=(
                "pub mod views;\n"
                "pub mod num { #[derive(Clone, Copy)] pub struct Wrapping { pub value: u64 } }\n"
            ),
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("AttackView", "borrowed"),
            ),
            additional_seam_types=(
                _seam("num::Wrapping", "borrowed", "crates/frontend-core/src/lib.rs"),
            ),
            workspace_files={
                "crates/api/src/lib.rs": (
                    "pub mod evil { pub mod num { "
                    "#[derive(Clone)] pub struct Wrapping(pub Vec<u8>); } }\n"
                )
            },
        )
        multi_errors = inventories.check_tree(multi_segment)
        self.assertTrue(
            any("seam classification disagrees" in error for error in multi_errors),
            multi_errors,
        )

    def test_std_leaf_exact_paths_refuse_glob_shadowing(self) -> None:
        api = (
            "pub mod std { pub mod num { "
            "#[derive(Clone)] pub struct Wrapping(pub Vec<u8>); } }\n"
        )
        imports = (
            "use api::{self, *};\n",
            "use api::{*, self};\n",
            "use api::*;\nuse api;\n",
        )
        for import_stmt in imports:
            with self.subTest(imports=import_stmt):
                errors = inventories.check_tree(
                    self.fixture(
                        views=import_stmt + self.baseline_views()
                        + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: std::num::Wrapping }\n",
                        seam_types=(
                            ("FleetCounts", "scalar"),
                            ("FleetView", "borrowed"),
                            ("AttackView", "borrowed"),
                        ),
                        workspace_files={"crates/api/src/lib.rs": api},
                    )
                )
                self.assertTrue(
                    any("seam field type std::num::Wrapping" in error for error in errors),
                    errors,
                )


        standard = inventories.check_tree(
            self.fixture(
                views=self.baseline_views()
                + "#[derive(Clone)] pub struct AttackView { pub label: &'static str, pub payload: std::num::Wrapping<u64> }\n",
                seam_types=(
                    ("FleetCounts", "scalar"),
                    ("FleetView", "borrowed"),
                    ("AttackView", "borrowed"),
                ),
            )
        )
        self.assertEqual(standard, [])

    def test_glob_import_shadows_multisegment_std_path_or_refuses_unknown(self) -> None:
        seams = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("GlobView", "borrowed"),
        )
        body = self.baseline_views() + (
            "pub mod evil { pub mod std { pub mod num {\n"
            "    #[derive(Clone)] pub struct Wrapping(pub Vec<u8>);\n"
            "} } }\n"
            "use self::evil::*;\n"
            "#[derive(Clone)] pub struct GlobView { pub label: &'static str,"
            " pub payload: std::num::Wrapping }\n"
        )
        candidate = self.fixture(
            views=body,
            seam_types=seams + (("views::evil::std::num::Wrapping", "owning"),),
        )
        errors = inventories.check_tree(candidate)
        self.assertTrue(any("seam classification disagrees" in error for error in errors), errors)
        unknown = self.fixture(
            views=self.baseline_views()
            + "use absent::*;\n"
            "#[derive(Clone)] pub struct GlobView { pub label: &'static str, pub payload: Option<u64> }\n",
            seam_types=seams,
        )
        self.assertTrue(any("ambiguous cfg/alternative seam field type" in error
                            for error in inventories.check_tree(unknown)))

    def test_macro_generated_workspace_items_fail_closed(self) -> None:
        seam_types = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("AttackView", "borrowed"),
        )
        base_api = "#[derive(Clone, Copy)]\npub struct State { payload: u64 }\n"
        base_views = (
            self.baseline_views()
            + "#[derive(Clone)]\npub struct AttackView {\n"
            "    pub label: &'static str,\n    pub payload: u64,\n}\n"
        )
        base = self.fixture(
            views=base_views,
            seam_types=seam_types,
            workspace_files={"crates/api/src/lib.rs": base_api},
        )
        cases = {
            "macro definition": (
                "macro_rules! make_type {\n"
                "    () => { pub struct Generated(pub Vec<u8>); };\n"
                "}\n"
                + base_api,
                "item-generating macro syntax is unsupported",
            ),
            "item invocation": (
                "make_type!();\n" + base_api,
                "item macro invocation is unsupported",
            ),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (api_lib, expected) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=base_views.replace("payload: u64", "payload: api::State"),
                    seam_types=seam_types,
                    workspace_files={"crates/api/src/lib.rs": api_lib},
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(
                    any(expected in error and "consulted for a seam field type" in error for error in errors),
                    errors,
                )

    def test_direct_macro_binding_attributes_refuse(self) -> None:
        base = self.clean_fixture(views=self.baseline_views())
        self.assertEqual(inventories.check_tree(base), [])
        cases = {
            "macro_use module": "#[macro_use]\nmod hidden {}\n",
            "macro_export definition": "#[macro_export]\nmacro_rules! generated { () => {}; }\n",
        }
        for row, source in cases.items():
            with self.subTest(row=row):
                candidate = self.clean_fixture(views=self.baseline_views() + source)
                expected = "unsupported macro binding attribute"
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)
        unrelated = self.clean_fixture(views=self.baseline_views())
        script_macro = unrelated / "crates/script/src/quester/compile.rs"
        script_macro.parent.mkdir(parents=True, exist_ok=True)
        script_macro.write_text(
            "#[macro_export]\nmacro_rules! step { () => {}; }\n",
            encoding="utf-8",
        )
        self.assertEqual(inventories.check_tree(unrelated), [])

    def test_unsupported_field_type_syntax_refuses_macro_and_pointer_forms(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"), ("Uses", "scalar"))
        base = self.clean_fixture(views=self.baseline_views())
        cases = {
            "type macro": ("pub struct Uses { value: type_macro!() }\n", "MACRO_TYPE"),
            "dyn trait": (
                "pub trait Marker {}\npub struct Uses { value: dyn Marker }\n",
                "DYN_TRAIT_TYPE",
            ),
            "impl trait": (
                "pub trait Marker {}\npub struct Uses { value: impl Marker }\n",
                "IMPL_TRAIT_TYPE",
            ),
            "function pointer": ("pub struct Uses { value: fn(u8) -> u8 }\n", "FN_PTR_TYPE"),
            "function pointer inside Option": (
                "pub struct Uses { value: Option<fn(u8) -> u8> }\n",
                "FN_PTR_TYPE",
            ),
            "callback function pointer": (
                "pub struct Uses { callback: fn() }\n",
                "FN_PTR_TYPE",
            ),
            "callback pointer inside Option": (
                "pub struct Uses { callback: Option<fn()> }\n",
                "FN_PTR_TYPE",
            ),
            "callback pointer inside Vec": (
                "pub struct Uses { callback: Vec<fn()> }\n",
                "FN_PTR_TYPE",
            ),
            "callback pointer behind a reference": (
                "pub struct Uses { callback: &'static fn() }\n",
                "FN_PTR_TYPE",
            ),
            "raw pointer": ("pub struct Uses { value: *const u8 }\n", "PTR_TYPE"),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (source, syntax) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=self.baseline_views() + source,
                    seam_types=base_seams,
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(
                    any(f"unsupported field type syntax ({syntax})" in error for error in errors),
                    errors,
                )

    def test_prelude_configuration_attributes_fail_closed_in_inner_and_outer_positions(self) -> None:
        base = self.clean_fixture(views=self.baseline_views())
        attributes = ("no_implicit_prelude", "no_std", "no_core", "prelude_import")
        cases: dict[str, tuple[str, str]] = {}
        for attribute in attributes:
            cases[f"inner {attribute}"] = (
                "#!["
                + attribute
                + "]\n"
                + self.baseline_views(),
                "pub mod views;\n",
            )
            cases[f"outer {attribute}"] = (
                self.baseline_views() + f"\n#[{attribute}]\nmod hidden {{}}\n",
                "pub mod views;\n",
            )
        cases["crate-root no_std"] = (
            self.baseline_views(),
            "#![no_std]\npub mod views;\n",
        )
        cases["conditional no_std"] = (
            '#[cfg_attr(feature = "no-std", no_std)]\n' + self.baseline_views(),
            "pub mod views;\n",
        )
        cases["inner conditional no_std"] = (
            self.baseline_views(),
            '#![cfg_attr(feature = "no-std", no_std)]\npub mod views;\n',
        )
        self.assertEqual(inventories.check_tree(base), [])
        for row, (views, frontend_lib) in cases.items():
            with self.subTest(row=row):
                candidate = self.clean_fixture(views=views, frontend_lib=frontend_lib)
                errors = inventories.check_tree(candidate)
                self.assertTrue(
                    any("unsupported Rust prelude configuration" in error for error in errors),
                    errors,
                )
        unrelated_predicate = self.clean_fixture(
            views=self.baseline_views(),
            frontend_lib='#[cfg_attr(no_std, doc = "not a binding")]\npub mod views;\n',
        )
        self.assertEqual(inventories.check_tree(unrelated_predicate), [])

    def test_generic_const_self_and_associated_type_bindings(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        base = self.clean_fixture(views=self.baseline_views())
        cases = {
            "bare generic parameter": (
                "#[derive(Clone, Copy)]\npub struct Uses<T> { value: T }\n",
                "unresolved generic field ownership (T)",
                (("Uses", "scalar"),),
            ),
            "generic associated path": (
                "pub trait HasItem { type Item; }\n"
                "#[derive(Clone)]\npub struct Uses<T: HasItem> { value: T::Item }\n",
                "unresolved generic field ownership (T)",
                (("Uses", "scalar"),),
            ),
            "generic inside Option": (
                "#[derive(Clone, Copy)]\npub struct Uses<T> { value: Option<T> }\n",
                "unresolved generic field ownership (T)",
                (("Uses", "scalar"),),
            ),
            "Self field": (
                "pub struct UsesSelf { value: Self }\n",
                "unsupported Self/associated seam field type",
                (("UsesSelf", "scalar"),),
            ),
            "Self inside generic argument": (
                "pub struct UsesSelf { value: Option<Self> }\n",
                "unsupported Self/associated seam field type",
                (("UsesSelf", "scalar"),),
            ),
            "Self associated path": (
                "pub struct UsesSelf { value: Self::Item }\n",
                "unsupported Self/associated seam field type",
                (("UsesSelf", "scalar"),),
            ),
            "qualified associated projection": (
                "pub trait HasItem { type Item; }\n"
                "#[derive(Clone)]\n"
                "pub struct Uses<T: HasItem> { value: <T as HasItem>::Item }\n",
                "unsupported qualified associated field type",
                (("Uses", "scalar"),),
            ),
        }
        self.assertEqual(inventories.check_tree(base), [])
        for row, (source, expected, extra_seams) in cases.items():
            with self.subTest(row=row):
                candidate = self.fixture(
                    views=self.baseline_views() + source,
                    seam_types=base_seams + extra_seams,
                )
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(expected in error for error in errors), errors)

        fixed_seams = base_seams + (("Fixed", "scalar"), ("UsesConst", "scalar"))
        fixed_head = (
            self.baseline_views()
            + "#[derive(Clone, Copy)]\npub struct Fixed<const N: usize> { bytes: [u8; N] }\n"
        )
        fixed_base = self.fixture(
            views=fixed_head + "#[derive(Clone, Copy)]\npub struct UsesConst { fixed: Fixed<4> }\n",
            seam_types=fixed_seams,
        )
        fixed_braced = self.fixture(
            views=fixed_head + "#[derive(Clone, Copy)]\npub struct UsesConst { fixed: Fixed<{4}> }\n",
            seam_types=fixed_seams,
        )
        self.assertEqual(inventories.check_tree(fixed_base), [])
        self.assertEqual(inventories.check_tree(fixed_braced), [])

    def test_restricted_visibility_does_not_create_an_exported_seam(self) -> None:
        base_seams = (("FleetCounts", "scalar"), ("FleetView", "borrowed"))
        public = self.fixture(
            views=self.baseline_views() + "#[derive(Clone, Copy)]\npub struct Visible(u64);\n",
            seam_types=base_seams + (("Visible", "scalar"),),
        )
        self.assertEqual(inventories.check_tree(public), [])
        for visibility in ("pub(crate)", "pub(super)", "pub(in crate::views)"):
            with self.subTest(visibility=visibility):
                restricted = self.fixture(
                    views=self.baseline_views()
                    + f"#[derive(Clone, Copy)]\n{visibility} struct Restricted(u64);\n",
                    seam_types=base_seams + (("Restricted", "scalar"),),
                )
                errors = inventories.check_tree(restricted)
                self.assertTrue(
                    any(f"stale seam type classification: {VIEWS_PATH}::Restricted" in error for error in errors),
                    errors,
                )

    def test_raw_identifier_type_and_import_names_normalize_consistently(self) -> None:
        root = self.fixture(
            views=self.baseline_views()
            + "#[derive(Clone, Copy)]\npub struct r#widget(u64);\n"
            "use self::r#widget as r#renamed_widget;\n"
            "pub type UsesRawAlias = r#renamed_widget;\n",
            seam_types=(
                ("FleetCounts", "scalar"),
                ("FleetView", "borrowed"),
                ("widget", "scalar"),
                ("UsesRawAlias", "scalar"),
            ),
        )
        self.assertEqual(inventories.check_tree(root), [])

    def test_local_std_module_and_import_alias_paths_resolve(self) -> None:
        base_seams = (
            ("FleetCounts", "scalar"),
            ("FleetView", "borrowed"),
            ("UsesStd", "scalar"),
        )
        api_lib = "pub mod num { #[derive(Clone, Copy)] pub struct Wrapping(u64); }\n"
        base = self.fixture(
            views=self.baseline_views() + "#[derive(Clone, Copy)]\npub struct UsesStd { value: u64 }\n",
            seam_types=base_seams,
            workspace_files={"crates/api/src/lib.rs": api_lib},
        )
        import_alias = self.fixture(
            views=self.baseline_views()
            + "use api as api_alias;\n"
            "#[derive(Clone, Copy)]\npub struct UsesStd { value: api_alias::num::Wrapping }\n",
            seam_types=base_seams,
            workspace_files={"crates/api/src/lib.rs": api_lib},
        )
        self.assertEqual(inventories.check_tree(base), [])
        self.assertEqual(inventories.check_tree(import_alias), [])

        local_module = self.fixture(
            views=self.baseline_views()
            + "pub mod std {\n"
            "    pub mod num {\n"
            "        #[derive(Clone, Copy)] pub struct Wrapping(u64);\n"
            "    }\n"
            "}\n"
            "#[derive(Clone, Copy)]\npub struct UsesStd { value: std::num::Wrapping }\n",
            seam_types=base_seams + (("views::std::num::Wrapping", "scalar"),),
        )
        self.assertEqual(inventories.check_tree(local_module), [])

    def test_reserved_crate_name_import_aliases_refuse(self) -> None:
        base = self.clean_fixture(views=self.baseline_views())
        self.assertEqual(inventories.check_tree(base), [])
        for name in ("std", "core", "alloc", "proc_macro", "test"):
            with self.subTest(name=name):
                candidate = self.clean_fixture(
                    views=f"use api as {name};\n" + self.baseline_views()
                )
                message = f"import api as {name} shadows reserved crate name"
                errors = inventories.check_tree(candidate)
                self.assertTrue(any(message in error for error in errors), errors)

if __name__ == "__main__":
    unittest.main()
