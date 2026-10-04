import hashlib
import pytest
import config
from core import write_guard
from services import write_service


def test_create_new_file_success(write_enabled):
    root = write_enabled
    out = write_service.write_one(
        str(root),
        "src/new_file.py",
        "print('hello world')\n",
    )
    assert out.created is True
    assert out.overwritten is False
    assert out.dry_run is False
    assert out.diff is None

    target = root / "src" / "new_file.py"
    assert target.exists()
    assert target.read_bytes() == b"print('hello world')\n"
    assert out.new_hash == hashlib.sha256(b"print('hello world')\n").hexdigest()
    assert len(list(target.parent.glob(".codescope-*.tmp"))) == 0


def test_overwrite_false_when_exists_raises(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises(FileExistsError, match="already exists"):
        write_service.write_one(
            str(root),
            "src/app.py",
            "new content",
            overwrite=False,
        )
    assert tree_snapshot(root) == before


def test_overwrite_true_replaces_and_provides_diff(write_enabled):
    root = write_enabled
    out = write_service.write_one(
        str(root),
        "src/app.py",
        "def main():\n    return 42\n",
        overwrite=True,
    )
    assert out.created is False
    assert out.overwritten is True
    assert out.dry_run is False
    assert out.diff is not None
    assert "-    return 1" in out.diff
    assert "+    return 42" in out.diff
    assert (root / "src" / "app.py").read_bytes() == b"def main():\n    return 42\n"


def test_overwrite_crlf_file_preserves_crlf(write_enabled):
    root = write_enabled
    write_service.write_one(
        str(root),
        "crlf.txt",
        "new line 1\nnew line 2\n",
        overwrite=True,
    )
    raw = (root / "crlf.txt").read_bytes()
    assert raw == b"new line 1\r\nnew line 2\r\n"


def test_overwrite_bom_file_preserves_bom(write_enabled):
    root = write_enabled
    write_service.write_one(
        str(root),
        "bom.txt",
        "hello universe\n",
        overwrite=True,
    )
    raw = (root / "bom.txt").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_expected_hash_match_and_mismatch(write_enabled, tree_snapshot):
    root = write_enabled
    target = root / "src" / "app.py"
    correct_hash = hashlib.sha256(target.read_bytes()).hexdigest()

    # Match succeeds
    out = write_service.write_one(
        str(root),
        "src/app.py",
        "def main():\n    return 100\n",
        overwrite=True,
        expected_hash=correct_hash,
    )
    assert out.overwritten is True

    # Mismatch raises and leaves tree unchanged
    before = tree_snapshot(root)
    with pytest.raises(write_guard.StaleFileError, match="read_file"):
        write_service.write_one(
            str(root),
            "src/app.py",
            "def main():\n    return 200\n",
            overwrite=True,
            expected_hash="stale_hash_value",
        )
    assert tree_snapshot(root) == before

    # Expected hash for nonexistent file raises
    with pytest.raises(write_guard.StaleFileError, match="does not exist"):
        write_service.write_one(
            str(root),
            "nonexistent.py",
            "content",
            expected_hash="any_hash",
        )


def test_create_parents_flag(write_enabled):
    root = write_enabled
    # Without create_parents -> raises
    with pytest.raises(ValueError, match="create_parents"):
        write_service.write_one(
            str(root),
            "deep/nested/dir/test.txt",
            "content",
            create_parents=False,
        )

    # With create_parents -> succeeds
    out = write_service.write_one(
        str(root),
        "deep/nested/dir/test.txt",
        "content",
        create_parents=True,
    )
    assert out.created is True
    assert (root / "deep" / "nested" / "dir" / "test.txt").read_text() == "content"


def test_dry_run_create_and_overwrite(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    # Dry run create
    out_create = write_service.write_one(
        str(root),
        "another_nested/dir/preview.txt",
        "preview data",
        create_parents=True,
        dry_run=True,
    )
    assert out_create.dry_run is True
    assert out_create.created is True
    assert tree_snapshot(root) == before  # No dirs, no files created

    # Dry run overwrite
    out_ow = write_service.write_one(
        str(root),
        "src/app.py",
        "new app content",
        overwrite=True,
        dry_run=True,
    )
    assert out_ow.dry_run is True
    assert out_ow.overwritten is True
    assert out_ow.diff is not None
    assert tree_snapshot(root) == before


def test_target_is_directory_raises(write_enabled):
    root = write_enabled
    with pytest.raises(ValueError, match="directory"):
        write_service.write_one(str(root), "src", "data", overwrite=True)


@pytest.mark.parametrize(
    "rel_path",
    [
        ".env",
        ".git/config",
        "dist/out.js",
        "../outside.py",
    ],
)
def test_blocked_paths_leave_tree_unchanged(write_enabled, rel_path, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)
    with pytest.raises((write_guard.WriteError, ValueError, PermissionError)):
        write_service.write_one(str(root), rel_path, "malicious", overwrite=True)
    assert tree_snapshot(root) == before


def test_content_too_large_or_null_bytes(write_enabled, monkeypatch, tree_snapshot):
    root = write_enabled
    monkeypatch.setattr(config, "MAX_WRITE_SIZE_BYTES", 10)
    before = tree_snapshot(root)

    with pytest.raises(write_guard.FileTooLargeError):
        write_service.write_one(str(root), "src/large.py", "1234567890123")
    assert tree_snapshot(root) == before

    with pytest.raises(write_guard.BinaryFileError):
        write_service.write_one(str(root), "src/binary.py", "hello\x00world")
    assert tree_snapshot(root) == before
