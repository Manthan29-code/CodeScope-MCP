import os
import sys
import pytest
import config
from core import write_guard
from services import file_ops_service


# -------------------------------------------------------------
# delete_one Tests
# -------------------------------------------------------------

def test_delete_one_success(write_enabled):
    root = write_enabled
    target = root / "README.md"
    assert target.exists()
    size = target.stat().st_size

    out = file_ops_service.delete_one(str(root), "README.md")
    assert out.deleted is True
    assert out.size_bytes == size
    assert not target.exists()


def test_delete_one_directory_error(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(ValueError, match="Directories are not supported"):
        file_ops_service.delete_one(str(root), "src")
    assert tree_snapshot(root) == before


def test_delete_one_missing_file_error(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(Exception):
        file_ops_service.delete_one(str(root), "nonexistent.txt")
    assert tree_snapshot(root) == before


@pytest.mark.parametrize("blocked_path", [
    ".env",
    ".git/config",
    "node_modules/pkg/index.js",
    "dist/out.js",
])
def test_delete_one_protected_and_ignored_blocked(write_enabled, tree_snapshot, blocked_path):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(write_guard.WriteError):
        file_ops_service.delete_one(str(root), blocked_path)
    assert tree_snapshot(root) == before


def test_delete_one_path_traversal_blocked(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(Exception):
        file_ops_service.delete_one(str(root), "../outside.txt")
    assert tree_snapshot(root) == before


def test_delete_one_gate_disabled(project, monkeypatch, tree_snapshot):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    before = tree_snapshot(project)
    with pytest.raises(write_guard.WriteDisabledError):
        file_ops_service.delete_one(str(project), "src/app.py")
    assert tree_snapshot(project) == before


# -------------------------------------------------------------
# move_one Tests
# -------------------------------------------------------------

def test_move_one_rename_within_directory(write_enabled):
    root = write_enabled
    src = root / "src/util.py"
    dst = root / "src/helper.py"
    original_data = src.read_bytes()

    out = file_ops_service.move_one(str(root), "src/util.py", "src/helper.py")
    assert out.source_path == "src/util.py"
    assert out.destination_path == "src/helper.py"
    assert not src.exists()
    assert dst.exists()
    assert dst.read_bytes() == original_data


def test_move_one_create_parents(write_enabled):
    root = write_enabled
    src = root / "src/util.py"

    # Fails when create_parents=False
    with pytest.raises(Exception):
        file_ops_service.move_one(str(root), "src/util.py", "newdir/sub/util.py", create_parents=False)

    # Succeeds when create_parents=True
    out = file_ops_service.move_one(str(root), "src/util.py", "newdir/sub/util.py", create_parents=True)
    assert out.destination_path == "newdir/sub/util.py"
    assert (root / "newdir/sub/util.py").exists()
    assert not src.exists()


def test_move_one_destination_exists_fails(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(FileExistsError):
        file_ops_service.move_one(str(root), "src/app.py", "src/util.py")
    assert tree_snapshot(root) == before


def test_move_one_source_missing_fails(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(Exception):
        file_ops_service.move_one(str(root), "nonexistent.py", "src/new.py")
    assert tree_snapshot(root) == before


def test_move_one_source_equals_destination(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(ValueError, match="identical"):
        file_ops_service.move_one(str(root), "src/app.py", "src/app.py")
    assert tree_snapshot(root) == before


@pytest.mark.parametrize("src_path,dst_path", [
    ("src/app.py", ".env"),
    ("src/app.py", "dist/out.js"),
    ("node_modules/pkg/index.js", "src/pkg.js"),
    ("dist/out.js", "src/out.js"),
])
def test_move_one_protected_and_ignored_fails(write_enabled, tree_snapshot, src_path, dst_path):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(write_guard.WriteError):
        file_ops_service.move_one(str(root), src_path, dst_path)
    assert tree_snapshot(root) == before


def test_move_one_binary_file_moves_intact(write_enabled):
    root = write_enabled
    src = root / "data.bin"
    dst = root / "data_moved.bin"
    original_data = src.read_bytes()

    file_ops_service.move_one(str(root), "data.bin", "data_moved.bin")
    assert not src.exists()
    assert dst.exists()
    assert dst.read_bytes() == original_data


@pytest.mark.skipif(os.name != "nt", reason="Windows case-only rename test")
def test_move_one_case_only_rename_windows(write_enabled):
    root = write_enabled
    src_content = (root / "src/util.py").read_bytes()

    out = file_ops_service.move_one(str(root), "src/util.py", "src/Util.py")
    assert out.destination_path == "src/Util.py"
    assert (root / "src/Util.py").read_bytes() == src_content


# -------------------------------------------------------------
# copy_one Tests
# -------------------------------------------------------------

def test_copy_one_success(write_enabled):
    root = write_enabled
    src = root / "src/app.py"
    dst = root / "src/app_copy.py"
    data = src.read_bytes()

    out = file_ops_service.copy_one(str(root), "src/app.py", "src/app_copy.py")
    assert out.bytes_copied == len(data)
    assert src.exists()
    assert dst.exists()
    assert dst.read_bytes() == data


def test_copy_one_destination_exists_fails(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(FileExistsError):
        file_ops_service.copy_one(str(root), "src/app.py", "src/util.py")
    assert tree_snapshot(root) == before


def test_copy_one_binary_file(write_enabled):
    root = write_enabled
    src = root / "data.bin"
    dst = root / "data_copy.bin"
    data = src.read_bytes()

    out = file_ops_service.copy_one(str(root), "data.bin", "data_copy.bin")
    assert out.bytes_copied == len(data)
    assert dst.read_bytes() == data


def test_copy_one_exceeds_max_write_size(write_enabled, monkeypatch, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    monkeypatch.setattr(config, "MAX_WRITE_SIZE_BYTES", 5)

    with pytest.raises(write_guard.FileTooLargeError):
        file_ops_service.copy_one(str(root), "src/app.py", "src/large_copy.py")
    assert tree_snapshot(root) == before


def test_copy_one_create_parents(write_enabled):
    root = write_enabled
    # Fails when False
    with pytest.raises(Exception):
        file_ops_service.copy_one(str(root), "src/app.py", "backup/copy.py", create_parents=False)

    # Succeeds when True
    out = file_ops_service.copy_one(str(root), "src/app.py", "backup/copy.py", create_parents=True)
    assert out.destination_path == "backup/copy.py"
    assert (root / "backup/copy.py").exists()


@pytest.mark.parametrize("src_path,dst_path", [
    ("src/app.py", ".env"),
    ("src/app.py", "dist/copy.js"),
    ("node_modules/pkg/index.js", "src/pkg.js"),
    ("dist/out.js", "src/out.js"),
])
def test_copy_one_protected_and_ignored_fails(write_enabled, tree_snapshot, src_path, dst_path):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(write_guard.WriteError):
        file_ops_service.copy_one(str(root), src_path, dst_path)
    assert tree_snapshot(root) == before


def test_copy_one_no_temp_files_on_failure(write_enabled, monkeypatch):
    import shutil
    root = write_enabled

    def broken_copy(*args, **kwargs):
        raise OSError("Disk write error")

    monkeypatch.setattr(shutil, "copy2", broken_copy)

    with pytest.raises(OSError, match="Disk write error"):
        file_ops_service.copy_one(str(root), "src/app.py", "src/broken.py")

    tmp_files = list(root.glob("src/.codescope-*.tmp"))
    assert len(tmp_files) == 0
