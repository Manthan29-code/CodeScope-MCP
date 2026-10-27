"""MCP tool registration for automated verification."""
from __future__ import annotations

import functools
from typing import List, Optional

from fastmcp import FastMCP

import config
from core.path_security import ReadRootNotAllowedError, verify_read_root
from services.verification_service import VerificationError, VerificationService
from utils.process_runner import ExecutableNotFound

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
EXECUTE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}

_HANDLED = (VerificationError, ValueError, PermissionError, ReadRootNotAllowedError, ExecutableNotFound)


def _guard(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except _HANDLED as exc:
            return {"ok": False, "error": str(exc)}
    return wrapper


def _get_verification_service(
    project_path: str = ".",
    default_verifier: Optional[VerificationService] = None,
) -> VerificationService:
    """Resolve and validate project_path against READ_ALLOWED_ROOTS, returning a VerificationService for it."""
    target_root = verify_read_root(project_path)
    if default_verifier and target_root == default_verifier.root:
        return default_verifier

    config_filename = default_verifier.config_filename if default_verifier else config.VERIFY_CONFIG_FILENAME
    autodetect = default_verifier.autodetect if default_verifier else config.VERIFY_AUTODETECT
    default_timeout = default_verifier.default_timeout if default_verifier else config.VERIFY_DEFAULT_TIMEOUT_SECONDS
    max_output_chars = default_verifier.max_output_chars if default_verifier else config.VERIFY_MAX_OUTPUT_CHARS

    return VerificationService(
        target_root,
        config_filename=config_filename,
        autodetect=autodetect,
        default_timeout=default_timeout,
        max_output_chars=max_output_chars,
    )


async def attach_verification(result: dict, verifier: VerificationService, names: Optional[List[str]]) -> dict:
    """Helper for the file-write tools: run the named checks after a successful edit."""
    if names and result.get("ok", True):
        summary = await verifier.run_many(names, stop_on_failure=True)
        result["verification"] = summary.model_dump()
    return result


def register_verify_tools(mcp: FastMCP, verifier: VerificationService) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def list_checks(project_path: str = ".") -> dict:
        """List the build/lint/test checks you are allowed to run (from .codescope.toml or auto-detected) in target project.
        
        Args:
            project_path: Absolute or relative path to project root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        svc = _get_verification_service(project_path, default_verifier=verifier)
        checks = svc.load_checks()
        return {"ok": True, "checks": [
            {"name": c.name, "command": " ".join(c.cmd), "description": c.description,
             "timeout": c.timeout, "source": c.source} for c in checks.values()]}

    @mcp.tool(annotations=EXECUTE)
    @_guard
    async def run_check(name: str, project_path: str = ".") -> dict:
        """Run ONE named check (for example lint, test or build) in target project. Only configured checks can run;
        arbitrary commands are not possible. Returns pass/fail plus the head and tail of the output.
        
        Args:
            name: Name of the check to run (e.g. "test", "lint", "build").
            project_path: Absolute or relative path to project root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        svc = _get_verification_service(project_path, default_verifier=verifier)
        return {"ok": True, **(await svc.run_check(name)).model_dump()}

    @mcp.tool(annotations=EXECUTE)
    @_guard
    async def run_all_checks(names: Optional[List[str]] = None, stop_on_failure: bool = False,
                             project_path: str = ".") -> dict:
        """Run several configured checks in target project (all of them if names is omitted).
        
        Args:
            names: Optional subset of check names to run in order.
            stop_on_failure: If true, stops at the first failing check.
            project_path: Absolute or relative path to project root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        svc = _get_verification_service(project_path, default_verifier=verifier)
        return {"ok": True, **(await svc.run_many(names, stop_on_failure)).model_dump()}
