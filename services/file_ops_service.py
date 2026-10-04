import os
import shutil
import tempfile
from pathlib import Path
import config
from core import write_guard
from core import path_security
from models.schemas import DeleteFileOutput, MoveFileOutput, CopyFileOutput
from utils.logger import logger


def delete_one(project_path: str, file_path: str) -> DeleteFileOutput:
    """
    Deletes a single file from the project directory.
    Validates permissions, path containment, and protection rules.
    """
    root = write_guard.begin_write(project_path)
    target = path_security.resolve_and_verify(str(root), file_path)

    if target.is_dir():
        raise ValueError(f"Directories are not supported; delete_file operates on single files only: '{file_path}'")

    write_guard.ensure_not_protected(root, target)
    write_guard.ensure_not_ignored(root, target)

    size_bytes = target.stat().st_size
    rel_posix = target.relative_to(root).as_posix()

    os.remove(target)

    logger.info(f"WRITE tool=delete_file root={root} path={rel_posix} size={size_bytes}")

    return DeleteFileOutput(
        file_path=rel_posix,
        deleted=True,
        size_bytes=size_bytes
    )


def move_one(
    project_path: str,
    source_path: str,
    destination_path: str,
    create_parents: bool = False
) -> MoveFileOutput:
    """
    Moves or renames a single file within the project directory.
    Validates containment, protected rules, and prevents unintended overwrites.
    """
    root = write_guard.begin_write(project_path)
    src_target = path_security.resolve_and_verify(str(root), source_path)

    if src_target.is_dir():
        raise ValueError(f"Directories are not supported; move_file operates on single files only: '{source_path}'")

    write_guard.ensure_not_protected(root, src_target)
    write_guard.ensure_not_ignored(root, src_target)

    dst_target = path_security.resolve_for_write(root, destination_path, create_parents=create_parents)
    write_guard.ensure_not_protected(root, dst_target)
    write_guard.ensure_not_ignored(root, dst_target)

    src_rel = src_target.relative_to(root).as_posix()
    dst_rel = destination_path.replace("\\", "/").lstrip("/")

    if src_rel == dst_rel:
        raise ValueError(f"Source and destination paths are identical: '{src_rel}'")

    if dst_target.exists():
        # Allow case-only rename on case-insensitive filesystems if pointing to the exact same file
        is_same_file = False
        try:
            is_same_file = src_target.samefile(dst_target)
        except Exception:
            pass

        if not (is_same_file and src_rel.lower() == dst_rel.lower()):
            raise FileExistsError(
                f"Destination file already exists: '{dst_rel}'. move_file does not overwrite existing files."
            )

    if create_parents and not dst_target.parent.exists():
        dst_target.parent.mkdir(parents=True, exist_ok=True)

    os.replace(src_target, dst_target)

    logger.info(f"WRITE tool=move_file root={root} src={src_rel} dst={dst_rel}")

    return MoveFileOutput(
        source_path=src_rel,
        destination_path=dst_rel
    )


def copy_one(
    project_path: str,
    source_path: str,
    destination_path: str,
    create_parents: bool = False
) -> CopyFileOutput:
    """
    Copies a single file to a destination within the project directory.
    Validates containment, size limits, and protection rules.
    """
    root = write_guard.begin_write(project_path)
    src_target = path_security.resolve_and_verify(str(root), source_path)

    if src_target.is_dir():
        raise ValueError(f"Directories are not supported; copy_file operates on single files only: '{source_path}'")

    write_guard.ensure_not_protected(root, src_target)
    write_guard.ensure_not_ignored(root, src_target)

    dst_target = path_security.resolve_for_write(root, destination_path, create_parents=create_parents)
    write_guard.ensure_not_protected(root, dst_target)
    write_guard.ensure_not_ignored(root, dst_target)

    src_rel = src_target.relative_to(root).as_posix()
    dst_rel = destination_path.replace("\\", "/").lstrip("/")

    if dst_target.exists():
        raise FileExistsError(
            f"Destination file already exists: '{dst_rel}'. copy_file does not overwrite existing files."
        )

    size_bytes = src_target.stat().st_size
    if size_bytes > config.MAX_WRITE_SIZE_BYTES:
        raise write_guard.FileTooLargeError(
            f"Source file size ({size_bytes} bytes) exceeds MAX_WRITE_SIZE_BYTES ({config.MAX_WRITE_SIZE_BYTES} bytes)."
        )

    if create_parents and not dst_target.parent.exists():
        dst_target.parent.mkdir(parents=True, exist_ok=True)

    # Atomic copy using temporary file
    fd, tmp_path_str = tempfile.mkstemp(dir=dst_target.parent, prefix=".codescope-", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_path_str)

    try:
        shutil.copy2(src_target, tmp_path)
        os.replace(tmp_path, dst_target)
    except Exception:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    logger.info(f"WRITE tool=copy_file root={root} src={src_rel} dst={dst_rel} bytes={size_bytes}")

    return CopyFileOutput(
        source_path=src_rel,
        destination_path=dst_rel,
        bytes_copied=size_bytes
    )
