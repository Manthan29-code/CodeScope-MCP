import unittest
from pathlib import Path
import tempfile
from services.read_service import read_one, read_many


class TestReadService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()
        
        # Create test text file
        self.file1 = self.root_path / "file1.txt"
        self.file1.write_text("line1\nline2\nline3\nline4\nline5\n")
        
        # Create binary file
        self.bin_file = self.root_path / "data.bin"
        self.bin_file.write_bytes(b"\x00\x01\x02\x03\x04")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_one_success(self):
        res = read_one(str(self.root_path), "file1.txt", offset=0, limit=3)
        self.assertIsNone(res.error)
        self.assertEqual(res.start_line, 1)
        self.assertEqual(res.end_line, 3)
        self.assertEqual(res.total_lines, 5)
        self.assertTrue(res.truncated)
        self.assertIn("line1\nline2\nline3", res.content)

    def test_read_binary_refusal(self):
        res = read_one(str(self.root_path), "data.bin")
        self.assertTrue(res.is_binary)
        self.assertIn("Binary file content skipped", res.content)

    def test_read_many_batch(self):
        res = read_many(str(self.root_path), ["file1.txt", "nonexistent.txt"])
        self.assertEqual(len(res.results), 2)
        self.assertIsNone(res.results[0].error)
        self.assertIsNotNone(res.results[1].error)


if __name__ == "__main__":
    unittest.main()
