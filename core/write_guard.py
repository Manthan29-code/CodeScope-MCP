import functools
import hashlib
import os
import re
from pathlib import Path
from typing import Union, Optional
import pathspec

import config
from core.path_security import is_within
from core.ignore_manager import IgnoreManager
from core.file_classifier import is_binary_file


class WriteError(Exception):
    """Base exception for all write and edit errors."""
    pass


class WriteDisabledError(WriteError):
    """Raised when write tools are disabled in configuration."""
    pass


class RootNotAllowedError(WriteError):
    """Raised when project path is not in WRITE_ALLOWED_ROOTS or is a filesystem root."""
    pass


class ProtectedPathError(WriteError):
    """Raised when target path matches protected files/directories (e.g. .git, .env, keys)."""
    pass


class IgnoredPathError(WriteError):
    """Raised when target path matches gitignore or default ignore patterns."""
    pass


class FileTooLargeError(WriteError):
    """Raised when file or write content exceeds MAX_WRITE_SIZE_BYTES."""
    pass


class BinaryFileError(WriteError):
    """Raised when attempting text operations on a binary file or writing binary content."""
    pass


class StaleFileError(WriteError):
    """Raised when expected_hash does not match current file content."""
    pass


@functools.lru_cache(maxsize=32)
def _get_protected_spec(patterns_tuple: tuple[str, ...]) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", patterns_tuple)


def begin_write(project_path: Union[str, Path]) -> Path:
    """
    Validates that write operations are enabled and the target project_path is valid
    and contained within one of WRITE_ALLOWED_ROOTS.

    Returns the resolved Path of project_path.
    """
    if not config.ENABLE_WRITE_TOOLS:
        raise WriteDisabledError(
            "Write operations are disabled. Set ENABLE_WRITE_TOOLS=true in configuration or .env to enable."
        )

    if not project_path or not str(project_path).strip():
        raise ValueError("project_path must be a non-empty string.")

    root = Path(project_path).resolve()

    if not root.exists():
        raise ValueError(f"Project root directory does not exist: '{project_path}'")
    if not root.is_dir():
        raise ValueError(f"Project root path is not a directory: '{project_path}'")

    # Reject filesystem root or drive root
    if root.parent == root or str(root) in ("/", "\\") or re.match(r"^[a-zA-Z]:[\\/]?$", str(root)):
        raise RootNotAllowedError(f"Cannot perform write operations directly on filesystem or drive root: '{root}'")

    if not config.WRITE_ALLOWED_ROOTS:
        raise RootNotAllowedError(
            "Write operations refused: WRITE_ALLOWED_ROOTS is empty. Add project root to WRITE_ALLOWED_ROOTS in .env or config."
        )

    # Check if root is contained within any allowed root
    is_allowed = False
    for allowed_str in config.WRITE_ALLOWED_ROOTS:
        if not allowed_str or not allowed_str.strip():
            continue
        try:
            allowed_p = Path(allowed_str.strip()).resolve()
            if is_within(allowed_p, root):
                is_allowed = True
                break
        except Exception:
            continue

    if not is_allowed:
        raise RootNotAllowedError(
            f"Access denied: Project path '{root}' is not within any allowed root in WRITE_ALLOWED_ROOTS: {config.WRITE_ALLOWED_ROOTS}"
        )

    return root


def ensure_not_protected(root: Path, target: Path) -> None:
    """
    Ensures that the target path does not match protected path patterns (.git/, .env, *.key, etc.).
    """
    try:
        rel_posix = target.relative_to(root).as_posix()
    except ValueError:
        # Fallback if relative_to fails
        rel_posix = os.path.relpath(str(target), str(root)).replace("\\", "/")

    # Any .git directory component is always protected
    parts = rel_posix.split("/")
    if ".git" in parts or any(p.startswith(".git") and p != ".gitignore" and p != ".gitattributes" and p != ".github" for p in parts if p == ".git"):
        raise ProtectedPathError(
            f"Access denied: path '{rel_posix}' contains protected '.git' directory component."
        )

    patterns_tuple = tuple(config.PROTECTED_PATH_PATTERNS)
    spec = _get_protected_spec(patterns_tuple)

    is_dir = target.is_dir() if target.exists() else False
    if is_dir and not rel_posix.endswith("/"):
        if spec.match_file(rel_posix + "/"):
            raise ProtectedPathError(f"Access denied: path '{rel_posix}' is protected by safety rules.")

    if spec.match_file(rel_posix):
        raise ProtectedPathError(f"Access denied: path '{rel_posix}' is protected by safety rules.")


def ensure_not_ignored(root: Path, target: Path) -> None:
    """
    Ensures that the target path is not ignored according to .gitignore or default ignore list.
    """
    if not config.BLOCK_WRITES_TO_IGNORED:
        return

    try:
        rel_posix = target.relative_to(root).as_posix()
    except ValueError:
        rel_posix = os.path.relpath(str(target), str(root)).replace("\\", "/")

    ignore_mgr = IgnoreManager.get_for_project(root)
    is_dir = target.is_dir() if target.exists() else False

    if ignore_mgr.is_ignored(rel_posix, is_dir=is_dir):
        raise IgnoredPathError(
            f"Access denied: path '{rel_posix}' is ignored (gitignore/default list); CodeScope does not write ignored paths."
        )


def ensure_size_ok(data: bytes) -> None:
    """
    Ensures that data size does not exceed MAX_WRITE_SIZE_BYTES.
    """
    if len(data) > config.MAX_WRITE_SIZE_BYTES:
        raise FileTooLargeError(
            f"Write size ({len(data)} bytes) exceeds maximum allowed limit MAX_WRITE_SIZE_BYTES ({config.MAX_WRITE_SIZE_BYTES} bytes)."
        )


def ensure_text_file(path: Path) -> None:
    """
    Ensures that an existing file is not a binary file.
    """
    if path.exists() and path.is_file():
        if is_binary_file(path):
            raise BinaryFileError(f"Cannot perform text operations on binary file: '{path.name}'.")


def ensure_text_content(text: str) -> None:
    """
    Ensures that text does not contain null bytes (binary indicator).
    """
    if "\x00" in text:
        raise BinaryFileError("Content contains null bytes (binary content detected).")


def check_expected_hash(path: Path, expected_hash: Optional[str]) -> None:
    """
    If expected_hash is provided, checks that the existing file matches expected_hash.
    """
    if expected_hash is not None:
        if not path.exists():
            raise StaleFileError(f"File '{path.name}' does not exist, but expected_hash was provided.")
        try:
            with open(path, "rb") as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            raise StaleFileError(f"Unable to read file '{path.name}' to verify hash: {e}")

        if current_hash != expected_hash:
            raise StaleFileError(
                f"File '{path.name}' changed since you read it (hash mismatch: expected {expected_hash}, got {current_hash}); call read_file again."
            )
