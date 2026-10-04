import unittest
from pathlib import Path
import tempfile
from core.path_security import resolve_and_verify


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


if __name__ == "__main__":
    unittest.main()
