import unittest
from pathlib import Path
import tempfile
from services.search_service import search


class TestSearchService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        
        src_dir = self.root_path / "src"
        src_dir.mkdir()
        
        self.py_file = src_dir / "app.py"
        self.py_file.write_text("def hello_world():\n    print('Hello World')\n")
        
        self.js_file = src_dir / "index.js"
        self.js_file.write_text("console.log('Hello JS');\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_search_content_match(self):
        res = search(str(self.root_path), query="hello_world", search_type="content")
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/app.py")
        self.assertEqual(res.matches[0].line_number, 1)

    def test_search_filename_match(self):
        res = search(str(self.root_path), query="index", search_type="filename")
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/index.js")

    def test_search_file_pattern_filter(self):
        res = search(str(self.root_path), query="Hello", search_type="content", file_pattern="*.py")
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/app.py")


if __name__ == "__main__":
    unittest.main()
