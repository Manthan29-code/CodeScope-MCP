from pathlib import Path
import config
from utils.logger import logger


def resolve_and_verify(
    project_root: str,
    relative_path: str = "",
    fallback_to_default: bool = True
) -> Path:
    """
    Resolves project_root and relative_path into an absolute Path,
    verifying that the resolved target path does NOT escape the project_root directory.

    If the requested project_root does not exist on this machine (e.g. when a remote
    LLM passes a virtual container path like /working_dir/...), it gracefully falls
    back to the server's configured DEFAULT_PROJECT_PATH.

    Raises:
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

    # Symlink check if symlinks are disallowed
    if not config.ALLOW_SYMLINKS:
        check_path = Path(root_path / rel_clean)
        if check_path.is_symlink():
            raise PermissionError(
                f"Security Error: Symlinks are disallowed by configuration: '{relative_path}'"
            )

    return target_path
