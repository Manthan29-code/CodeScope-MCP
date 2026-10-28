"""Tests for centralized error handling and structured outputs across file-operation tools."""
import pytest
from pathlib import Path
from models.schemas import EditOperation
from tools.write_file_tool import write_file
from tools.edit_file_tool import edit_file
from tools.delete_file_tool import delete_file
from tools.move_file_tool import move_file
from tools.copy_file_tool import copy_file
from tools.replace_in_files_tool import replace_in_files


# ==============================================================================
# write_file Tests
# ==============================================================================

def test_write_file_success(write_enabled):
    root = str(write_enabled)
    res = write_file(
        project_path=root,
        file_path="src/created.py",
        content="print('created')\n",
        overwrite=False
    )
    assert res["ok"] is True
    assert res["created"] is True
    assert res["overwritten"] is False
    assert res["bytes_written"] > 0
    assert "new_hash" in res
    assert (write_enabled / "src" / "created.py").exists()


def test_write_file_exists_error_handled(write_enabled):
    root = str(write_enabled)
    # src/app.py already exists in write_enabled fixture
    res = write_file(
        project_path=root,
        file_path="src/app.py",
        content="new content\n",
        overwrite=False
    )
    assert res["ok"] is False
    assert res["error_type"] == "FileExistsError"
    assert "already exists" in res["error"]
    assert "hint" in res


def test_write_file_protected_path_handled(write_enabled):
    root = str(write_enabled)
    res = write_file(
        project_path=root,
        file_path=".env",
        content="MALICIOUS=true\n",
        overwrite=True
    )
    assert res["ok"] is False
    assert res["error_type"] == "ProtectedPathError"
    assert "protected" in res["error"]


def test_write_file_disallowed_root_handled(write_enabled):
    forbidden = str(write_enabled.parent / "forbidden_write")
    Path(forbidden).mkdir(parents=True, exist_ok=True)
    res = write_file(
        project_path=forbidden,
        file_path="test.py",
        content="print('bad')\n",
    )
    assert res["ok"] is False
    assert res["error_type"] == "AccessDeniedError"


# ==============================================================================
# edit_file Tests
# ==============================================================================

def test_edit_file_success(write_enabled):
    root = str(write_enabled)
    edits = [
        EditOperation(
            old_string="return 1",
            new_string="return 42",
            replace_all=False
        )
    ]
    res = edit_file(
        project_path=root,
        file_path="src/app.py",
        edits=edits
    )
    assert res["ok"] is True
    assert res["edits_applied"] == 1
    assert res["replacements_made"] == 1
    assert "+    return 42" in res["diff"]
    assert (write_enabled / "src" / "app.py").read_text(encoding="utf-8") == "import util\n\ndef main():\n    return 42\n"


def test_edit_file_match_error_handled(write_enabled):
    root = str(write_enabled)
    edits = [
        EditOperation(
            old_string="non_existent_function_signature()",
            new_string="replacement()",
            replace_all=False
        )
    ]
    res = edit_file(
        project_path=root,
        file_path="src/app.py",
        edits=edits
    )
    assert res["ok"] is False
    assert res["error_type"] == "EditMatchError"
    assert "not found" in res["error"]
    assert "hint" in res


def test_edit_file_stale_hash_handled(write_enabled):
    root = str(write_enabled)
    edits = [
        EditOperation(
            old_string="return 1",
            new_string="return 99",
            replace_all=False
        )
    ]
    res = edit_file(
        project_path=root,
        file_path="src/app.py",
        edits=edits,
        expected_hash="0000000000000000000000000000000000000000000000000000000000000000"
    )
    assert res["ok"] is False
    assert res["error_type"] == "StaleFileError"
    assert "changed since you read it" in res["error"]


def test_edit_file_empty_edits_handled(write_enabled):
    root = str(write_enabled)
    res = edit_file(
        project_path=root,
        file_path="src/app.py",
        edits=[]
    )
    assert res["ok"] is False
    assert res["error_type"] == "InvalidInputError"


# ==============================================================================
# delete_file Tests
# ==============================================================================

def test_delete_file_success(write_enabled):
    root = str(write_enabled)
    target = write_enabled / "src" / "util.py"
    assert target.exists()

    res = delete_file(
        project_path=root,
        file_path="src/util.py"
    )
    assert res["ok"] is True
    assert res["deleted"] is True
    assert not target.exists()


def test_delete_file_protected_path_handled(write_enabled):
    root = str(write_enabled)
    res = delete_file(
        project_path=root,
        file_path=".env"
    )
    assert res["ok"] is False
    assert res["error_type"] == "ProtectedPathError"


def test_delete_file_not_found_handled(write_enabled):
    root = str(write_enabled)
    res = delete_file(
        project_path=root,
        file_path="src/missing.py"
    )
    assert res["ok"] is False
    assert res["error_type"] == "PathNotFoundError"


# ==============================================================================
# move_file Tests
# ==============================================================================

def test_move_file_success(write_enabled):
    root = str(write_enabled)
    res = move_file(
        project_path=root,
        source_path="README.md",
        destination_path="DOCS.md"
    )
    assert res["ok"] is True
    assert res["source_path"] == "README.md"
    assert res["destination_path"] == "DOCS.md"
    assert (write_enabled / "DOCS.md").exists()
    assert not (write_enabled / "README.md").exists()


def test_move_file_source_not_found_handled(write_enabled):
    root = str(write_enabled)
    res = move_file(
        project_path=root,
        source_path="nonexistent.md",
        destination_path="DOCS.md"
    )
    assert res["ok"] is False
    assert res["error_type"] == "PathNotFoundError"


def test_move_file_destination_exists_handled(write_enabled):
    root = str(write_enabled)
    res = move_file(
        project_path=root,
        source_path="README.md",
        destination_path="src/app.py"
    )
    assert res["ok"] is False
    assert res["error_type"] == "FileExistsError"


# ==============================================================================
# copy_file Tests
# ==============================================================================

def test_copy_file_success(write_enabled):
    root = str(write_enabled)
    res = copy_file(
        project_path=root,
        source_path="README.md",
        destination_path="README.copy.md"
    )
    assert res["ok"] is True
    assert res["bytes_copied"] > 0
    assert (write_enabled / "README.md").exists()
    assert (write_enabled / "README.copy.md").exists()


def test_copy_file_destination_exists_handled(write_enabled):
    root = str(write_enabled)
    res = copy_file(
        project_path=root,
        source_path="README.md",
        destination_path="src/app.py"
    )
    assert res["ok"] is False
    assert res["error_type"] == "FileExistsError"


# ==============================================================================
# replace_in_files Tests
# ==============================================================================

def test_replace_in_files_dry_run_success(write_enabled):
    root = str(write_enabled)
    res = replace_in_files(
        project_path=root,
        find="old_name",
        replace="new_name",
        file_pattern="*.py",
        dry_run=True
    )
    assert res["ok"] is True
    assert res["dry_run"] is True
    assert res["files_changed"] > 0
    assert res["total_replacements"] > 0


def test_replace_in_files_empty_find_handled(write_enabled):
    root = str(write_enabled)
    res = replace_in_files(
        project_path=root,
        find="",
        replace="new_name",
        file_pattern="*.py"
    )
    assert res["ok"] is False
    assert res["error_type"] == "InvalidInputError"
