import os
import stat
import pytest
from core import file_writer


def test_sha256_bytes():
    assert file_writer.sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.parametrize(
    "rel_path",
    [
        "crlf.txt",
        "bom.txt",
        "src/app.py",
    ],
)
def test_round_trip_existing_project_files(project, rel_path):
    p = project / rel_path
    style = file_writer.read_text_with_style(p)
    encoded = file_writer.encode_text_with_style(style.text, style)
    assert encoded == p.read_bytes()


def test_round_trip_empty_and_no_trailing_newline(project):
    empty_file = project / "empty.txt"
    empty_file.write_bytes(b"")

    no_nl_file = project / "no_nl.txt"
    no_nl_file.write_bytes(b"first line\nsecond line without newline")

    for f in (empty_file, no_nl_file):
        style = file_writer.read_text_with_style(f)
        encoded = file_writer.encode_text_with_style(style.text, style)
        assert encoded == f.read_bytes()


def test_crlf_file_detection(project):
    p = project / "crlf.txt"
    style = file_writer.read_text_with_style(p)
    assert style.newline == "\r\n"
    assert "\r" not in style.text
    assert style.trailing_newline is True
    assert style.mixed_newlines is False


def test_bom_file_detection(project):
    p = project / "bom.txt"
    style = file_writer.read_text_with_style(p)
    assert style.bom is True
    assert not style.text.startswith("\ufeff")
    assert style.newline == "\r\n"
    assert style.trailing_newline is True


def test_mixed_newlines_detection(project):
    p = project / "mixed.txt"
    style = file_writer.read_text_with_style(p)
    assert style.mixed_newlines is True


def test_non_utf8_file_handling(project):
    # Non-UTF8 text with non-ASCII characters
    text = "Hélène déjà vu et café crème. " * 20
    cp1252_bytes = text.encode("windows-1252")
    p = project / "cp1252.txt"
    p.write_bytes(cp1252_bytes)

    style = file_writer.read_text_with_style(p)
    assert style.encoding is not None
    encoded = file_writer.encode_text_with_style(style.text, style)
    assert encoded == cp1252_bytes


def test_atomic_write_bytes_creates_and_overwrites(tmp_path):
    target = tmp_path / "subdir" / "test_file.txt"
    data1 = b"initial content"
    file_writer.atomic_write_bytes(target, data1)
    assert target.read_bytes() == data1

    # Check no temp files left in directory
    temp_files = list(target.parent.glob(".codescope-*.tmp"))
    assert len(temp_files) == 0

    data2 = b"overwritten content"
    file_writer.atomic_write_bytes(target, data2)
    assert target.read_bytes() == data2

    temp_files = list(target.parent.glob(".codescope-*.tmp"))
    assert len(temp_files) == 0


def test_atomic_write_bytes_failure_cleanup(tmp_path, monkeypatch):
    target = tmp_path / "failure_test.txt"
    target.write_bytes(b"original content")

    def failing_replace(src, dst):
        raise OSError("Simulated atomic replace disk failure")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="Simulated"):
        file_writer.atomic_write_bytes(target, b"new content that should fail")

    # Original content preserved
    assert target.read_bytes() == b"original content"
    # No temporary files left behind
    temp_files = list(tmp_path.glob(".codescope-*.tmp"))
    assert len(temp_files) == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions preservation test")
def test_atomic_write_preserves_permissions_posix(tmp_path):
    target = tmp_path / "script.sh"
    target.write_bytes(b"echo 1")
    os.chmod(target, 0o755)

    file_writer.atomic_write_bytes(target, b"echo 2")
    file_stat = target.stat()
    assert stat.S_IMODE(file_stat.st_mode) == 0o755
