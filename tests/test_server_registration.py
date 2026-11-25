import asyncio
import importlib
import pytest
import config
from core.write_guard import WriteDisabledError
from services.git_service import GitDisabledError
from services.verification_service import VerificationDisabledError
from tools.write_file_tool import write_file
from tools.git_tools import _get_git_service
from tools.verify_tools import _get_verification_service
from tools.file_metadata_tool import get_file_metadata


def test_server_all_tools_registered():
    import server
    importlib.reload(server)

    comp_names = {getattr(c, "name", "") for c in server.mcp._local_provider._components.values() if hasattr(c, "name")}

    expected_read = {
        "list_directory_tree",
        "get_file_metadata",
        "read_file",
        "read_multiple_files",
        "search_files",
    }
    expected_write = {
        "write_file",
        "edit_file",
        "delete_file",
        "move_file",
        "copy_file",
        "replace_in_files",
    }
    expected_git = {
        "git_status",
        "git_diff",
        "git_log",
        "git_show",
        "git_branch_list",
        "git_branch_create",
        "git_switch",
        "git_merge",
        "git_revert",
        "git_restore",
        "git_commit",
        "git_push",
        "confirm_action",
    }
    expected_verify = {
        "list_checks",
        "run_check",
        "run_all_checks",
    }

    assert expected_read.issubset(comp_names)
    assert expected_write.issubset(comp_names)
    assert expected_git.issubset(comp_names)
    assert expected_verify.issubset(comp_names)


def test_server_tool_annotations():
    import server
    importlib.reload(server)

    comps = {getattr(c, "name", ""): c for c in server.mcp._local_provider._components.values() if hasattr(c, "name")}

    # Read tools must advertise readOnlyHint=True, destructiveHint=False
    for name in ["read_file", "search_files", "list_directory_tree", "get_file_metadata"]:
        ann = getattr(comps[name], "annotations", None)
        assert ann is not None, f"Tool '{name}' must have annotations"
        assert getattr(ann, "readOnlyHint", None) is True
        assert getattr(ann, "destructiveHint", None) is False

    # Write tools must advertise readOnlyHint=False, destructiveHint=True
    for name in ["write_file", "edit_file", "delete_file", "move_file", "replace_in_files"]:
        ann = getattr(comps[name], "annotations", None)
        assert ann is not None, f"Tool '{name}' must have annotations"
        assert getattr(ann, "readOnlyHint", None) is False
        assert getattr(ann, "destructiveHint", None) is True

    # Destructive git tools must advertise destructiveHint=True
    for name in ["git_commit", "git_push", "git_merge", "git_restore", "git_revert"]:
        ann = getattr(comps[name], "annotations", None)
        assert ann is not None, f"Tool '{name}' must have annotations"
        assert getattr(ann, "readOnlyHint", None) is False
        assert getattr(ann, "destructiveHint", None) is True


def test_runtime_gate_write_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(tmp_path)])

    res = write_file("test.txt", "content", project_path=str(tmp_path))
    assert res["ok"] is False
    assert res.get("error_type") == "WriteDisabledError" or "disabled" in str(res.get("error")).lower()


def test_runtime_gate_git_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", False)
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(tmp_path)])

    with pytest.raises(GitDisabledError, match="Git operations are disabled"):
        _get_git_service(str(tmp_path), for_write=False)


def test_runtime_gate_verification_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", False)
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(tmp_path)])

    with pytest.raises(VerificationDisabledError, match="Automated verification tools are disabled"):
        _get_verification_service(str(tmp_path))


def test_get_file_metadata_error_handling(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(tmp_path)])

    # Non-existent file
    res = get_file_metadata("does_not_exist.txt", project_path=str(tmp_path))
    assert isinstance(res, dict)
    assert res["ok"] is False
    assert "File not found" in res["error"]
    assert res["error_type"] == "PathNotFoundError"

    # Empty file_path
    res_empty = get_file_metadata("", project_path=str(tmp_path))
    assert isinstance(res_empty, dict)
    assert res_empty["ok"] is False
    assert res_empty["error_type"] in ("InvalidInputError", "PathNotFoundError")
