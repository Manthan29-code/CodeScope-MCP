"""MCP tool registration for git. Business logic lives in services/git_service.py."""
from __future__ import annotations

import functools
import logging
from typing import List, Optional

from fastmcp import Context, FastMCP

import config
from core.path_security import ReadRootNotAllowedError, verify_read_root
from core.safety import ProtectedPathError
from core.write_guard import RootNotAllowedError, WriteDisabledError, WriteError, begin_write
from services.confirmation_service import ApprovalError, ApprovalGate
from services.git_service import GitError, GitService
from utils.process_runner import ExecutableNotFound

audit = logging.getLogger("codescope.audit")

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
LOW_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}

from utils.error_handler import handle_tool_errors

_guard = handle_tool_errors()


def _get_git_service(
    project_path: str = ".",
    for_write: bool = False,
    default_git: Optional[GitService] = None,
) -> GitService:
    """Resolve and validate project_path against security roots, returning a GitService for it."""
    if for_write:
        target_root = begin_write(project_path)
    else:
        target_root = verify_read_root(project_path)

    if default_git and target_root == default_git.root:
        return default_git

    timeout = default_git.timeout if default_git else config.GIT_COMMAND_TIMEOUT_SECONDS
    max_diff_lines = default_git.max_diff_lines if default_git else config.GIT_MAX_DIFF_LINES
    block_ignored = default_git.block_ignored if default_git else config.BLOCK_WRITES_TO_IGNORED

    return GitService(
        target_root,
        timeout=timeout,
        max_diff_lines=max_diff_lines,
        block_ignored=block_ignored,
    )


def register_git_tools(mcp: FastMCP, git: GitService, gate: ApprovalGate, *, enable_write_tools: bool) -> None:

    # ------------------------------------------------------------ READ (no approval)
    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_status(project_path: str = ".") -> dict:
        """Show current branch, upstream, ahead/behind and changed or untracked files in the target repository. Read-only.
        
        Args:
            project_path: Absolute or relative path to target repository root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=False, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, **(await git_target.status()).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_diff(path: Optional[str] = None, staged: bool = False,
                       base: Optional[str] = None, max_lines: int = 500,
                       project_path: str = ".") -> dict:
        """Show a diff of the working tree (or staged changes, or against a base revision) in the target repository. Read-only.
        
        Args:
            path: Optional relative path to limit diff to.
            staged: Show staged changes if true, unstaged if false.
            base: Base commit/revision to diff against.
            max_lines: Maximum diff lines to return.
            project_path: Absolute or relative path to target repository root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=False, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, **(await git_target.diff(path, staged, base, max_lines)).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_log(limit: int = 20, path: Optional[str] = None, rev: Optional[str] = None,
                      project_path: str = ".") -> dict:
        """List recent commits (max 200), optionally for one path or starting from a revision in target repository. Read-only.
        
        Args:
            limit: Number of commits to retrieve (max 200).
            path: Optional relative path to filter commits by.
            rev: Starting revision/commit.
            project_path: Absolute or relative path to target repository root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=False, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, "commits": [c.model_dump() for c in await git_target.log(limit, path, rev)]}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_show(rev: str = "HEAD", max_lines: int = 500, project_path: str = ".") -> dict:
        """Show one commit with its stats and patch in target repository. Read-only.
        
        Args:
            rev: Revision/commit to show (default "HEAD").
            max_lines: Maximum patch lines to return.
            project_path: Absolute or relative path to target repository root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=False, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, **(await git_target.show(rev, max_lines)).model_dump()}

    @mcp.tool(annotations=READ_ONLY)
    @_guard
    async def git_branch_list(project_path: str = ".") -> dict:
        """List local branches and mark the current one in target repository. Read-only.
        
        Args:
            project_path: Absolute or relative path to target repository root (default "."). Must be within READ_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=False, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, "branches": [b.model_dump() for b in await git_target.branches()]}

    if not enable_write_tools:
        return

    # ------------------------------------------------------------ LOW_WRITE (no approval)
    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_branch_create(name: str, start_point: Optional[str] = None, checkout: bool = False,
                              project_path: str = ".") -> dict:
        """Create a local branch (optionally switching to it) in target repository. Does not modify any files unless checkout=true.
        
        Args:
            name: New branch name.
            start_point: Optional starting commit or branch.
            checkout: If true, switches to the new branch immediately.
            project_path: Absolute or relative path to target repository root (default "."). Must be within WRITE_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, **(await git_target.create_branch(name, start_point, checkout)).model_dump()}

    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_create_branch(name: str, start_point: Optional[str] = None, checkout: bool = False,
                              project_path: str = ".") -> dict:
        """Alias for git_branch_create. Create a local branch (optionally switching to it) in target repository."""
        return await git_branch_create(name=name, start_point=start_point, checkout=checkout, project_path=project_path)

    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_switch(branch: str, project_path: str = ".") -> dict:
        """Switch to an existing local branch in target repository. Refuses if tracked files have uncommitted changes.
        
        Args:
            branch: Existing branch name to switch to.
            project_path: Absolute or relative path to target repository root (default "."). Must be within WRITE_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        return {"ok": True, **(await git_target.switch(branch)).model_dump()}

    @mcp.tool(annotations=LOW_WRITE)
    @_guard
    async def git_checkout(branch: str, project_path: str = ".") -> dict:
        """Alias for git_switch. Switch to an existing local branch in target repository."""
        return await git_switch(branch=branch, project_path=project_path)

    # ------------------------------------------------------------ DANGEROUS (approval required)
    async def _run_gated(ctx: Optional[Context], git_target: GitService, prepared) -> dict:
        outcome = await gate.gate(
            ctx,
            tool=prepared.tool,
            args=prepared.args,
            summary=prepared.summary,
            preview=prepared.preview,
            fingerprint=prepared.fingerprint,
            project_path=str(git_target.root),
        )
        if outcome.status == "approved":
            result = await git_target.execute(prepared.tool, prepared.args)
            audit.warning("executed %s %s in %s", prepared.tool, prepared.args, git_target.root)
            return {"ok": True, **result.model_dump()}
        return outcome.payload or {"ok": False, "error": "Not approved"}

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_merge(branch: str, ctx: Context, project_path: str = ".") -> dict:
        """DANGEROUS. Merge a local branch into the current branch with a merge commit in target repository.
        The user must approve. You will get a preview. Show it to the user and wait for their
        approval. Never call confirm_action unless the user gave you the approval code.
        
        Args:
            branch: Branch to merge into current HEAD.
            ctx: FastMCP context for approval elicitation.
            project_path: Absolute or relative path to target repository root (default "."). Must be within WRITE_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        prepared = await git_target.prepare_merge(branch)
        prepared.args["project_path"] = str(git_target.root)
        return await _run_gated(ctx, git_target, prepared)

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_revert(commit: str, ctx: Context, project_path: str = ".") -> dict:
        """DANGEROUS. Create a new commit that undoes an earlier commit (merge commits unsupported) in target repository.
        The user must approve. Show the preview to the user and wait for their approval.
        
        Args:
            commit: Commit SHA or revision to revert.
            ctx: FastMCP context for approval elicitation.
            project_path: Absolute or relative path to target repository root (default "."). Must be within WRITE_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        prepared = await git_target.prepare_revert(commit)
        prepared.args["project_path"] = str(git_target.root)
        return await _run_gated(ctx, git_target, prepared)

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def git_restore(paths: List[str], ctx: Context, project_path: str = ".") -> dict:
        """DANGEROUS. Permanently discard uncommitted changes (staged and unstaged) in the given
        paths, resetting them to HEAD in target repository. A recovery point is saved first. The user must approve.
        
        Args:
            paths: List of relative file paths to restore.
            ctx: FastMCP context for approval elicitation.
            project_path: Absolute or relative path to target repository root (default "."). Must be within WRITE_ALLOWED_ROOTS.
        """
        git_target = _get_git_service(project_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        prepared = await git_target.prepare_restore(paths)
        prepared.args["project_path"] = str(git_target.root)
        return await _run_gated(ctx, git_target, prepared)

    @mcp.tool(annotations=DESTRUCTIVE)
    @_guard
    async def confirm_action(action_id: str, approval_code: str, project_path: Optional[str] = None) -> dict:
        """Execute a previewed dangerous git action. approval_code is shown ONLY on the CodeScope
        server console and must come from the user. Never guess or invent it.
        
        Args:
            action_id: Action ID received from preview.
            approval_code: 6-digit code shown on the server console.
            project_path: Optional project path (if omitted, uses the repository targeted during preview).
        """
        pending = gate.service.peek(action_id)
        target_path = project_path or getattr(pending, "project_path", None) or pending.args.get("project_path", ".")
        git_target = _get_git_service(target_path, for_write=True, default_git=git)
        await git_target.ensure_repo()
        current = (await git_target.prepare(pending.tool, pending.args)).fingerprint
        action = gate.service.consume(action_id, approval_code, current)
        result = await git_target.execute(action.tool, action.args)
        audit.warning("executed %s %s (approved by code) in %s", action.tool, action.args, git_target.root)
        return {"ok": True, **result.model_dump()}
