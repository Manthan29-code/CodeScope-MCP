import asyncio
import importlib
import pytest
import config


def test_server_registration_gate_off(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", False)
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", False)
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

    expected_read_tools = {
        "list_directory_tree",
        "get_file_metadata",
        "read_file",
        "read_multiple_files",
        "search_files",
    }
    assert names == expected_read_tools


def test_server_registration_gate_on(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", False)
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", False)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", ["/dummy/allowed"])
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

    expected_all_tools = {
        "list_directory_tree",
        "get_file_metadata",
        "read_file",
        "read_multiple_files",
        "search_files",
        "write_file",
        "edit_file",
        "delete_file",
        "move_file",
        "copy_file",
        "replace_in_files",
    }
    assert names == expected_all_tools


def test_server_registration_git_read_only(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", False)
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

    git_read_tools = {
        "git_status",
        "git_diff",
        "git_log",
        "git_show",
        "git_branch_list",
    }
    assert git_read_tools.issubset(names)
    assert "git_branch_create" not in names
    assert "git_merge" not in names


def test_server_registration_git_with_write(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", False)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", ["/dummy/allowed"])
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

    all_git_tools = {
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
        "confirm_action",
    }
    assert all_git_tools.issubset(names)


def test_server_registration_verification_tools(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", False)
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

    verify_tools = {"list_checks", "run_check", "run_all_checks"}
    assert verify_tools.issubset(names)
    assert "git_status" not in names
    assert "write_file" not in names


def test_server_registration_all_enabled(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_GIT_TOOLS", True)
    monkeypatch.setattr(config, "ENABLE_VERIFICATION_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", ["/dummy/allowed"])
    import server
    importlib.reload(server)

    from fastmcp import Client

    async def _get_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(_get_tools())
    names = {t.name for t in tools}

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
        "confirm_action",
    }
    expected_verify = {
        "list_checks",
        "run_check",
        "run_all_checks",
    }
    assert names == (expected_read | expected_write | expected_git | expected_verify)
