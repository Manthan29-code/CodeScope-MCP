import asyncio
import importlib
import pytest
import config


def test_server_registration_gate_off(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", False)
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

