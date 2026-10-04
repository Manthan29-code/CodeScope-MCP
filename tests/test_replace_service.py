import pytest
import config
from core import write_guard
from core import file_writer
from services import replace_service


def test_replace_in_files_dry_run_default(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="*.*",
    )

    assert out.dry_run is True
    assert out.files_changed > 0
    assert out.total_replacements > 0
    assert len(out.results) > 0
    for res in out.results:
        assert res.diff != ""
        assert res.replacements > 0

    # Ensure nothing changed on disk
    assert tree_snapshot(root) == before


def test_replace_in_files_literal_scope_and_filter(write_enabled):
    root = write_enabled

    # Only replace in *.py
    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="*.py",
        dry_run=False,
    )

    assert out.dry_run is False
    assert (root / "src/util.py").read_text(encoding="utf-8") == "def helper():\n    return 'new_name'\n"
    # README.md should still contain old_name because file_pattern="*.py"
    assert "old_name" in (root / "README.md").read_text(encoding="utf-8")


def test_replace_in_files_subpath_restriction(write_enabled):
    root = write_enabled

    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="*.*",
        subpath="src",
        dry_run=False,
    )

    assert (root / "src/util.py").read_text(encoding="utf-8") == "def helper():\n    return 'new_name'\n"
    assert "old_name" in (root / "README.md").read_text(encoding="utf-8")


def test_replace_in_files_ignored_and_protected_skipped(write_enabled):
    root = write_enabled

    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="*.*",
        dry_run=False,
    )

    # Protected .env and ignored node_modules, dist, debug.log must NOT be modified
    assert "SECRET=old_name" in (root / ".env").read_text(encoding="utf-8")
    assert "old_name" in (root / "node_modules/pkg/index.js").read_text(encoding="utf-8")
    assert "old_name" in (root / "dist/out.js").read_text(encoding="utf-8")
    assert "old_name" in (root / "debug.log").read_text(encoding="utf-8")


def test_replace_in_files_skipped_types(write_enabled, monkeypatch):
    root = write_enabled

    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="*.*",
        dry_run=True,
    )

    skipped_reasons = {s["file_path"]: s["reason"] for s in out.skipped}
    # data.bin is binary, mixed.txt has mixed endings
    assert "data.bin" in skipped_reasons
    assert "mixed.txt" in skipped_reasons
    assert skipped_reasons["mixed.txt"] == "mixed line endings"


def test_replace_in_files_regex_backreferences(write_enabled):
    root = write_enabled

    # In README.md: "old_name appears here"
    out = replace_service.replace_in_files(
        str(root),
        find=r"old_(\w+)",
        replace=r"brand_new_\1",
        file_pattern="README.md",
        regex=True,
        dry_run=False,
    )

    assert out.total_replacements == 1
    readme_content = (root / "README.md").read_text(encoding="utf-8")
    assert "brand_new_name appears here" in readme_content


def test_replace_in_files_literal_mode_handles_special_chars(write_enabled):
    root = write_enabled
    # Add a file with literal dots and backslashes
    (root / "src/special.py").write_text("regex.test \\1 here\n", encoding="utf-8")

    out = replace_service.replace_in_files(
        str(root),
        find="regex.test \\1",
        replace="literal.success \\2",
        file_pattern="special.py",
        regex=False,
        dry_run=False,
    )

    assert out.total_replacements == 1
    assert (root / "src/special.py").read_text(encoding="utf-8") == "literal.success \\2 here\n"


def test_replace_in_files_case_sensitivity(write_enabled):
    root = write_enabled
    (root / "src/case.txt").write_text("abc ABC Abc", encoding="utf-8")

    out_ci = replace_service.replace_in_files(
        str(root),
        find="abc",
        replace="X",
        file_pattern="case.txt",
        case_sensitive=False,
        dry_run=True,
    )
    assert out_ci.total_replacements == 3

    out_cs = replace_service.replace_in_files(
        str(root),
        find="abc",
        replace="X",
        file_pattern="case.txt",
        case_sensitive=True,
        dry_run=True,
    )
    assert out_cs.total_replacements == 1


def test_replace_in_files_invalid_pattern_and_empty_match(write_enabled):
    root = write_enabled

    with pytest.raises(ValueError, match="empty string"):
        replace_service.replace_in_files(
            str(root),
            find="a*",
            replace="x",
            file_pattern="*.py",
            regex=True,
        )

    with pytest.raises(ValueError, match="non-empty"):
        replace_service.replace_in_files(
            str(root),
            find="",
            replace="x",
            file_pattern="*.py",
        )


def test_replace_in_files_expected_replacements_guard(write_enabled, tree_snapshot):
    root = write_enabled
    before = tree_snapshot(root)

    # Wrong expected count
    with pytest.raises(ValueError, match="Total replacements count mismatch"):
        replace_service.replace_in_files(
            str(root),
            find="old_name",
            replace="new_name",
            file_pattern="*.py",
            expected_replacements=999,
            dry_run=False,
        )
    assert tree_snapshot(root) == before

    # Correct expected count
    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="src/util.py",
        expected_replacements=1,
        dry_run=False,
    )
    assert out.total_replacements == 1
    assert (root / "src/util.py").read_text(encoding="utf-8") == "def helper():\n    return 'new_name'\n"


def test_replace_in_files_max_files_exceeded(write_enabled, monkeypatch):
    root = write_enabled
    monkeypatch.setattr(config, "MAX_FILES_PER_REPLACE", 1)

    with pytest.raises(write_guard.FileTooLargeError, match="MAX_FILES_PER_REPLACE"):
        replace_service.replace_in_files(
            str(root),
            find="old_name",
            replace="new_name",
            file_pattern="*.*",
            dry_run=True,
        )


def test_replace_in_files_preserves_crlf(write_enabled):
    root = write_enabled
    (root / "test_crlf.txt").write_bytes(b"hello old_name\r\nworld old_name\r\n")

    out = replace_service.replace_in_files(
        str(root),
        find="old_name",
        replace="new_name",
        file_pattern="test_crlf.txt",
        dry_run=False,
    )

    assert out.total_replacements == 2
    raw = (root / "test_crlf.txt").read_bytes()
    assert b"\r\n" in raw
    assert raw == b"hello new_name\r\nworld new_name\r\n"


def test_replace_in_files_changed_since_scan(write_enabled, monkeypatch):
    root = write_enabled
    # Prepare 2 files matching pattern
    (root / "src/f1.py").write_text("target_word\n", encoding="utf-8")
    (root / "src/f2.py").write_text("target_word\n", encoding="utf-8")

    original_atomic = file_writer.atomic_write_bytes

    def fake_atomic_write(target, data):
        # When f1.py is being written, mutate f2.py in background
        if target.name == "f1.py":
            (root / "src/f2.py").write_text("target_word changed externally\n", encoding="utf-8")
        return original_atomic(target, data)

    monkeypatch.setattr(file_writer, "atomic_write_bytes", fake_atomic_write)

    out = replace_service.replace_in_files(
        str(root),
        find="target_word",
        replace="new_word",
        file_pattern="src/f*.py",
        dry_run=False,
    )

    # f1 succeeded, f2 skipped because it changed since scan
    assert out.files_changed == 1
    skipped_reasons = {s["file_path"]: s["reason"] for s in out.skipped}
    assert "src/f2.py" in skipped_reasons
    assert skipped_reasons["src/f2.py"] == "changed since scan"
    assert (root / "src/f2.py").read_text(encoding="utf-8") == "target_word changed externally\n"


def test_replace_in_files_partial_failure(write_enabled, monkeypatch):
    root = write_enabled
    (root / "src/f1.py").write_text("replace_target\n", encoding="utf-8")
    (root / "src/f2.py").write_text("replace_target\n", encoding="utf-8")
    (root / "src/f3.py").write_text("replace_target\n", encoding="utf-8")

    original_atomic = file_writer.atomic_write_bytes

    def fail_on_second(target, data):
        if target.name == "f2.py":
            raise OSError("Simulated disk error on f2")
        return original_atomic(target, data)

    monkeypatch.setattr(file_writer, "atomic_write_bytes", fail_on_second)

    out = replace_service.replace_in_files(
        str(root),
        find="replace_target",
        replace="replaced",
        file_pattern="src/f*.py",
        dry_run=False,
    )

    assert out.partial is True
    assert out.files_changed == 1
    assert (root / "src/f1.py").read_text(encoding="utf-8") == "replaced\n"
    # f3 was not attempted
    skipped_reasons = {s["file_path"]: s["reason"] for s in out.skipped}
    assert "src/f3.py" in skipped_reasons
    assert "not attempted" in skipped_reasons["src/f3.py"]


def test_replace_in_files_gate_disabled(project, monkeypatch, tree_snapshot):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    before = tree_snapshot(project)

    with pytest.raises(write_guard.WriteDisabledError):
        replace_service.replace_in_files(
            str(project),
            find="old_name",
            replace="new_name",
            file_pattern="*.py",
        )
    assert tree_snapshot(project) == before
