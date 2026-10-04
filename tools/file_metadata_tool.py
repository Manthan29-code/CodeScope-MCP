from services.metadata_service import get_metadata
from models.schemas import FileMetadataOutput

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def get_file_metadata(
    file_path: str,
    project_path: str = "."
) -> FileMetadataOutput:
    """
    Retrieves file metadata (size, last modified time, language, token estimate, binary status)
    without reading full file content into context.
    
    Args:
        file_path: Relative path to target file from project root.
        project_path: Absolute or relative path to project root (default ".").
    """
    return get_metadata(project_path, file_path)
