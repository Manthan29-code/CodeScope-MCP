from typing import List, Optional
from services.read_service import read_many
from models.schemas import ReadMultipleFilesOutput


def read_multiple_files(
    file_paths: List[str],
    project_path: str = ".",
    limit_per_file: Optional[int] = None
) -> ReadMultipleFilesOutput:
    """
    Reads multiple files in a single batch request to avoid multiple tool calls.
    
    Args:
        file_paths: List of relative file paths to read.
        project_path: Absolute or relative path to project root (default ".").
        limit_per_file: Optional maximum line cap per file.
    """
    return read_many(project_path, file_paths, limit_per_file)
