import unittest
from pathlib import Path
import tempfile
import config
from services.tree_service import build_tree


class TestTreeService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        self.orig_read_roots = list(config.READ_ALLOWED_ROOTS)
        config.READ_ALLOWED_ROOTS = [str(self.root_path)]
        
        (self.root_path / "file1.txt").write_text("content")
        sub = self.root_path / "subdir"
        sub.mkdir()
        (sub / "file2.txt").write_text("content2")

    def tearDown(self):
        config.READ_ALLOWED_ROOTS = self.orig_read_roots
        self.temp_dir.cleanup()

    def test_build_tree_structure(self):
        out = build_tree(str(self.root_path))
        self.assertEqual(out.total_files, 2)
        self.assertGreaterEqual(out.total_directories, 1)
        self.assertEqual(out.tree.type, "directory")

    def test_tree_unauthorized_root_raises(self):
        other_temp = tempfile.TemporaryDirectory()
        try:
            other_path = Path(other_temp.name).resolve()
            (other_path / "secret.txt").write_text("secret")
            from core.path_security import ReadRootNotAllowedError
            with self.assertRaises(ReadRootNotAllowedError):
                build_tree(str(other_path))
        finally:
            other_temp.cleanup()


if __name__ == "__main__":
    unittest.main()
