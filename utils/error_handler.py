"""Centralized error handling and debugging helper for CodeScope MCP tools."""
from __future__ import annotations

import functools
import inspect
import traceback
from typing import Any, Callable, Dict, Optional

from utils.logger import logger


def format_tool_error(exc: Exception, tool_name: str = "") -> Dict[str, Any]:
    """Classify an exception into a structured error dictionary with an actionable hint."""
    exc_type = type(exc).__name__
    msg = str(exc).strip() or exc_type

    # Classify error type and provide actionable hint
    if "protectedpatherror" in exc_type.lower() or "protected by safety rules" in msg.lower() or "contains protected" in msg.lower():
        error_type = "ProtectedPathError"
        hint = "Access denied: the target path matches protected files or patterns (.git, .env, keys, config) and cannot be modified."
    elif "ignoredpatherror" in exc_type.lower() or "is ignored" in msg.lower():
        error_type = "IgnoredPathError"
        hint = "Access denied: the target path matches .gitignore or default ignore patterns."
    elif "editmatcherror" in exc_type.lower() or "old_string" in msg.lower():
        error_type = "EditMatchError"
        hint = "The old_string was not found or was not unique in the target file. Check whitespace and exact indentation, or add more surrounding context lines."
    elif "stalefileerror" in exc_type.lower() or "hash mismatch" in msg.lower():
        error_type = "StaleFileError"
        hint = "The file content changed since it was read. Call read_file again to fetch the latest content and SHA-256 hash before modifying."
    elif "filetoolargeerror" in exc_type.lower() or "max_write_size_bytes" in msg.lower():
        error_type = "FileTooLargeError"
        hint = "The write content exceeds MAX_WRITE_SIZE_BYTES. Break the content into smaller files or use edit_file for partial edits."
    elif "READ_ALLOWED_ROOTS" in msg or "WRITE_ALLOWED_ROOTS" in msg or "Access denied" in msg or "RootNotAllowedError" in exc_type:
        error_type = "AccessDeniedError"
        hint = (
            "The requested project_path is outside the configured allowed roots. "
            "Ensure the path is approved in .env (ALLOWED_PROJECT_ROOTS, READ_ALLOWED_ROOTS, or WRITE_ALLOWED_ROOTS)."
        )
    elif "writedisablederror" in exc_type.lower() or "write operations are disabled" in msg.lower():
        error_type = "WriteDisabledError"
        hint = "Write operations are disabled on the server. Set ENABLE_WRITE_TOOLS=true in the server configuration to enable file modifications."
    elif "binaryfileerror" in exc_type.lower() or "binary file" in msg.lower() or "null bytes" in msg.lower():
        error_type = "BinaryFileError"
        hint = "Cannot perform text operations on binary files. CodeScope text tools only operate on valid text files."
    elif isinstance(exc, FileExistsError) or "file already exists" in msg.lower() or "destination file already exists" in msg.lower():
        error_type = "FileExistsError"
        hint = "The target file already exists. Set overwrite=True in write_file to replace it, or use edit_file for partial modifications."
    elif "does not exist" in msg.lower() or "not found" in msg.lower() or isinstance(exc, FileNotFoundError):
        error_type = "PathNotFoundError"
        hint = "The specified path does not exist on the local filesystem. Verify that the directory or file exists and the path is spelled correctly."
    elif "not inside a git repository" in msg.lower() or "not a git repository" in msg.lower():
        error_type = "GitNotRepositoryError"
        hint = "The target directory is not an initialized Git repository. Initialize git in that folder or verify that project_path points to the repository root."
    elif "uncommitted changes" in msg.lower() or "clean_tracked" in msg.lower():
        error_type = "DirtyWorkingTreeError"
        hint = (
            "The repository has uncommitted changes to tracked files. "
            "To switch branches or merge safely, either commit the changes, run git_restore "
            "to discard the uncommitted changes, or run git_status() to inspect them."
        )
    elif "conflict" in msg.lower() or "merge failed" in msg.lower():
        error_type = "MergeConflictError"
        hint = "The merge resulted in conflicts and was automatically aborted. The repository remains clean and unchanged."
    elif "branch" in msg.lower() and "already exists" in msg.lower():
        error_type = "BranchAlreadyExistsError"
        hint = "A branch with that name already exists. Choose a different name or switch to it using git_switch()."
    elif "unknown or expired action_id" in msg.lower():
        error_type = "ExpiredApprovalError"
        hint = "The approval request has expired or action_id is invalid. Re-request the dangerous action to receive a fresh approval code."
    elif "invalid approval code" in msg.lower():
        error_type = "InvalidApprovalCodeError"
        hint = "The 6-digit approval code was incorrect. Obtain the exact code displayed on the server console."
    elif "project_path is required" in msg.lower():
        error_type = "MissingArgumentError"
        hint = "Always pass an explicit absolute or relative project_path (e.g. 'C:/MyProject/codescope-sandbox'). Never run tools without specifying project_path."
    elif "approval" in msg.lower() or "approvalerror" in exc_type.lower():
        error_type = "ApprovalError"
        hint = "This action requires human confirmation. Show the preview to the user and request the 6-digit approval code displayed on the server console."
    elif "verification" in msg.lower():
        error_type = "VerificationError"
        hint = "Verification check failed or configuration is invalid. Run list_checks() to see all configured verification checks."
    elif isinstance(exc, PermissionError):
        error_type = "PermissionError"
        hint = "Operating system permission denied or attempting to modify a protected/ignored file."
    elif isinstance(exc, ValueError):
        error_type = "InvalidInputError"
        hint = "Check the arguments provided to this tool."
    else:
        error_type = exc_type
        hint = "An unexpected error occurred. Review the error message for details."

    return {
        "ok": False,
        "error": msg,
        "error_type": error_type,
        "hint": hint,
    }


_EXPECTED_ERROR_NAMES = {
    "GitError",
    "ApprovalError",
    "VerificationError",
    "ValueError",
    "PermissionError",
    "ReadRootNotAllowedError",
    "RootNotAllowedError",
    "WriteDisabledError",
    "WriteError",
    "EditMatchError",
    "FileTooLargeError",
    "BinaryFileError",
    "StaleFileError",
    "FileExistsError",
    "ProtectedPathError",
    "IgnoredPathError",
    "FileNotFoundError",
    "ExecutableNotFound",
}


def _log_tool_exception(name: str, exc: Exception, kwargs: dict) -> None:
    exc_type = type(exc).__name__
    is_expected = exc_type in _EXPECTED_ERROR_NAMES or isinstance(
        exc, (ValueError, PermissionError, FileNotFoundError, FileExistsError)
    )
    # Sanitize arguments: truncate long strings or remove sensitive keys if any
    safe_kwargs = {k: (str(v)[:100] + "..." if isinstance(v, str) and len(v) > 100 else v) for k, v in kwargs.items()}

    if is_expected:
        logger.warning(f"Tool '{name}' rejected request: [{exc_type}] {exc} (Args: {safe_kwargs})")
    else:
        logger.error(
            f"Tool '{name}' unexpected failure: [{exc_type}] {exc}\n"
            f"  Arguments: {safe_kwargs}\n"
            f"  Traceback:\n{traceback.format_exc()}"
        )


def handle_tool_errors(tool_name: Optional[str] = None):
    """
    Decorator for MCP tools providing centralized logging to server console
    and returning a structured error response to the LLM.
    """
    def decorator(fn: Callable) -> Callable:
        name = tool_name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                _log_tool_exception(name, exc, kwargs)
                return format_tool_error(exc, name)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                _log_tool_exception(name, exc, kwargs)
                return format_tool_error(exc, name)

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

    return decorator
