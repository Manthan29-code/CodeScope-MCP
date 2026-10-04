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
        res = search(str(self.root_path), query="hello_world", search_type="content", file_pattern="*.py")
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/app.py")
        # Ensure .js is not included
        for match in res.matches:
            self.assertTrue(match.file_path.endswith(".py"))

    def test_search_regex_content_capture(self):
        res = search(str(self.root_path), query=r"def\s+([a-z_]+)\(\):", search_type="content", regex=True)
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/app.py")
        self.assertEqual(res.matches[0].line_number, 1)

    def test_search_regex_filename_match(self):
        res = search(str(self.root_path), query=r"^src/.*\.py$", search_type="filename", regex=True)
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].file_path, "src/app.py")

    def test_search_literal_mode_handles_dots(self):
        # Create a file with literal dots
        (self.root_path / "src" / "literal.txt").write_text("a.b\naxb\n")
        res = search(str(self.root_path), query="a.b", search_type="content", regex=False)
        # Should only match line 1 with 'a.b', not 'axb'
        self.assertEqual(len(res.matches), 1)
        self.assertEqual(res.matches[0].line_number, 1)

    def test_search_invalid_regex_raises_error(self):
        from core.regex_utils import PatternError
        with self.assertRaises(PatternError):
            search(str(self.root_path), query="(", search_type="content", regex=True)

    def test_iter_searchable_files(self):
        from services.search_service import iter_searchable_files
        files = list(iter_searchable_files(self.root_path, file_pattern="*.py"))
        rel_files = [f.relative_to(self.root_path).as_posix() for f in files]
        self.assertIn("src/app.py", rel_files)
        self.assertNotIn("src/index.js", rel_files)

        sub_files = list(iter_searchable_files(self.root_path, subpath="src"))
        self.assertEqual(len(sub_files), 2)


if __name__ == "__main__":
    unittest.main()

