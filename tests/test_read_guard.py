import os
from pathlib import Path
import pytest
import config
from core import path_security
from tools.read_file_tool import read_file
from tools.search_files_tool import search_files


def test_verify_read_root_empty_allowlist_refused(project, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [])
    monkeypatch.setattr(config, "ALLOWED_PROJECT_ROOTS", [])
    with pytest.raises(path_security.ReadRootNotAllowedError, match="empty"):
        path_security.verify_read_root(str(project))


def test_verify_read_root_allowed_root_succeeds(project, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    resolved = path_security.verify_read_root(str(project))
    assert resolved == project.resolve()


def test_verify_read_root_subfolder_of_allowed_root_succeeds(project, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    subfolder = project / "src"
    resolved = path_security.verify_read_root(str(subfolder))
    assert resolved == subfolder.resolve()


def test_verify_read_root_outside_allowed_root_refused(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    outside = tmp_path_factory.mktemp("outside_dir")
    with pytest.raises(path_security.ReadRootNotAllowedError, match="not within any allowed root"):
        path_security.verify_read_root(str(outside))


def test_verify_read_root_sibling_attack_refused(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    # Sibling with matching prefix e.g. project-evil
    sibling = project.parent / f"{project.name}-evil"
    sibling.mkdir(exist_ok=True)
    try:
        with pytest.raises(path_security.ReadRootNotAllowedError, match="not within any allowed root"):
            path_security.verify_read_root(str(sibling))
    finally:
        if sibling.exists():
            sibling.rmdir()


def test_verify_read_root_filesystem_or_drive_root_refused(monkeypatch):
    drive_root = "C:\\" if os.name == "nt" else "/"
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [drive_root])
    with pytest.raises(path_security.ReadRootNotAllowedError, match="filesystem or drive root"):
        path_security.verify_read_root(drive_root)


def test_verify_read_root_nonexistent_or_file_raises(project, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    with pytest.raises(ValueError, match="does not exist"):
        path_security.verify_read_root(str(project / "nonexistent"))
    with pytest.raises(ValueError, match="not a directory"):
        path_security.verify_read_root(str(project / "src" / "app.py"))


@pytest.mark.skipif(os.name != "nt", reason="Windows case-insensitivity test")
def test_verify_read_root_windows_case_insensitive_root(project, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project).lower()])
    resolved = path_security.verify_read_root(str(project).upper())
    assert resolved == project.resolve()


def test_resolve_and_verify_enforces_read_roots(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    outside = tmp_path_factory.mktemp("outside_dir")
    outside_file = outside / "secret.txt"
    outside_file.write_text("secret")

    with pytest.raises(path_security.ReadRootNotAllowedError):
        path_security.resolve_and_verify(str(outside), "secret.txt")


def test_read_file_tool_integration_blocked(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    outside = tmp_path_factory.mktemp("outside_dir")
    outside_file = outside / "secret.txt"
    outside_file.write_text("secret content")

    result = read_file("secret.txt", project_path=str(outside))
    assert result.error is not None
    assert "not within any allowed root in READ_ALLOWED_ROOTS" in result.error
    assert result.content == ""


def test_search_files_tool_integration_blocked(project, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(project)])
    outside = tmp_path_factory.mktemp("outside_dir")

    with pytest.raises(path_security.ReadRootNotAllowedError):
        search_files("query", project_path=str(outside))
