"""MCP tool registration for git. Business logic lives in services/git_service.py."""
from __future__ import annotations

import functools
import logging
from typing import List, Optional

from fastmcp import Context, FastMCP

from services.confirmation_service import ApprovalError, ApprovalGate
from services.git_service import GitError, GitService
from core.safety import ProtectedPathError
from utils.process_runner import ExecutableNotFound

audit = logging.getLogger("codescope.audit")

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
LOW_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}

_HANDLED = (GitError, ValueError, PermissionError, ProtectedPathError, ApprovalError, ExecutableNotFound)


def _guard(fn):
    """Turn expected errors into a clean {"ok": False, "error": ...} result."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except _HANDLED as exc:
            return {"ok": False, "error": str(exc)}
    return wrapper


def register_git_tools(mcp: FastMCP, git: GitService, gate: ApprovalGate, *, enable_write_tools: bool) -> None:

    # ------------------------------------------------------------ READ (no approval)
    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_status() -> dict:
        """Show current branch, upstream, ahead/behind and changed or untracked files. Read-only."""
        await git.ensure_repo()
        return {"ok": True, **(await git.status()).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_diff(path: Optional[str] = None, staged: bool = False,
                       base: Optional[str] = None, max_lines: int = 500) -> dict:
        """Show a diff of the working tree (or staged changes, or against a base revision). Read-only."""
        await git.ensure_repo()
        return {"ok": True, **(await git.diff(path, staged, base, max_lines)).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_log(limit: int = 20, path: Optional[str] = None, rev: Optional[str] = None) -> dict:
        """List recent commits (max 200), optionally for one path or starting from a revision. Read-only."""
        await git.ensure_repo()
        return {"ok": True, "commits": [c.model_dump() for c in await git.log(limit, path, rev)]}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_show(rev: str = "HEAD", max_lines: int = 500) -> dict:
        """Show one commit with its stats and patch. Read-only."""
        await git.ensure_repo()
        return {"ok": True, **(await git.show(rev, max_lines)).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_branch_list() -> dict:
        """List local branches and mark the current one. Read-only."""
        await git.ensure_repo()
        return {"ok": True, "branches": [b.model_dump() for b in await git.branches()]}

    if not enable_write_tools:
        return

    # ------------------------------------------------------------ LOW_WRITE (no approval)
    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_branch_create(name: str, start_point: Optional[str] = None, checkout: bool = False) -> dict:
        """Create a local branch (optionally switching to it). Does not modify any files unless checkout=true."""
        await git.ensure_repo()
        return {"ok": True, **(await git.create_branch(name, start_point, checkout)).model_dump()}

    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_switch(branch: str) -> dict:
        """Switch to an existing local branch. Refuses if tracked files have uncommitted changes."""
        await git.ensure_repo()
        return {"ok": True, **(await git.switch(branch)).model_dump()}

    # ------------------------------------------------------------ DANGEROUS (approval required)
    async def _run_gated(ctx: Optional[Context], prepared) -> dict:
        outcome = await gate.gate(ctx, tool=prepared.tool, args=prepared.args, summary=prepared.summary,
                                  preview=prepared.preview, fingerprint=prepared.fingerprint)
        if outcome.status == "approved":
            result = await git.execute(prepared.tool, prepared.args)
            audit.warning("executed %s %s", prepared.tool, prepared.args)
            return {"ok": True, **result.model_dump()}
        return outcome.payload or {"ok": False, "error": "Not approved"}

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_merge(branch: str, ctx: Context) -> dict:
        """DANGEROUS. Merge a local branch into the current branch with a merge commit.
        The user must approve. You will get a preview. Show it to the user and wait for their
        approval. Never call confirm_action unless the user gave you the approval code."""
        await git.ensure_repo()
        return await _run_gated(ctx, await git.prepare_merge(branch))

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_revert(commit: str, ctx: Context) -> dict:
        """DANGEROUS. Create a new commit that undoes an earlier commit (merge commits unsupported).
        The user must approve. Show the preview to the user and wait for their approval."""
        await git.ensure_repo()
        return await _run_gated(ctx, await git.prepare_revert(commit))

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_restore(paths: List[str], ctx: Context) -> dict:
        """DANGEROUS. Permanently discard uncommitted changes (staged and unstaged) in the given
        paths, resetting them to HEAD. A recovery point is saved first. The user must approve."""
        await git.ensure_repo()
        return await _run_gated(ctx, await git.prepare_restore(paths))

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def confirm_action(action_id: str, approval_code: str) -> dict:
        """Execute a previewed dangerous git action. approval_code is shown ONLY on the CodeScope
        server console and must come from the user. Never guess or invent it."""
        await git.ensure_repo()
        pending = gate.service.peek(action_id)
        current = (await git.prepare(pending.tool, pending.args)).fingerprint
        action = gate.service.consume(action_id, approval_code, current)
        result = await git.execute(action.tool, action.args)
        audit.warning("executed %s %s (approved by code)", action.tool, action.args)
        return {"ok": True, **result.model_dump()}
