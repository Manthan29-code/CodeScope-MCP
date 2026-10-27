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
    if "READ_ALLOWED_ROOTS" in msg or "WRITE_ALLOWED_ROOTS" in msg or "Access denied" in msg or "RootNotAllowedError" in exc_type:
        error_type = "AccessDeniedError"
        hint = (
            "The requested project_path is outside the configured allowed roots. "
            "Ensure the path is approved in .env (ALLOWED_PROJECT_ROOTS, READ_ALLOWED_ROOTS, or WRITE_ALLOWED_ROOTS)."
        )
    elif "does not exist" in msg.lower() or "not found" in msg.lower() or isinstance(exc, FileNotFoundError):
        error_type = "PathNotFoundError"
        hint = "The specified path does not exist on the local filesystem. Verify that the directory or file exists and the path is spelled correctly."
    elif "not inside a git repository" in msg.lower() or "not a git repository" in msg.lower():
        error_type = "GitNotRepositoryError"
        hint = "The target directory is not an initialized Git repository. Initialize git in that folder or verify that project_path points to the repository root."
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
                logger.error(
                    f"Tool '{name}' failed: [{type(exc).__name__}] {exc}\n"
                    f"  Arguments: {kwargs}\n"
                    f"  Traceback:\n{traceback.format_exc()}"
                )
                return format_tool_error(exc, name)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    f"Tool '{name}' failed: [{type(exc).__name__}] {exc}\n"
                    f"  Arguments: {kwargs}\n"
                    f"  Traceback:\n{traceback.format_exc()}"
                )
                return format_tool_error(exc, name)

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

    return decorator
