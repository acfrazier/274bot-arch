"""Behavioral tests for remote-owned source-path ownership rules."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import ownership as subject


def rules_dir(root: Path) -> Path:
    return root / ".architecture-rules"


def write_map(root: Path, entries: list[tuple[str, str]]) -> None:
    directory = rules_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "contract": "test",
        "paths": [{"path": path, "owner": owner} for path, owner in entries],
    }
    (directory / "ownership.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_raw_map(root: Path, text: str) -> None:
    directory = rules_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ownership.json").write_text(text, encoding="utf-8")


def make_source(root: Path, relative: str, content: str = "test\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def check_tree(root: Path) -> list[str]:
    previous_rules = subject.RULES_DIR
    subject.RULES_DIR = rules_dir(root)
    try:
        return subject.check_tree(root)
    finally:
        subject.RULES_DIR = previous_rules


def test_missing_source_ownership() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/host-play/src/play_login.rs", "a\n")
        make_source(root, "crates/host-play/src/play_login_tests.rs", "b\n")
        write_map(root, [("crates/host-play/src/play_login.rs", "T1")])
        errors = check_tree(root)
        assert any("missing ownership" in error and "play_login_tests.rs" in error for error in errors), errors
        assert not any("stale ownership" in error for error in errors), errors


def test_stale_row() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_map(root, [("crates/api/build.rs", "T2"), ("crates/api/src/gone.rs", "T2")])
        errors = check_tree(root)
        assert any("stale ownership" in error and "gone.rs" in error for error in errors), errors


def test_duplicate_path_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_raw_map(
            root,
            json.dumps(
                {
                    "version": 1,
                    "contract": "test",
                    "paths": [
                        {"path": "crates/api/build.rs", "owner": "T2"},
                        {"path": "crates/api/build.rs", "owner": "T2"},
                    ],
                }
            ),
        )
        assert any("duplicate path" in error for error in check_tree(root))


def test_unknown_field_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_raw_map(
            root,
            json.dumps(
                {
                    "version": 1,
                    "contract": "test",
                    "extra": True,
                    "paths": [{"path": "crates/api/build.rs", "owner": "T2"}],
                }
            ),
        )
        assert any("unknown field" in error for error in check_tree(root))


def test_unknown_owner_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_map(root, [("crates/api/build.rs", "T9")])
        assert any("unknown owner" in error for error in check_tree(root))


def test_path_escape_and_wildcard_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_raw_map(
            root,
            json.dumps(
                {
                    "version": 1,
                    "contract": "test",
                    "paths": [
                        {"path": "../outside.rs", "owner": "T1"},
                        {"path": "crates/api/*.rs", "owner": "T2"},
                    ],
                }
            ),
        )
        errors = check_tree(root)
        assert len([error for error in errors if "invalid path" in error]) == 2, errors


def test_clean_tree() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_map(root, [("crates/api/build.rs", "T2")])
        assert check_tree(root) == []


def test_duplicate_object_key_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_raw_map(root, '{"version":1,"version":1,"contract":"test","paths":[]}')
        assert any("duplicate" in error for error in check_tree(root))
        write_map(root, [])
        assert check_tree(root) == []


def test_source_symlinks_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "root"
        outside = Path(temporary) / "outside"
        make_source(outside, "hidden.rs")
        root.mkdir()
        write_map(root, [])
        (root / "linked").symlink_to(outside, target_is_directory=True)
        assert any("source symlink" in error for error in check_tree(root))
        (root / "linked").unlink()
        (root / "linked.rs").symlink_to(outside / "hidden.rs")
        assert any("source symlink" in error for error in check_tree(root))
        (root / "linked.rs").unlink()
        assert check_tree(root) == []


def test_candidate_ownership_file_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        make_source(root, "crates/api/build.rs")
        write_map(root, [("crates/api/build.rs", "T2")])
        candidate_map = root / "tools/architecture/ownership.json"
        candidate_map.parent.mkdir(parents=True)
        candidate_map.write_text("not checker rules", encoding="utf-8")
        assert check_tree(root) == []


def load_tests(
    _loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    for test in (
        test_missing_source_ownership,
        test_stale_row,
        test_duplicate_path_rejected,
        test_unknown_field_rejected,
        test_unknown_owner_rejected,
        test_path_escape_and_wildcard_rejected,
        test_clean_tree,
        test_duplicate_object_key_rejected,
        test_source_symlinks_rejected,
        test_candidate_ownership_file_is_ignored,
    ):
        standard_tests.addTest(unittest.FunctionTestCase(test))
    return standard_tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
