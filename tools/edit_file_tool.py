from typing import List, Optional
from services.edit_service import edit_one
from models.schemas import EditOperation
from utils.error_handler import handle_tool_errors

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}

_guard = handle_tool_errors()


@_guard
def edit_file(
    file_path: str,
    edits: List[EditOperation],
    project_path: str = ".",
    expected_hash: Optional[str] = None,
    dry_run: bool = False,
    verify: Optional[List[str]] = None
) -> dict:
    """
    Applies exact-match string replacement edits sequentially to an existing text file.
    
    Guidelines:
      - Always inspect the file first with read_file before constructing edits.
      - old_string must match text in the file exactly (including exact indentation, newlines, and spaces) and must be unique.
      - new_string must preserve clean multi-line formatting and proper indentation (matching surrounding code style).
      - If old_string appears multiple times, include surrounding lines to make it unique or set replace_all=True.
      - Edits apply sequentially in the given order; each edit operates on the output of the preceding edit.
      - Pass expected_hash from read_file to ensure the file has not been modified since it was read.
      - Use dry_run=True to preview the resulting unified diff without making changes to disk.
      - Pass verify=['lint', 'test'] to automatically run named verification checks after edits are applied.
    
    Args:
        file_path: Relative path to target file from project root.
        edits: List of 1-50 EditOperation objects (old_string, new_string, replace_all).
        project_path: Absolute or relative path to project root (default ".").
        expected_hash: Optional SHA-256 hash from read_file for staleness check.
        dry_run: If True, returns the unified diff preview without modifying disk (default False).
        verify: Optional list of check names (e.g. ['lint', 'test']) to execute after editing.
    """
    res = edit_one(
        project_path=project_path,
        file_path=file_path,
        edits=edits,
        expected_hash=expected_hash,
        dry_run=dry_run,
        verify=verify
    )
    return {"ok": True, **res.model_dump()}
