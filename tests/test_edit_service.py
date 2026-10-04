import hashlib
import pytest
from pydantic import ValidationError
import config
from core import write_guard
from models.schemas import EditOperation, EditFileInput
from services import edit_service


def test_edit_one_unique_match_changes_only_that_text(write_enabled):
    root = write_enabled
    out = edit_service.edit_one(
        str(root),
        "src/util.py",
        [EditOperation(old_string="'old_name'", new_string="'new_name'")],
    )
    assert (root / "src/util.py").read_bytes() == b"def helper():\n    return 'new_name'\n"
    assert out.edits_applied == 1 and out.replacements_made == 1
    assert out.dry_run is False and "-    return 'old_name'" in out.diff


def test_edit_one_second_edit_fails_nothing_written(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(edit_service.EditMatchError, match="edit #2"):
        edit_service.edit_one(
            str(root),
            "src/util.py",
            [
                EditOperation(old_string="'old_name'", new_string="'new_name'"),
                EditOperation(old_string="does_not_exist", new_string="x"),
            ],
        )
    assert tree_snapshot(root) == before


def test_edit_one_not_found_reports_edit_number(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(edit_service.EditMatchError, match="edit #1"):
        edit_service.edit_one(
            str(root),
            "src/app.py",
            [EditOperation(old_string="non_existent_function()", new_string="something()")],
        )
    assert tree_snapshot(root) == before


def test_edit_one_multiple_matches_without_replace_all_fails(write_enabled, tree_snapshot):
    root = write_enabled
    target = root / "src" / "repeat.py"
    target.write_bytes(b"foo = 1\nfoo = 2\n")
    before = tree_snapshot(root)

    with pytest.raises(edit_service.EditMatchError, match="found 2 times"):
        edit_service.edit_one(
            str(root),
            "src/repeat.py",
            [EditOperation(old_string="foo", new_string="bar", replace_all=False)],
        )
    assert tree_snapshot(root) == before


def test_edit_one_replace_all_succeeds(write_enabled):
    root = write_enabled
    target = root / "src" / "repeat.py"
    target.write_bytes(b"foo = 1\nfoo = 2\n")

    out = edit_service.edit_one(
        str(root),
        "src/repeat.py",
        [EditOperation(old_string="foo", new_string="bar", replace_all=True)],
    )
    assert out.edits_applied == 1
    assert out.replacements_made == 2
    assert target.read_bytes() == b"bar = 1\nbar = 2\n"


def test_edit_one_sequential_dependent_edits(write_enabled):
    root = write_enabled
    out = edit_service.edit_one(
        str(root),
        "src/util.py",
        [
            EditOperation(old_string="'old_name'", new_string="'step_one'"),
            EditOperation(old_string="'step_one'", new_string="'step_two'"),
        ],
    )
    assert out.edits_applied == 2
    assert out.replacements_made == 2
    assert (root / "src/util.py").read_bytes() == b"def helper():\n    return 'step_two'\n"


def test_edit_one_identical_strings_or_empty_raises(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    with pytest.raises(edit_service.EditMatchError, match="identical"):
        edit_service.edit_one(
            str(root),
            "src/util.py",
            [EditOperation(old_string="'old_name'", new_string="'old_name'")],
        )
    assert tree_snapshot(root) == before


def test_edit_one_deletion_with_empty_new_string(write_enabled):
    root = write_enabled
    out = edit_service.edit_one(
        str(root),
        "README.md",
        [EditOperation(old_string="old_name appears here\n", new_string="")],
    )
    assert out.replacements_made == 1
    assert (root / "README.md").read_bytes() == b"# Demo\n"


def test_edit_one_crlf_file_multi_line_and_style_preserved(write_enabled):
    root = write_enabled
    out = edit_service.edit_one(
        str(root),
        "crlf.txt",
        [EditOperation(old_string="line1\nline2", new_string="first\nsecond")],
    )
    assert out.edits_applied == 1
    raw = (root / "crlf.txt").read_bytes()
    assert raw == b"first\r\nsecond\r\nline3\r\n"


def test_edit_one_bom_preserved(write_enabled):
    root = write_enabled
    edit_service.edit_one(
        str(root),
        "bom.txt",
        [EditOperation(old_string="world", new_string="everyone")],
    )
    raw = (root / "bom.txt").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"everyone" in raw


def test_edit_one_mixed_newlines_refused(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(write_guard.WriteError, match="mixed line endings"):
        edit_service.edit_one(
            str(root),
            "mixed.txt",
            [EditOperation(old_string="line1", new_string="newline1")],
        )
    assert tree_snapshot(root) == before


def test_edit_one_expected_hash_chaining(write_enabled):
    root = write_enabled
    target = root / "src" / "util.py"
    initial_hash = hashlib.sha256(target.read_bytes()).hexdigest()

    # First edit with initial expected_hash
    out1 = edit_service.edit_one(
        str(root),
        "src/util.py",
        [EditOperation(old_string="'old_name'", new_string="'v1'")],
        expected_hash=initial_hash,
    )
    assert out1.new_hash == hashlib.sha256(target.read_bytes()).hexdigest()

    # Second edit chained with out1.new_hash
    out2 = edit_service.edit_one(
        str(root),
        "src/util.py",
        [EditOperation(old_string="'v1'", new_string="'v2'")],
        expected_hash=out1.new_hash,
    )
    assert out2.new_hash == hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.read_bytes() == b"def helper():\n    return 'v2'\n"


def test_edit_one_dry_run_leaves_file_unchanged(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    out = edit_service.edit_one(
        str(root),
        "src/util.py",
        [EditOperation(old_string="'old_name'", new_string="'preview'")],
        dry_run=True,
    )
    assert out.dry_run is True
    assert "-    return 'old_name'" in out.diff
    assert "+    return 'preview'" in out.diff
    assert tree_snapshot(root) == before


def test_edit_one_nonexistent_file_mentions_write_file(write_enabled):
    root = write_enabled
    with pytest.raises(FileNotFoundError, match="write_file"):
        edit_service.edit_one(
            str(root),
            "missing.py",
            [EditOperation(old_string="a", new_string="b")],
        )


def test_edit_one_blocked_files(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    # Binary file
    with pytest.raises(write_guard.BinaryFileError):
        edit_service.edit_one(
            str(root),
            "data.bin",
            [EditOperation(old_string="binary", new_string="text")],
        )

    # Protected .env
    with pytest.raises(write_guard.ProtectedPathError):
        edit_service.edit_one(
            str(root),
            ".env",
            [EditOperation(old_string="SECRET", new_string="NEW_SECRET")],
        )

    # Ignored file
    with pytest.raises(write_guard.IgnoredPathError):
        edit_service.edit_one(
            str(root),
            "dist/out.js",
            [EditOperation(old_string="old_name", new_string="new_name")],
        )

    assert tree_snapshot(root) == before


def test_edit_one_max_edits_schema_validation(write_enabled):
    root = write_enabled
    too_many_edits = [
        EditOperation(old_string=f"old_{i}", new_string=f"new_{i}")
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        EditFileInput(
            project_path=str(root),
            file_path="src/util.py",
            edits=too_many_edits,
        )


def test_edit_one_no_changes_error(write_enabled, tree_snapshot):
    root = write_enabled
    target = root / "src" / "same.py"
    target.write_bytes(b"hello world\n")
    before = tree_snapshot(root)

    # Edit that produces no net change
    with pytest.raises(write_guard.WriteError, match="no changes"):
        edit_service.edit_one(
            str(root),
            "src/same.py",
            [
                EditOperation(old_string="hello", new_string="temp"),
                EditOperation(old_string="temp", new_string="hello"),
            ],
        )
    assert tree_snapshot(root) == before


def test_edit_one_whitespace_spaces_vs_tabs_exact_match(write_enabled):
    root = write_enabled
    # src/app.py uses 4 spaces for indentation: '    return 1\n'
    # Searching with a tab '\treturn 1\n' must fail to find match
    with pytest.raises(edit_service.EditMatchError, match="not found"):
        edit_service.edit_one(
            str(root),
            "src/app.py",
            [EditOperation(old_string="\treturn 1", new_string="\treturn 2")],
        )
