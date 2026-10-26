import pytest
from pathlib import Path
from utils.git_validators import (
    to_repo_relative,
    validate_ref_name,
    validate_revision,
)


def test_validate_ref_name_valid():
    assert validate_ref_name("main") == "main"
    assert validate_ref_name("feature/x") == "feature/x"
    assert validate_ref_name("release/1.0.0") == "release/1.0.0"
    assert validate_ref_name("user-branch_1") == "user-branch_1"


def test_validate_ref_name_invalid():
    bad_refs = [
        "-x",
        "/leading-slash",
        "trailing-slash/",
        "ends-with-dot.",
        "branch.lock",
        "a..b",
        "a//b",
        "branch@{1}",
        "@",
        "with space",
        "with~tilde",
        "with^caret",
        "with:colon",
        "with?question",
        "with*star",
        "with[bracket",
        "with\\backslash",
        "",
        "x" * 201,
    ]
    for bad in bad_refs:
        with pytest.raises(ValueError):
            validate_ref_name(bad)


def test_validate_revision_valid():
    assert validate_revision("HEAD") == "HEAD"
    assert validate_revision("HEAD~2") == "HEAD~2"
    assert validate_revision("HEAD^") == "HEAD^"
    assert validate_revision("v1.0.0") == "v1.0.0"
    assert validate_revision("a" * 40) == "a" * 40


def test_validate_revision_invalid():
    bad_revs = [
        "-o",
        "--all",
        "main..feature",
        "main...feature",
        "with space",
        "with:colon",
        "",
        "a" * 201,
    ]
    for bad in bad_revs:
        with pytest.raises(ValueError):
            validate_revision(bad)


def test_to_repo_relative(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    file = sub / "file.txt"
    file.write_text("hello")

    assert to_repo_relative(tmp_path, "sub/file.txt") == "sub/file.txt"
    assert to_repo_relative(tmp_path, "sub\\file.txt") == "sub/file.txt"
    assert to_repo_relative(tmp_path, ".") == "."

    # Path escape
    with pytest.raises(PermissionError):
        to_repo_relative(tmp_path, "../outside.txt")

    # Invalid paths
    with pytest.raises(ValueError):
        to_repo_relative(tmp_path, "")
    with pytest.raises(ValueError):
        to_repo_relative(tmp_path, "null\x00byte")
