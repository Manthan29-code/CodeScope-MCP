import os
import re
from pathlib import Path
from typing import Union
import config
from utils.logger import logger

RESERVED_DEVICE_NAMES_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$",
    re.IGNORECASE
)


def is_within(parent: Union[str, Path], child: Union[str, Path]) -> bool:
    """
    Checks if child path is contained within parent directory path.
    Uses os.path.commonpath on os.path.normcase-normalized resolved paths to avoid
    sibling prefix attacks (e.g. /tmp/proj vs /tmp/proj-evil).
    Case-insensitive on Windows.
    """
    try:
        p_res = str(Path(parent).resolve())
        c_res = str(Path(child).resolve())
        p_norm = os.path.normcase(p_res)
        c_norm = os.path.normcase(c_res)
        common = os.path.commonpath([p_norm, c_norm])
        return common == p_norm
    except (ValueError, Exception):
        return False


class ReadRootNotAllowedError(PermissionError, ValueError):
    """Raised when project path is not in READ_ALLOWED_ROOTS or is a filesystem root."""
    pass


def verify_read_root(root: Union[str, Path]) -> Path:
    """
    Validates that root is an approved directory within config.READ_ALLOWED_ROOTS,
    and is not a raw filesystem/drive root.

    Raises:
        ValueError: If root is empty or does not exist or is not a directory.
        ReadRootNotAllowedError: If root is a filesystem/drive root or not within READ_ALLOWED_ROOTS.
    """
    if not root or not str(root).strip():
        raise ValueError("project_path must be a non-empty string.")

    root_p = Path(root).resolve()

    if not root_p.exists():
        raise ValueError(f"Project root directory does not exist: '{root}'")
    if not root_p.is_dir():
        raise ValueError(f"Project root path is not a directory: '{root}'")

    # Reject filesystem root or drive root
    if root_p.parent == root_p or str(root_p) in ("/", "\\") or re.match(r"^[a-zA-Z]:[\\/]?$", str(root_p)):
        raise ReadRootNotAllowedError(f"Cannot perform read operations directly on filesystem or drive root: '{root_p}'")

    if not config.READ_ALLOWED_ROOTS:
        raise ReadRootNotAllowedError(
            "Read operations refused: READ_ALLOWED_ROOTS is empty. Add project root to READ_ALLOWED_ROOTS in .env or config."
        )

    # Check if root is contained within any allowed root
    is_allowed = False
    for allowed_str in config.READ_ALLOWED_ROOTS:
        if not allowed_str or not allowed_str.strip():
            continue
        try:
            allowed_p = Path(allowed_str.strip()).resolve()
            if is_within(allowed_p, root_p):
                is_allowed = True
                break
        except Exception:
            continue

    if not is_allowed:
        raise ReadRootNotAllowedError(
            f"Access denied: Project path '{root_p}' is not within any allowed root in READ_ALLOWED_ROOTS: {config.READ_ALLOWED_ROOTS}"
        )

    return root_p


def resolve_and_verify(
    project_root: str,
    relative_path: str = "",
    fallback_to_default: bool = True,
    check_read_roots: bool = True
) -> Path:
    """
    Resolves project_root and relative_path into an absolute Path,
    verifying that the resolved target path does NOT escape the project_root directory
    and that project_root is within the approved READ_ALLOWED_ROOTS.

    If the requested project_root does not exist on this machine (e.g. when a remote
    LLM passes a virtual container path like /working_dir/...), it gracefully falls
    back to the server's configured DEFAULT_PROJECT_PATH.

    Raises:
        ReadRootNotAllowedError: If project_root is not inside READ_ALLOWED_ROOTS or is a filesystem root.
        ValueError: If project_root is invalid or target escapes project_root.
        PermissionError: If symlinks are disallowed and a symlink is detected.
    """
    selected_root = project_root

    # Handle empty / omitted / relative project_root
    if not selected_root or selected_root.strip() in ("", ".", "./"):
        if fallback_to_default and config.DEFAULT_PROJECT_PATH:
            selected_root = config.DEFAULT_PROJECT_PATH
        elif not selected_root:
            raise ValueError("project_path must be a non-empty string.")

    root_path = Path(selected_root).resolve()

    # If the provided path does not exist on this host machine
    if not root_path.exists() or not root_path.is_dir():
        if fallback_to_default and config.DEFAULT_PROJECT_PATH:
            default_path = Path(config.DEFAULT_PROJECT_PATH).resolve()
            if default_path.exists() and default_path.is_dir():
                logger.warning(
                    f"Provided project_root '{project_root}' does not exist on host. "
                    f"Falling back to server workspace root: '{default_path}'"
                )
                root_path = default_path
            else:
                raise ValueError(
                    f"Project root directory does not exist: '{project_root}' and fallback '{default_path}' is invalid."
                )
        else:
            if not root_path.exists():
                raise ValueError(f"Project root directory does not exist: {project_root}")
            if not root_path.is_dir():
                raise ValueError(f"Project root path is not a directory: {project_root}")

    # Verify project_root against READ_ALLOWED_ROOTS if enabled
    if check_read_roots:
        root_path = verify_read_root(root_path)

    # Clean relative path string
    rel_clean = relative_path.strip().lstrip("/\\") if relative_path else ""
    target_path = (root_path / rel_clean).resolve()

    # Verify path containment
    try:
        target_path.relative_to(root_path)
    except ValueError:
        raise ValueError(
            f"Security Error: Access denied. Path '{relative_path}' escapes project root '{root_path}'."
        )
    if not is_within(root_path, target_path):
        raise ValueError(
            f"Security Error: Access denied. Path '{relative_path}' escapes project root '{root_path}'."
        )

    # Symlink check if symlinks are disallowed
    if not config.ALLOW_SYMLINKS:
        check_path = Path(root_path / rel_clean)
        if check_path.is_symlink():
            raise PermissionError(
                f"Security Error: Symlinks are disallowed by configuration: '{relative_path}'"
            )

    return target_path


def resolve_for_write(
    project_root: Union[str, Path],
    relative_path: str,
    *,
    create_parents: bool = False
) -> Path:
    """
    Returns the absolute target path of a file that may not exist yet,
    strictly validating path security, containment, forbidden names, and symlinks.

    Rules:
      - Reject empty path, '.', absolute paths, drive letters, and target equal to project root.
      - Accept both / and \\ separators.
      - Reject Windows-reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) with or without extension.
      - Reject trailing dot or space in any path component.
      - Verify containment via is_within (rejects path traversal / sibling escapes).
      - Enforce symlink policy (ALLOW_SYMLINKS=False) on all existing chain components.
      - If create_parents=False and parent dir is missing -> raise ValueError.
      - If create_parents=True, parent may be missing, but nothing is created here.
    """
    if not project_root:
        raise ValueError("project_root must be a non-empty string or Path.")

    root_path = Path(project_root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Project root directory does not exist or is not a directory: '{project_root}'")

    if not relative_path or not str(relative_path).strip():
        raise ValueError("relative_path must be a non-empty string.")

    # Split raw components to check for forbidden names & trailing dots/spaces
    raw_components = [c for c in re.split(r"[\\/]+", str(relative_path)) if c]
    if not raw_components:
        raise ValueError("relative_path cannot be empty.")

    for comp in raw_components:
        if comp in (".", ".."):
            continue
        if RESERVED_DEVICE_NAMES_RE.match(comp):
            raise ValueError(
                f"Invalid path component '{comp}': Windows-reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) are disallowed."
            )
        if comp.endswith(".") or comp.endswith(" "):
            raise ValueError(
                f"Invalid path component '{comp}': Trailing dots and trailing spaces are disallowed."
            )

    clean_raw = relative_path.strip()
    if clean_raw in (".", "./", ".\\", "/", "\\"):
        raise ValueError("Target path cannot be the project root directory.")

    if os.path.isabs(clean_raw) or re.match(r"^[a-zA-Z]:", clean_raw):
        raise ValueError(f"Target path must be a relative path, got absolute path: '{relative_path}'")

    target_path = (root_path / clean_raw).resolve()

    # Reject target equal to project root
    if os.path.normcase(str(target_path)) == os.path.normcase(str(root_path)):
        raise ValueError("Target path cannot be the project root itself.")

    # Check containment
    if not is_within(root_path, target_path):
        raise ValueError(
            f"Security Error: Access denied. Path '{relative_path}' escapes project root '{root_path}'."
        )

    # Nearest existing ancestor
    curr = target_path
    existing_ancestor = None
    while True:
        if curr.exists() or curr.is_symlink():
            existing_ancestor = curr
            break
        if curr.parent == curr:
            break
        curr = curr.parent

    # Enforce symlink policy if disallowed
    if not config.ALLOW_SYMLINKS:
        if root_path.is_symlink():
            raise PermissionError(f"Security Error: Symlinks are disallowed by configuration: '{root_path}'")
        check = existing_ancestor
        while check and check != root_path and is_within(root_path, check):
            if check.is_symlink():
                raise PermissionError(
                    f"Security Error: Symlinks are disallowed by configuration: '{relative_path}'"
                )
            check = check.parent

    # Check parent existence
    if not create_parents and not target_path.parent.exists():
        raise ValueError(
            f"Parent directory does not exist: '{target_path.parent}'. Pass create_parents=True to allow creating parent directories."
        )

    return target_path
