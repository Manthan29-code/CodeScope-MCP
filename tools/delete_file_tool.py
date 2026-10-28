from services.file_ops_service import delete_one
from utils.error_handler import handle_tool_errors

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}

_guard = handle_tool_errors()


@_guard
def delete_file(
    file_path: str,
    project_path: str = "."
) -> dict:
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
    res = delete_one(project_path=project_path, file_path=file_path)
    return {"ok": True, **res.model_dump()}
