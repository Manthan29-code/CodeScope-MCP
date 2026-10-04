from typing import Optional
from core import write_guard
from core import path_security
from core import file_writer
from core import diff_utils
from models.schemas import WriteFileOutput
from utils.logger import logger


def write_one(
    project_path: str,
    file_path: str,
    content: str,
    *,
    overwrite: bool = False,
    create_parents: bool = False,
    expected_hash: Optional[str] = None,
    dry_run: bool = False
) -> WriteFileOutput:
    """
    Creates a new file or completely overwrites an existing file safely.
    Follows write guard checks, style preservation, atomic writing, and audit logging.
    """
    # 1. Begin write gate & root allowlist check
    root = write_guard.begin_write(project_path)

    # 2. Resolve target path with write safety checks
    target = path_security.resolve_for_write(root, file_path, create_parents=create_parents)

    # 3. Protected and ignore checks
    write_guard.ensure_not_protected(root, target)
    write_guard.ensure_not_ignored(root, target)

    # 4. Check for binary null bytes in content
    write_guard.ensure_text_content(content)

    rel_posix = file_path.replace("\\", "/").lstrip("/")

    if target.is_dir():
        raise ValueError(f"Target path is a directory, not a file: '{rel_posix}'")

    if target.exists():
        if not overwrite:
            raise FileExistsError(
                f"File already exists: '{rel_posix}'. Pass overwrite=True to replace or use edit_file for partial changes."
            )
        write_guard.ensure_text_file(target)
        write_guard.check_expected_hash(target, expected_hash)

        existing_style = file_writer.read_text_with_style(target)
        old_text = existing_style.text
        new_bytes = file_writer.encode_text_with_style(content, existing_style)
        diff = diff_utils.unified_diff(old_text, content, rel_posix)
        created = False
        overwritten = True
    else:
        if expected_hash is not None:
            raise write_guard.StaleFileError(
                f"File '{rel_posix}' does not exist, but expected_hash was provided."
            )
        new_bytes = content.encode("utf-8")
        diff = None
        created = True
        overwritten = False

    # 5. Check size limit
    write_guard.ensure_size_ok(new_bytes)
    new_hash = file_writer.sha256_bytes(new_bytes)

    # 6. Dry run early return (no disk modifications)
    if dry_run:
        return WriteFileOutput(
            file_path=rel_posix,
            created=created,
            overwritten=overwritten,
            bytes_written=len(new_bytes),
            new_hash=new_hash,
            diff=diff,
            dry_run=True
        )

    # 7. Create parent dirs if requested & perform atomic write
    if create_parents and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    file_writer.atomic_write_bytes(target, new_bytes)

    logger.info(
        f"WRITE tool=write_file root={root} path={rel_posix} created={created} "
        f"overwritten={overwritten} bytes={len(new_bytes)} hash={new_hash}"
    )

    return WriteFileOutput(
        file_path=rel_posix,
        created=created,
        overwritten=overwritten,
        bytes_written=len(new_bytes),
        new_hash=new_hash,
        diff=diff,
        dry_run=False
    )
