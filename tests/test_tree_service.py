import unittest
from pathlib import Path
import tempfile
from services.tree_service import build_tree


class TestTreeService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        
        (self.root_path / "file1.txt").write_text("content")
        sub = self.root_path / "subdir"
        sub.mkdir()
        (sub / "file2.txt").write_text("content2")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_tree_structure(self):
        out = build_tree(str(self.root_path))
        self.assertEqual(out.total_files, 2)
        self.assertGreaterEqual(out.total_directories, 1)
        self.assertEqual(out.tree.type, "directory")


if __name__ == "__main__":
    unittest.main()
