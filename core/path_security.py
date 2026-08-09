from pathlib import Path
import config


def resolve_and_verify(project_root: str, relative_path: str = "") -> Path:
    """
    Resolves project_root and relative_path into an absolute Path,
    verifying that the resolved target path does NOT escape the project_root directory.
    
    Raises:
        ValueError: If project_root is invalid or target escapes project_root.
        PermissionError: If symlinks are disallowed and a symlink is detected.
    """
    if not project_root:
        raise ValueError("project_path must be a non-empty string.")

    root_path = Path(project_root).resolve()

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
