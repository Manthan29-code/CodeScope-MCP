from typing import Any, Dict, List, Optional, Union
from services.read_service import read_many
from models.schemas import ReadMultipleFilesOutput
from utils.error_handler import handle_tool_errors

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_guard = handle_tool_errors()


@_guard
def read_multiple_files(
    file_paths: List[str],
    project_path: str = ".",
    limit_per_file: Optional[int] = None
) -> Union[ReadMultipleFilesOutput, Dict[str, Any]]:
    """
    Reads multiple files in a single batch request to avoid multiple tool calls.
    
    Args:
        file_paths: List of relative file paths to read.
        project_path: Absolute or relative path to project root (default "."). Must be within configured READ_ALLOWED_ROOTS.
        limit_per_file: Optional maximum line cap per file.
    """
    return read_many(project_path, file_paths, limit_per_file)
