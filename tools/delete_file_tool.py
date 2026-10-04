from services.file_ops_service import delete_one
from models.schemas import DeleteFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}


def delete_file(
    file_path: str,
    project_path: str = "."
) -> DeleteFileOutput:
    """
    Deletes a single file from the project directory.
    
    Guidelines:
      - Operates on single files only (deleting directories is not supported).
      - Cannot delete protected files (.git, .env, private keys) or ignored paths.
      - Deletions are permanent; use your version control system (e.g. git) to undo if needed.
    
    Args:
        file_path: Relative path to target file from project root.
        project_path: Absolute or relative path to project root (default ".").
    """
    return delete_one(project_path=project_path, file_path=file_path)
