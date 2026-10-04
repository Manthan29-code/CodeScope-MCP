from typing import List, Optional
import config
from core.path_security import resolve_and_verify
from core.file_classifier import is_binary_file
from core.ignore_manager import IgnoreManager
from core.file_writer import sha256_bytes
from models.schemas import ReadFileOutput, ReadMultipleFilesOutput


def read_one(
    project_path: str,
    file_path: str,
    offset: int = 0,
    limit: Optional[int] = None
) -> ReadFileOutput:
    """
    Reads a single file with line range pagination and truncation handling.
    Returns content_hash of the entire raw file for valid text files.
    """
    rel_clean = file_path.replace("\\", "/").lstrip("/")
    limit_val = limit if limit is not None else config.MAX_LINES_PER_READ

    try:
        root_path = resolve_and_verify(project_path, "")
        target_path = resolve_and_verify(project_path, file_path)
    except Exception as e:
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=None,
            error=str(e)
        )

    if not target_path.exists():
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=None,
            error=f"File not found: {rel_clean}"
        )

    if not target_path.is_file():
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=None,
            error=f"Target path is not a file: {rel_clean}"
        )

    # Check ignore rules
    ignore_mgr = IgnoreManager.get_for_project(root_path)
    if ignore_mgr.is_ignored(rel_clean, is_dir=False):
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=None,
            error=f"File is ignored by configuration or .gitignore: {rel_clean}"
        )

    # Check size limit cap
    stat = target_path.stat()
    if stat.st_size > config.MAX_FILE_SIZE_BYTES:
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=True,
            is_binary=False,
            content_hash=None,
            error=f"File size ({stat.st_size} bytes) exceeds maximum limit ({config.MAX_FILE_SIZE_BYTES} bytes)"
        )

    # Binary check
    if is_binary_file(target_path):
        return ReadFileOutput(
            file_path=rel_clean,
            content="[Binary file content skipped]",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=True,
            content_hash=None,
            error=None
        )

    # Calculate raw content hash
    try:
        raw_bytes = target_path.read_bytes()
        file_hash = sha256_bytes(raw_bytes)
    except Exception as e:
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=None,
            error=f"Error reading file bytes: {e}"
        )

    # Read text content
    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=0,
            end_line=0,
            total_lines=0,
            truncated=False,
            is_binary=False,
            content_hash=file_hash,
            error=f"Error reading file lines: {e}"
        )

    total_lines = len(lines)
    if offset < 0:
        offset = 0

    if offset >= total_lines:
        return ReadFileOutput(
            file_path=rel_clean,
            content="",
            start_line=offset + 1 if total_lines > 0 else 0,
            end_line=total_lines,
            total_lines=total_lines,
            truncated=False,
            is_binary=False,
            content_hash=file_hash,
            error=None
        )

    selected_lines = lines[offset : offset + limit_val]
    content = "".join(selected_lines)

    start_line = offset + 1
    end_line = offset + len(selected_lines)
    truncated = (offset + limit_val) < total_lines

    return ReadFileOutput(
        file_path=rel_clean,
        content=content,
        start_line=start_line,
        end_line=end_line,
        total_lines=total_lines,
        truncated=truncated,
        is_binary=False,
        content_hash=file_hash,
        error=None
    )


def read_many(
    project_path: str,
    file_paths: List[str],
    limit_per_file: Optional[int] = None
) -> ReadMultipleFilesOutput:
    """
    Batches multiple file reads by reusing read_one internally.
    """
    results: List[ReadFileOutput] = []
    for fp in file_paths:
        res = read_one(project_path, fp, offset=0, limit=limit_per_file)
        results.append(res)

    return ReadMultipleFilesOutput(results=results)
