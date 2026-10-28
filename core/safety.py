"""Risk tiers, tool-enable rules and protected paths."""
from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Dict


class Risk(str, Enum):
    READ = "read"
    LOW_WRITE = "low_write"
    DANGEROUS = "dangerous"
    EXECUTE = "execute"


TOOL_RISK: Dict[str, Risk] = {
    "git_status": Risk.READ,
    "git_diff": Risk.READ,
    "git_log": Risk.READ,
    "git_show": Risk.READ,
    "git_branch_list": Risk.READ,
    "git_branch_create": Risk.LOW_WRITE,
    "git_switch": Risk.LOW_WRITE,
    "git_merge": Risk.DANGEROUS,
    "git_revert": Risk.DANGEROUS,
    "git_restore": Risk.DANGEROUS,
    "git_commit": Risk.DANGEROUS,
    "git_push": Risk.DANGEROUS,
    "confirm_action": Risk.DANGEROUS,
    "list_checks": Risk.READ,
    "run_check": Risk.EXECUTE,
    "run_all_checks": Risk.EXECUTE,
}


def tool_enabled(tool: str, *, enable_git: bool, enable_write: bool, enable_verify: bool) -> bool:
    risk = TOOL_RISK[tool]
    if tool in {"list_checks", "run_check", "run_all_checks"}:
        return enable_verify
    if not enable_git:
        return False
    if risk in (Risk.LOW_WRITE, Risk.DANGEROUS):
        return enable_write
    return True


# ---- Protected paths: the LLM's write tools must never modify these ----

class ProtectedPathError(PermissionError):
    pass


_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


def is_protected(rel_posix: str) -> bool:
    """True for .git internals, the check config, and real .env files (not .env.example)."""
    parts = [p.casefold() for p in PurePosixPath(rel_posix).parts]   # casefold: Windows/macOS are case-insensitive
    if ".git" in parts:
        return True
    name = parts[-1] if parts else ""
    if name == ".codescope.toml":
        return True
    if name == ".env" or name.startswith(".env."):
        return not name.endswith(_TEMPLATE_SUFFIXES)
    return False


def assert_not_protected(rel_posix: str) -> None:
    if is_protected(rel_posix):
        raise ProtectedPathError(f"'{rel_posix}' is protected and cannot be modified through CodeScope")
