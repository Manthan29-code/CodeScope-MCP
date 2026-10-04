from pathlib import Path
from typing import Optional, List
import config
from core import write_guard
from core import path_security
from core import file_writer
from core import diff_utils
from core import regex_utils
from core.file_classifier import is_binary_file
from services import search_service
from models.schemas import ReplaceInFilesOutput, ReplaceFileResult
from utils.logger import logger


def replace_in_files(
    project_path: str,
    find: str,
    replace: str,
    *,
    file_pattern: str,
    subpath: Optional[str] = None,
    regex: bool = False,
    case_sensitive: bool = True,
    dry_run: bool = True,
    expected_replacements: Optional[int] = None
) -> ReplaceInFilesOutput:
    """
    Finds and replaces text across multiple matching files within the project.
    Supports dry-run preview, regex with back-references, safety limits, and stale file checks.
    """
    # 1. Gate and allowlist check
    root = write_guard.begin_write(project_path)

    if not find:
        raise ValueError("The 'find' parameter must be a non-empty string.")

    if not file_pattern:
        raise ValueError("The 'file_pattern' parameter is required (e.g. '*.py' or '*.ts').")

    # 2. Compile pattern and safety checks
    pattern = regex_utils.compile_pattern(find, regex_mode=regex, case_sensitive=case_sensitive)
    if regex_utils.matches_empty(pattern):
        raise ValueError("Search pattern matches the empty string; this is not allowed for replace_in_files.")

    # 3. Find candidate files
    candidates = list(search_service.iter_searchable_files(root, subpath=subpath, file_pattern=file_pattern))

    file_results = []
    skipped: List[dict] = []

    # 4. Scan and process candidates
    for fpath in candidates:
        rel_posix = fpath.relative_to(root).as_posix()

        # Check protected paths
        try:
            write_guard.ensure_not_protected(root, fpath)
        except write_guard.ProtectedPathError:
            skipped.append({"file_path": rel_posix, "reason": "protected file"})
            continue

        # Check file size limit
        try:
            if fpath.stat().st_size > config.MAX_FILE_SIZE_BYTES:
                skipped.append({"file_path": rel_posix, "reason": "file exceeds size limit"})
                continue
        except OSError:
            continue

        # Check binary file
        if is_binary_file(fpath):
            skipped.append({"file_path": rel_posix, "reason": "binary file"})
            continue

        # Read content and style
        try:
            style = file_writer.read_text_with_style(fpath)
        except Exception as e:
            skipped.append({"file_path": rel_posix, "reason": f"read error: {e}"})
            continue

        if style.mixed_newlines:
            skipped.append({"file_path": rel_posix, "reason": "mixed line endings"})
            continue

        old_text = style.text

        # Compute replacements
        if regex:
            new_text, count = regex_utils.safe_subn(pattern, replace, old_text)
        else:
            if case_sensitive:
                count = old_text.count(find)
                new_text = old_text.replace(find, replace)
            else:
                new_text, count = regex_utils.safe_subn(pattern, lambda m: replace, old_text)

        if count == 0:
            continue

        new_bytes = file_writer.encode_text_with_style(new_text, style)

        if len(new_bytes) > config.MAX_WRITE_SIZE_BYTES:
            skipped.append({"file_path": rel_posix, "reason": "resulting file exceeds size limit"})
            continue

        diff_str = diff_utils.unified_diff(old_text, new_text, rel_posix)
        file_results.append((fpath, rel_posix, count, diff_str, new_bytes, style.raw_hash))

    # 5. Check maximum modified files limit (applies to dry_run as well)
    max_files = getattr(config, "MAX_FILES_PER_REPLACE", 100)
    if len(file_results) > max_files:
        raise write_guard.FileTooLargeError(
            f"Replace operation would modify {len(file_results)} files, exceeding MAX_FILES_PER_REPLACE ({max_files}). "
            "Narrow your scope with 'file_pattern' or 'subpath'."
        )

    total_replacements = sum(item[2] for item in file_results)

    # 6. Check expected_replacements if provided
    if expected_replacements is not None and total_replacements != expected_replacements:
        raise ValueError(
            f"Total replacements count mismatch: found {total_replacements} replacements, but expected_replacements was {expected_replacements}. No files were modified."
        )

    # 7. Dry run preview return
    if dry_run:
        results = [
            ReplaceFileResult(file_path=rel, replacements=cnt, diff=d)
            for _, rel, cnt, d, _, _ in file_results
        ]
        return ReplaceInFilesOutput(
            dry_run=True,
            files_changed=len(file_results),
            total_replacements=total_replacements,
            results=results,
            skipped=skipped,
            partial=False,
            error=None
        )

    # 8. Apply writes to disk atomically
    written_results: List[ReplaceFileResult] = []
    partial = False
    err_msg = None

    for i, (fpath, rel, cnt, d, new_bytes, original_hash) in enumerate(file_results):
        # Fresh hash check right before writing
        try:
            current_bytes = fpath.read_bytes()
            current_hash = file_writer.sha256_bytes(current_bytes)
            if current_hash != original_hash:
                skipped.append({"file_path": rel, "reason": "changed since scan"})
                continue
        except Exception as e:
            skipped.append({"file_path": rel, "reason": f"verification error: {e}"})
            continue

        try:
            file_writer.atomic_write_bytes(fpath, new_bytes)
            logger.info(f"WRITE tool=replace_in_files root={root} path={rel} replacements={cnt}")
            written_results.append(ReplaceFileResult(file_path=rel, replacements=cnt, diff=d))
        except Exception as e:
            partial = True
            err_msg = str(e)
            for remaining in file_results[i + 1:]:
                skipped.append({"file_path": remaining[1], "reason": "not attempted after earlier failure"})
            break

    actual_total = sum(r.replacements for r in written_results)

    return ReplaceInFilesOutput(
        dry_run=False,
        files_changed=len(written_results),
        total_replacements=actual_total,
        results=written_results,
        skipped=skipped,
        partial=partial,
        error=err_msg
    )
