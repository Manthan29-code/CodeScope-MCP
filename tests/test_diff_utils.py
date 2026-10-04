import config
from core import diff_utils


def test_unified_diff_identical_returns_empty():
    text = "line1\nline2\nline3\n"
    assert diff_utils.unified_diff(text, text, "src/app.py") == ""


def test_unified_diff_one_line_change():
    old_text = "def main():\n    return 1\n"
    new_text = "def main():\n    return 2\n"
    diff = diff_utils.unified_diff(old_text, new_text, "src/app.py")
    assert "--- a/src/app.py" in diff
    assert "+++ b/src/app.py" in diff
    assert "-    return 1" in diff
    assert "+    return 2" in diff


def test_unified_diff_truncation(monkeypatch):
    monkeypatch.setattr(config, "MAX_DIFF_CHARS", 100)
    old_text = "\n".join([f"old_line_{i}" for i in range(50)])
    new_text = "\n".join([f"new_line_{i}" for i in range(50)])

    diff = diff_utils.unified_diff(old_text, new_text, "test.txt")
    assert "... diff truncated (" in diff
    assert "more lines)" in diff


def test_count_changed_lines():
    old_text = "line1\nline2\nline3\nline4\n"
    new_text = "line1\nline2_modified\nline4\nline5_added\n"

    added, removed = diff_utils.count_changed_lines(old_text, new_text)
    assert added == 2
    assert removed == 2
