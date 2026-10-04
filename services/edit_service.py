from typing import List, Optional
from core import write_guard
from core import path_security
from core import file_writer
from core import diff_utils
from models.schemas import EditOperation, EditFileOutput
from utils.logger import logger


class EditMatchError(write_guard.WriteError):
    """Raised when old_string is not found or is ambiguous in the target file."""
    pass


def edit_one(
    project_path: str,
    file_path: str,
    edits: List[EditOperation],
    expected_hash: Optional[str] = None,
    dry_run: bool = False
) -> EditFileOutput:
    """
    Applies exact-match string replacement edits sequentially to an existing text file.
    Preserves original file style (newlines, encoding, BOM, trailing newline).
    """
    # 1. Pipeline guards
    root = write_guard.begin_write(project_path)
    target = path_security.resolve_for_write(root, file_path, create_parents=False)
    write_guard.ensure_not_protected(root, target)
    write_guard.ensure_not_ignored(root, target)

    rel_posix = file_path.replace("\\", "/").lstrip("/")

    # 2. Target existence and text validation
    if not target.exists():
        raise FileNotFoundError(
            f"File not found: '{rel_posix}'. Use write_file to create new files."
        )

    if target.is_dir():
        raise ValueError(f"Target path is a directory: '{rel_posix}'")

    write_guard.ensure_text_file(target)
    write_guard.check_expected_hash(target, expected_hash)

    # 3. Read style and check line endings
    style = file_writer.read_text_with_style(target)
    if style.mixed_newlines:
        raise write_guard.WriteError(
            f"File '{rel_posix}' contains mixed line endings (CRLF and LF). "
            f"Refusing edit to prevent corruption. Normalize line endings first."
        )

    if not edits:
        raise ValueError("edits list cannot be empty.")

    # 4. Sequentially apply edits in memory
    current_text = style.text
    edits_applied = 0
    total_replacements = 0

    for idx, edit in enumerate(edits, start=1):
        if not edit.old_string:
            raise EditMatchError(f"edit #{idx}: old_string must be non-empty.")
        if edit.old_string == edit.new_string:
            raise EditMatchError(f"edit #{idx}: old_string and new_string are identical.")

        write_guard.ensure_text_content(edit.new_string)

        old_norm = edit.old_string.replace("\r\n", "\n").replace("\r", "\n")
        new_norm = edit.new_string.replace("\r\n", "\n").replace("\r", "\n")

        count = current_text.count(old_norm)
        if count == 0:
            raise EditMatchError(
                f"edit #{idx}: old_string not found in file '{rel_posix}'. Check whitespace and indentation."
            )
        if count > 1 and not edit.replace_all:
            raise EditMatchError(
                f"edit #{idx}: old_string found {count} times in file (must be unique). "
                f"Add more surrounding context lines or set replace_all=True."
            )

        if edit.replace_all:
            current_text = current_text.replace(old_norm, new_norm)
            total_replacements += count
        else:
            current_text = current_text.replace(old_norm, new_norm, 1)
            total_replacements += 1

        edits_applied += 1

    # 5. Check if any actual modifications occurred
    if current_text == style.text:
        raise write_guard.WriteError(f"Edits resulted in no changes to file '{rel_posix}'.")

    # 6. Re-encode with original style and check size
    new_bytes = file_writer.encode_text_with_style(current_text, style)
    write_guard.ensure_size_ok(new_bytes)
    new_hash = file_writer.sha256_bytes(new_bytes)
    diff = diff_utils.unified_diff(style.text, current_text, rel_posix)

    # 7. Dry run preview
    if dry_run:
        return EditFileOutput(
            file_path=rel_posix,
            edits_applied=edits_applied,
            replacements_made=total_replacements,
            diff=diff,
            new_hash=new_hash,
            dry_run=True
        )

    # 8. Atomic disk write
    file_writer.atomic_write_bytes(target, new_bytes)

    logger.info(
        f"WRITE tool=edit_file root={root} path={rel_posix} edits={edits_applied} "
        f"replacements={total_replacements} hash={new_hash}"
    )

    return EditFileOutput(
        file_path=rel_posix,
        edits_applied=edits_applied,
        replacements_made=total_replacements,
        diff=diff,
        new_hash=new_hash,
        dry_run=False
    )
