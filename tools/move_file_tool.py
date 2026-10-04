from services.file_ops_service import move_one
from models.schemas import MoveFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}


def move_file(
    source_path: str,
    destination_path: str,
    project_path: str = ".",
    create_parents: bool = False
) -> MoveFileOutput:
    """
    Moves or renames a single file within the project directory.
    
    Guidelines:
      - Operates on single files only (moving directories is not supported).
      - Destination file must not already exist (does not overwrite).
      - Use create_parents=True to create any missing directories along the destination path.
      - Case-only renames (e.g. file.py -> File.py) are supported.
    
    Args:
        source_path: Relative path to existing source file from project root.
        destination_path: Relative path to target destination file.
        project_path: Absolute or relative path to project root (default ".").
        create_parents: Set to True to create missing destination parent directories.
    """
    return move_one(
        project_path=project_path,
        source_path=source_path,
        destination_path=destination_path,
        create_parents=create_parents
    )
