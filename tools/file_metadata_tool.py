from services.metadata_service import get_metadata
from models.schemas import FileMetadataOutput


def get_file_metadata(
    project_path: str,
    file_path: str
) -> FileMetadataOutput:
    """
    Retrieves file metadata (size, last modified time, language, token estimate, binary status)
    without reading full file content into context.
    
    Args:
        project_path: Absolute path to project root.
        file_path: Relative path to target file.
    """
    return get_metadata(project_path, file_path)
