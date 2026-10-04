import os
from pathlib import Path
import pytest
import config
from core import write_guard


def test_begin_write_gate_off(project, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    with pytest.raises(write_guard.WriteDisabledError, match="disabled"):
        write_guard.begin_write(str(project))


def test_begin_write_empty_allowlist_refused(project, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [])
    with pytest.raises(write_guard.RootNotAllowedError, match="empty"):
        write_guard.begin_write(str(project))


def test_begin_write_allowed_root_succeeds(project, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(project)])
    resolved = write_guard.begin_write(str(project))
    assert resolved == project.resolve()


def test_begin_write_subfolder_of_allowed_root_succeeds(project, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(project)])
    subfolder = project / "src"
    resolved = write_guard.begin_write(str(subfolder))
    assert resolved == subfolder.resolve()


def test_begin_write_outside_allowed_root_refused(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(project)])
    outside = tmp_path_factory.mktemp("outside_dir")
    with pytest.raises(write_guard.RootNotAllowedError, match="not within any allowed root"):
        write_guard.begin_write(str(outside))


def test_begin_write_filesystem_or_drive_root_refused(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    drive_root = "C:\\" if os.name == "nt" else "/"
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [drive_root])
    with pytest.raises(write_guard.RootNotAllowedError, match="root"):
        write_guard.begin_write(drive_root)


def test_begin_write_nonexistent_or_file_raises(project, write_enabled):
    with pytest.raises(ValueError, match="does not exist"):
        write_guard.begin_write(str(project / "nonexistent"))
    with pytest.raises(ValueError, match="not a directory"):
        write_guard.begin_write(str(project / "src" / "app.py"))


@pytest.mark.skipif(os.name != "nt", reason="Windows case-insensitivity test")
def test_begin_write_windows_case_insensitive_root(project, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(project).lower()])
    resolved = write_guard.begin_write(str(project).upper())
    assert resolved == project.resolve()


@pytest.mark.parametrize(
    "rel_path, should_block",
    [
        (".git/config", True),
        (".git/hooks/pre-commit", True),
        (".env", True),
        (".env.local", True),
        ("sub/.env", True),
        ("server.pem", True),
        ("deploy.key", True),
        (".env.example", False),
        ("src/app.py", False),
    ],
)
def test_ensure_not_protected(project, rel_path, should_block):
    target = project / rel_path
    if should_block:
        with pytest.raises(write_guard.ProtectedPathError, match="protected"):
            write_guard.ensure_not_protected(project, target)
    else:
        write_guard.ensure_not_protected(project, target)


def test_ensure_not_ignored_blocks_ignored_files(project):
    # .gitignore has dist/ and *.log, default ignore has node_modules/
    with pytest.raises(write_guard.IgnoredPathError, match="ignored"):
        write_guard.ensure_not_ignored(project, project / "node_modules" / "x.js")

    with pytest.raises(write_guard.IgnoredPathError, match="ignored"):
        write_guard.ensure_not_ignored(project, project / "dist" / "new.js")

    with pytest.raises(write_guard.IgnoredPathError, match="ignored"):
        write_guard.ensure_not_ignored(project, project / "app.log")

    # Allowed path
    write_guard.ensure_not_ignored(project, project / "src" / "new.py")


def test_ensure_not_ignored_disabled(project, monkeypatch):
    monkeypatch.setattr(config, "BLOCK_WRITES_TO_IGNORED", False)
    # Should not raise when disabled
    write_guard.ensure_not_ignored(project, project / "dist" / "new.js")


def test_ensure_size_ok(monkeypatch):
    monkeypatch.setattr(config, "MAX_WRITE_SIZE_BYTES", 10)
    write_guard.ensure_size_ok(b"1234567890")  # exactly 10 bytes -> ok
    with pytest.raises(write_guard.FileTooLargeError, match="exceeds"):
        write_guard.ensure_size_ok(b"12345678901")  # 11 bytes -> raises


def test_ensure_text_file(project):
    with pytest.raises(write_guard.BinaryFileError, match="binary"):
        write_guard.ensure_text_file(project / "data.bin")

    # Regular text file does not raise
    write_guard.ensure_text_file(project / "src" / "app.py")


def test_ensure_text_content():
    with pytest.raises(write_guard.BinaryFileError, match="null bytes"):
        write_guard.ensure_text_content("hello\x00world")

    write_guard.ensure_text_content("hello world\n")


def test_check_expected_hash(project):
    target = project / "src" / "util.py"
    raw = target.read_bytes()
    import hashlib
    correct_hash = hashlib.sha256(raw).hexdigest()

    # Correct hash passes
    write_guard.check_expected_hash(target, correct_hash)

    # None hash passes (skipped)
    write_guard.check_expected_hash(target, None)

    # Mismatched hash raises StaleFileError
    with pytest.raises(write_guard.StaleFileError, match="read_file"):
        write_guard.check_expected_hash(target, "wronghash12345")
