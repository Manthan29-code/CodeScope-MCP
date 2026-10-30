import os
import tempfile
import pytest
from pathlib import Path

import config
from core.ignore_manager import IgnoreManager
from core import write_guard
from services.read_service import read_one
from services.tree_service import build_tree
from services.search_service import search


@pytest.fixture
def test_env():
    orig_read = list(config.READ_ALLOWED_ROOTS)
    orig_write = list(config.WRITE_ALLOWED_ROOTS)
    orig_allow = list(config.CODESCOPE_ALLOW_IGNORED)
    orig_enable_write = config.ENABLE_WRITE_TOOLS

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir).resolve()
        config.READ_ALLOWED_ROOTS = [str(root)]
        config.WRITE_ALLOWED_ROOTS = [str(root)]
        config.ENABLE_WRITE_TOOLS = True

        # Setup gitignore
        gitignore = root / ".gitignore"
        gitignore.write_text("plan/\nspec.md\n*.local.txt\n", encoding="utf-8")

        # Setup files
        plan_dir = root / "plan"
        plan_dir.mkdir()
        (plan_dir / "spec.md").write_text("# Project Specification\nArchitecture details.", encoding="utf-8")
        (plan_dir / "notes.txt").write_text("internal notes", encoding="utf-8")
        (root / "spec.md").write_text("# Root Spec\nRoot specs.", encoding="utf-8")
        (root / "main.py").write_text("print('hello')", encoding="utf-8")

        IgnoreManager.clear_cache()
        yield root

    config.READ_ALLOWED_ROOTS = orig_read
    config.WRITE_ALLOWED_ROOTS = orig_write
    config.CODESCOPE_ALLOW_IGNORED = orig_allow
    config.ENABLE_WRITE_TOOLS = orig_enable_write
    IgnoreManager.clear_cache()


def test_tree_strips_gitignored_files(test_env, monkeypatch):
    """list_directory_tree must strip gitignored files even if they are in CODESCOPE_ALLOW_IGNORED."""
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", ["*.md", "plan/**", "spec.md"])
    IgnoreManager.clear_cache()

    tree_res = build_tree(str(test_env))
    child_names = [c.name for c in tree_res.tree.children]

    # main.py is tracked / not ignored, so it must be in the tree
    assert "main.py" in child_names

    # plan/ and spec.md are in .gitignore, so they MUST BE STRIPPED from the tree!
    assert "plan" not in child_names
    assert "spec.md" not in child_names


def test_read_file_with_allow_ignored(test_env, monkeypatch):
    """read_file allows reading gitignored files if matched in CODESCOPE_ALLOW_IGNORED."""
    # Without allowlist: reading gitignored file returns an error
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", [])
    IgnoreManager.clear_cache()

    res_blocked = read_one(str(test_env), "plan/spec.md")
    assert res_blocked.error is not None
    assert "ignored by configuration or .gitignore" in res_blocked.error

    # With allowlist for *.md only:
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", ["*.md"])
    IgnoreManager.clear_cache()

    # plan/spec.md matches *.md -> allowed!
    res_allowed = read_one(str(test_env), "plan/spec.md")
    assert res_allowed.error is None
    assert "Project Specification" in res_allowed.content

    # plan/notes.txt does not match *.md -> blocked!
    res_other = read_one(str(test_env), "plan/notes.txt")
    assert res_other.error is not None
    assert "ignored by configuration or .gitignore" in res_other.error


def test_write_guard_with_allow_ignored(test_env, monkeypatch):
    """write_guard allows writing/editing gitignored files if matched in CODESCOPE_ALLOW_IGNORED."""
    target_spec = test_env / "plan" / "spec.md"
    target_notes = test_env / "plan" / "notes.txt"

    # Without allowlist: ensure_not_ignored raises IgnoredPathError
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", [])
    IgnoreManager.clear_cache()

    with pytest.raises(write_guard.IgnoredPathError):
        write_guard.ensure_not_ignored(test_env, target_spec)

    # With allowlist matching *.md:
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", ["*.md"])
    IgnoreManager.clear_cache()

    # Should not raise for spec.md
    write_guard.ensure_not_ignored(test_env, target_spec)

    # But notes.txt is still blocked
    with pytest.raises(write_guard.IgnoredPathError):
        write_guard.ensure_not_ignored(test_env, target_notes)


def test_protected_files_never_allowed(test_env, monkeypatch):
    """Sensitive protected files (.env, keys) can never be overridden by CODESCOPE_ALLOW_IGNORED."""
    env_file = test_env / ".env"
    env_file.write_text("SECRET=12345", encoding="utf-8")

    # Even with an overly broad wildcard allowlist:
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", ["*", ".*", ".env*"])
    IgnoreManager.clear_cache()

    # Reading .env is denied by safety rules
    res = read_one(str(test_env), ".env")
    assert res.error is not None
    assert "protected by safety rules" in res.error

    # Writing .env is denied by safety rules
    with pytest.raises(write_guard.ProtectedPathError):
        write_guard.ensure_not_protected(test_env, env_file)


def test_search_includes_allowed_files(test_env, monkeypatch):
    """search_files can find content in gitignored files when allowed in CODESCOPE_ALLOW_IGNORED."""
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", ["plan/**", "*.md"])
    IgnoreManager.clear_cache()

    search_res = search(str(test_env), query="Architecture", search_type="content")
    matched_paths = [m.file_path for m in search_res.matches]
    assert "plan/spec.md" in matched_paths


def test_codescopeallowed_file_support(test_env, monkeypatch):
    """A .codescopeallowed file in project root acts as a local allowlist."""
    monkeypatch.setattr(config, "CODESCOPE_ALLOW_IGNORED", [])
    IgnoreManager.clear_cache()

    # Before creating .codescopeallowed: reading is blocked
    res_before = read_one(str(test_env), "spec.md")
    assert res_before.error is not None

    # Create .codescopeallowed in project root
    (test_env / ".codescopeallowed").write_text("spec.md\n", encoding="utf-8")
    IgnoreManager.clear_cache()

    # Now reading spec.md succeeds
    res_after = read_one(str(test_env), "spec.md")
    assert res_after.error is None
    assert "Root Spec" in res_after.content

