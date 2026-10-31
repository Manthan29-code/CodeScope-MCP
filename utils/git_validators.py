"""Input validation for anything that reaches a git command line."""
from __future__ import annotations

import re
from pathlib import Path

_MAX_LEN = 200
_BAD_REF_CHARS = re.compile(r"[\x00-\x20\x7f~^:?*\[\\]")
_REVISION_RE = re.compile(r"^[A-Za-z0-9._/@~^-]+$")


def validate_ref_name(name: str, kind: str = "ref") -> str:
    """Cheap first-line check for branch names. git check-ref-format is the authority."""
    if (
        not isinstance(name, str) or not name or len(name) > _MAX_LEN
        or name.startswith(("-", "/")) or name.endswith(("/", ".", ".lock"))
        or ".." in name or "//" in name or "@{" in name or name == "@"
        or _BAD_REF_CHARS.search(name)
    ):
        raise ValueError(f"Invalid {kind} name")
    return name


def validate_revision(rev: str) -> str:
    """Allows SHAs, branch/tag names and forms like HEAD~2. Rejects ranges and option-like input."""
    if (
        not isinstance(rev, str) or not rev or len(rev) > _MAX_LEN
        or rev.startswith("-") or ".." in rev or not _REVISION_RE.match(rev)
    ):
        raise ValueError("Invalid revision")
    return rev


def to_repo_relative(root: Path, user_path: str) -> str:
    """Resolve a user path inside the project root and return it as a forward-slash relative path.

    Git accepts forward slashes on every OS, so this is the only form passed to git.
    Reuse your existing sandbox helper instead if one already exists.
    """
    if not isinstance(user_path, str) or not user_path.strip() or "\x00" in user_path:
        raise ValueError("Invalid path")
    root_resolved = Path(root).resolve()
    clean_user = user_path.replace("\\", "/")
    candidate = (root_resolved / clean_user).resolve()
    try:
        rel = candidate.relative_to(root_resolved)
    except ValueError:
        raise PermissionError("Path is outside the project root") from None
    return rel.as_posix() or "."
