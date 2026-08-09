import unittest
from pathlib import Path
import tempfile
from core.ignore_manager import IgnoreManager


class TestIgnoreManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        
        # Create a mock .gitignore
        gitignore = self.root_path / ".gitignore"
        gitignore.write_text("*.log\ncustom_build/\n")

    def tearDown(self):
        self.temp_dir.cleanup()
        IgnoreManager.clear_cache()

    def test_default_ignores(self):
        mgr = IgnoreManager.get_for_project(self.root_path)
        self.assertTrue(mgr.is_ignored("node_modules/index.js"))
        self.assertTrue(mgr.is_ignored("venv/lib/python3.10"))
        self.assertTrue(mgr.is_ignored(".git/config"))

    def test_custom_gitignore_rules(self):
        mgr = IgnoreManager.get_for_project(self.root_path)
        self.assertTrue(mgr.is_ignored("app.log"))
        self.assertTrue(mgr.is_ignored("custom_build/output.bin", is_dir=False))
        self.assertFalse(mgr.is_ignored("src/main.py"))


if __name__ == "__main__":
    unittest.main()
