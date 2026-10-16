"""Exact input identity does not depend on Cargo workspace interpretation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import vendor_manifests as pin


class VendoredManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vendor-manifest-pin-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tree = self.root / pin.TREE
        self.tree.mkdir(parents=True)
        self.manifest = self.tree / "Cargo.toml"
        self.manifest.write_bytes(b'[workspace]\r\nmembers = []\r\n')
        self.protected = self.root / pin.PIN
        self.protected.write_text(pin.pin_json(self.root), encoding="utf-8")

    def test_digest_uses_sorted_paths_lengths_and_exact_bytes(self):
        manifests = {"z/Cargo.toml": "z\r\n", "Cargo.toml": "a\n"}
        expected = hashlib.sha256()
        for name in ("Cargo.toml", "z/Cargo.toml"):
            for value in (name.encode(), manifests[name].encode()):
                expected.update(len(value).to_bytes(8, "big"))
                expected.update(value)
        self.assertEqual(pin.manifest_digest(manifests), expected.hexdigest())
        self.assertEqual(pin.snapshot(self.root)["Cargo.toml"], '[workspace]\r\nmembers = []\r\n')
        pin.check_pin(self.root, self.protected)
        self.manifest.write_bytes(b'[workspace]\nmembers = []\n')
        with self.assertRaisesRegex(ValueError, r"Cargo.toml \(changed\).+operator commit"):
            pin.check_pin(self.root, self.protected)

    def test_scan_includes_hidden_and_normally_ignored_directories(self):
        for directory in ("node_modules/probe", ".hidden", "target/fixture"):
            manifest = self.tree / directory / "Cargo.toml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("[workspace]\n", encoding="utf-8")
        self.assertEqual(len(pin.snapshot(self.root)), 4)
        with self.assertRaisesRegex(ValueError, "node_modules/probe/Cargo.toml"):
            pin.check_pin(self.root, self.protected)

    def test_nonmanifest_change_does_not_change_identity(self):
        (self.tree / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.98.1"\n', encoding="utf-8")
        pin.check_pin(self.root, self.protected)

    def test_missing_tree_names_removed_manifests(self):
        self.manifest.unlink()
        self.tree.rmdir()
        with self.assertRaisesRegex(ValueError, r"Cargo.toml \(removed\)"):
            pin.check_pin(self.root, self.protected)

    def test_manifest_and_directory_symlinks_are_refused(self):
        content = self.manifest.read_bytes()
        self.manifest.unlink()
        target = self.root / "other.toml"
        target.write_bytes(content)
        self.manifest.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "manifest must not be a symlink"):
            pin.check_pin(self.root, self.protected)
        self.manifest.unlink()
        self.manifest.write_bytes(content)
        (self.tree / "nested").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "directory must not be a symlink"):
            pin.check_pin(self.root, self.protected)

    def test_changed_pin_content_needs_matching_digest(self):
        raw = json.loads(self.protected.read_text())
        raw["manifests"]["Cargo.toml"] += "# changed\n"
        self.protected.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "digest disagrees"):
            pin.check_pin(self.root, self.protected)

    def test_duplicate_pin_keys_are_refused(self):
        self.protected.write_text('{"sha256": "a", "sha256": "b", "manifests": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate vendored manifest pin key"):
            pin.check_pin(self.root, self.protected)

    def test_pin_refuses_all_dependency_inheritance_spellings(self):
        for table in ("dependencies", "dev-dependencies", "dev_dependencies",
                      "build-dependencies", "build_dependencies"):
            for prefix in ("", "target.'cfg(unix)'."):
                with self.subTest(table=prefix + table):
                    content = '[package]\nname = "probe"\nversion = "0.1.0"\n'
                    content += f'[{prefix}{table}]\napiish = {{ workspace = true }}\n'
                    with self.assertRaisesRegex(ValueError, "dependency inheritance is forbidden"):
                        pin.validate_manifests({"crates/probe/Cargo.toml": content})


if __name__ == "__main__":
    unittest.main()
