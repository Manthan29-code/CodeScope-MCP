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

    assert "list_directory_tree" in names
    assert "get_file_metadata" in names
    assert "read_file" in names
    assert "read_multiple_files" in names
    assert "search_files" in names
    assert "write_file" not in names
    assert "edit_file" not in names


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
    tools_dict = {t.name: t for t in tools}

    assert "list_directory_tree" in names
    assert "write_file" in names
    assert "edit_file" in names
