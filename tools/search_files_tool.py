from typing import Optional, Literal
from services.search_service import search
from models.schemas import SearchFilesOutput


def search_files(
    project_path: str,
    query: str,
    search_type: Literal["content", "filename"] = "content",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 50,
    offset: int = 0
) -> SearchFilesOutput:
    """
    Searches for files or code content within the project root directory.
    Filters out ignored directories/files (.venv, node_modules, .git, build, etc.) automatically.
    
    Args:
        project_path: Absolute path to project root.
        query: Search string or regex pattern to look for.
        search_type: "content" (grep inside files) or "filename" (match file names).
        file_pattern: Optional glob filter e.g. '*.py' or '*.ts'.
        case_sensitive: Whether search should be case sensitive (default False).
        max_results: Maximum matches to return in one page (default 50).
        offset: Pagination starting offset index (default 0).
    """
    return search(
        project_path=project_path,
        query=query,
        search_type=search_type,
        file_pattern=file_pattern,
        case_sensitive=case_sensitive,
        max_results=max_results,
        offset=offset
    )
