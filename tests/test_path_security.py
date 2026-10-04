import os
import unittest
from pathlib import Path
import tempfile
import pytest
from core.path_security import resolve_and_verify, resolve_for_write, is_within
import config


class TestPathSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        self.test_file = self.root_path / "hello.txt"
        self.test_file.write_text("hello world")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_contained_path(self):
        resolved = resolve_and_verify(str(self.root_path), "hello.txt")
        self.assertEqual(resolved, self.test_file)

    def test_path_traversal_attack(self):
        with self.assertRaises(ValueError):
            resolve_and_verify(str(self.root_path), "../outside.txt")

    def test_empty_root_strict(self):
        with self.assertRaises(ValueError):
            resolve_and_verify("", "hello.txt", fallback_to_default=False)

    def test_nonexistent_root_strict(self):
        with self.assertRaises(ValueError):
            resolve_and_verify(str(self.root_path / "nonexistent"), "hello.txt", fallback_to_default=False)

    def test_nonexistent_root_fallback(self):
        # Should fallback to server DEFAULT_PROJECT_PATH without crashing
        resolved = resolve_and_verify("/fake/remote/working_dir", "", fallback_to_default=True)
        self.assertTrue(resolved.exists())


class TestResolveForWrite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        (self.root_path / "src").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_file_in_existing_dir(self):
        target = resolve_for_write(self.root_path, "src/new.py")
        self.assertEqual(target, (self.root_path / "src" / "new.py").resolve())
        self.assertFalse(target.exists())

    def test_missing_parent_without_create_parents_fails(self):
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "nested/deep/file.py", create_parents=False)

    def test_missing_parent_with_create_parents_succeeds_without_creating(self):
        target = resolve_for_write(self.root_path, "nested/deep/file.py", create_parents=True)
        self.assertEqual(target, (self.root_path / "nested" / "deep" / "file.py").resolve())
        # Target and parent must not have been created yet
        self.assertFalse(target.parent.exists())
        self.assertFalse(target.exists())

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "../outside.txt")
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "src/../../outside.txt")

    def test_absolute_paths_rejected(self):
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "/etc/shadow")
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "C:\\Windows\\system.ini")

    def test_empty_string_and_root_itself_rejected(self):
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "")
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, ".")
        with self.assertRaises(ValueError):
            resolve_for_write(self.root_path, "./")

    def test_sibling_prefix_trap_rejected(self):
        proj_evil = self.root_path.parent / (self.root_path.name + "-evil")
        proj_evil.mkdir(exist_ok=True)
        try:
            with self.assertRaises(ValueError):
                resolve_for_write(self.root_path, f"../{proj_evil.name}/attack.txt")
        finally:
            if proj_evil.exists():
                proj_evil.rmdir()

    def test_reserved_device_names_rejected(self):
        reserved = ["CON.txt", "nul", "aux.py", "src/COM1", "PRN", "LPT2.dat"]
        for name in reserved:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    resolve_for_write(self.root_path, name)

    def test_trailing_dot_and_space_rejected(self):
        bad_names = ["src/a.", "src/b ", "test. ", "test.."]
        for name in bad_names:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    resolve_for_write(self.root_path, name)

    def test_symlink_parent_pointing_outside(self):
        if not hasattr(os, "symlink"):
            self.skipTest("Symlinks not supported on this platform")
        outside_dir = self.root_path.parent / "outside_dir"
        outside_dir.mkdir(exist_ok=True)
        link = self.root_path / "link_dir"
        try:
            try:
                os.symlink(str(outside_dir), str(link), target_is_directory=True)
            except OSError:
                self.skipTest("Symlink creation failed due to system permissions")

            with self.assertRaises(PermissionError):
                resolve_for_write(self.root_path, "link_dir/file.txt")
        finally:
            if link.is_symlink():
                link.unlink()
            if outside_dir.exists():
                outside_dir.rmdir()

    def test_is_within_helper(self):
        child = self.root_path / "src" / "app.py"
        self.assertTrue(is_within(self.root_path, child))
        self.assertFalse(is_within(self.root_path, self.root_path.parent))
        self.assertFalse(is_within(self.root_path, Path("/some/other/path")))


if __name__ == "__main__":
    unittest.main()
