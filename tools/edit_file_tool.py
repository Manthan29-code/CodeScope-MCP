from typing import List, Optional
from services.edit_service import edit_one
from models.schemas import EditOperation, EditFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}


def edit_file(
    file_path: str,
    edits: List[EditOperation],
    project_path: str = ".",
    expected_hash: Optional[str] = None,
    dry_run: bool = False
) -> EditFileOutput:
    """
    Applies exact-match string replacement edits sequentially to an existing text file.
    
    Guidelines:
      - Always inspect the file first with read_file before constructing edits.
      - old_string must match text in the file exactly (including indentation and spaces) and must be unique.
      - If old_string appears multiple times, include surrounding lines to make it unique or set replace_all=True.
      - Edits apply sequentially in the given order; each edit operates on the output of the preceding edit.
      - Pass expected_hash from read_file to ensure the file has not been modified since it was read.
      - Use dry_run=True to preview the resulting unified diff without making changes to disk.
    
    Args:
        file_path: Relative path to target file from project root.
        edits: List of 1-50 EditOperation objects (old_string, new_string, replace_all).
        project_path: Absolute or relative path to project root (default ".").
        expected_hash: Optional SHA-256 hash from read_file for staleness check.
        dry_run: If True, returns the unified diff preview without modifying disk (default False).
    """
    return edit_one(
        project_path=project_path,
        file_path=file_path,
        edits=edits,
        expected_hash=expected_hash,
        dry_run=dry_run
    )
