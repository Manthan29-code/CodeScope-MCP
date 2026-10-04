from typing import Optional
from services.read_service import read_one
from models.schemas import ReadFileOutput


def read_file(
    file_path: str,
    project_path: str = ".",
    offset: int = 0,
    limit: Optional[int] = None
) -> ReadFileOutput:
    """
    Reads the content of a single text file in the project with pagination support.
    
    Args:
        file_path: Relative path to target file from project root.
        project_path: Absolute or relative path to project root (default ".").
        offset: 0-indexed line offset to start reading from (default 0).
        limit: Maximum number of lines to read (defaults to server MAX_LINES_PER_READ).
    """
    return read_one(project_path, file_path, offset, limit)
