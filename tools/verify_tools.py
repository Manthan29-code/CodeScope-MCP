"""MCP tool registration for automated verification."""
from __future__ import annotations

import functools
from typing import List, Optional

from fastmcp import FastMCP

from services.verification_service import VerificationError, VerificationService

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
EXECUTE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}


def _guard(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except (VerificationError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
    return wrapper


async def attach_verification(result: dict, verifier: VerificationService, names: Optional[List[str]]) -> dict:
    """Helper for the file-write tools: run the named checks after a successful edit."""
    if names and result.get("ok", True):
        summary = await verifier.run_many(names, stop_on_failure=True)
        result["verification"] = summary.model_dump()
    return result


def register_verify_tools(mcp: FastMCP, verifier: VerificationService) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def list_checks() -> dict:
        """List the build/lint/test checks you are allowed to run (from .codescope.toml or auto-detected)."""
        checks = verifier.load_checks()
        return {"ok": True, "checks": [
            {"name": c.name, "command": " ".join(c.cmd), "description": c.description,
             "timeout": c.timeout, "source": c.source} for c in checks.values()]}

    @mcp.tool(annotations=EXECUTE)
    @_guard
    async def run_check(name: str) -> dict:
        """Run ONE named check (for example lint, test or build). Only configured checks can run;
        arbitrary commands are not possible. Returns pass/fail plus the head and tail of the output."""
        return {"ok": True, **(await verifier.run_check(name)).model_dump()}

    @mcp.tool(annotations=EXECUTE)
    @_guard
    async def run_all_checks(names: Optional[List[str]] = None, stop_on_failure: bool = False) -> dict:
        """Run several configured checks (all of them if names is omitted)."""
        return {"ok": True, **(await verifier.run_many(names, stop_on_failure)).model_dump()}
