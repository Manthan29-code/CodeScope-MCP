from typing import Any, Dict, Union
from services.metadata_service import get_metadata
from models.schemas import FileMetadataOutput
from utils.error_handler import handle_tool_errors

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_guard = handle_tool_errors()


@_guard
def get_file_metadata(
    file_path: str,
    project_path: str = "."
) -> Union[FileMetadataOutput, Dict[str, Any]]:
    """
    Retrieves file metadata (size, last modified time, language, token estimate, binary status)
    without reading full file content into context.
    
    Args:
        file_path: Relative path to target file from project root.
        project_path: Absolute or relative path to project root (default "."). Must be within configured READ_ALLOWED_ROOTS.
    """
    return get_metadata(project_path, file_path)
