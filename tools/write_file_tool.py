from typing import Optional
from services.write_service import write_one
from models.schemas import WriteFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}


def write_file(
    file_path: str,
    content: str,
    project_path: str = ".",
    overwrite: bool = False,
    create_parents: bool = False,
    expected_hash: Optional[str] = None,
    dry_run: bool = False
) -> WriteFileOutput:
    """
    Creates a new file or completely overwrites an existing file.
    
    Guidelines:
      - Prefer edit_file for updating existing files to avoid rewriting large content.
      - Use overwrite=True only for complete file rewrites.
      - Pass expected_hash (obtained from read_file) to avoid clobbering newer concurrent changes.
      - Use dry_run=True to preview the write operation and inspect diffs without modifying disk.
    
    Args:
        file_path: Relative path to target file from project root.
        content: String content to write.
        project_path: Absolute or relative path to project root (default ".").
        overwrite: Set to True to allow replacing an existing file (default False).
        create_parents: Set to True to automatically create missing parent directories (default False).
        expected_hash: Optional SHA-256 hash from read_file for staleness check.
        dry_run: If True, previews changes without modifying disk (default False).
    """
    return write_one(
        project_path=project_path,
        file_path=file_path,
        content=content,
        overwrite=overwrite,
        create_parents=create_parents,
        expected_hash=expected_hash,
        dry_run=dry_run
    )
