from services.file_ops_service import copy_one
from models.schemas import CopyFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


def copy_file(
    source_path: str,
    destination_path: str,
    project_path: str = ".",
    create_parents: bool = False
) -> CopyFileOutput:
    """
    Copies a single file to a destination path within the project directory.
    
    Guidelines:
      - Operates on single files only (copying directories is not supported).
      - Destination file must not already exist (does not overwrite).
      - Use create_parents=True to create any missing directories along the destination path.
      - Source file size must be within MAX_WRITE_SIZE_BYTES.
    
    Args:
        source_path: Relative path to existing source file from project root.
        destination_path: Relative path to target destination file.
        project_path: Absolute or relative path to project root (default ".").
        create_parents: Set to True to create missing destination parent directories.
    """
    return copy_one(
        project_path=project_path,
        source_path=source_path,
        destination_path=destination_path,
        create_parents=create_parents
    )
