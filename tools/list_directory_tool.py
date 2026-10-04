from typing import Optional
from services.tree_service import build_tree
from models.schemas import ListDirectoryOutput

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def list_directory_tree(
    project_path: str = ".",
    max_depth: Optional[int] = None,
    include_hidden: bool = False
) -> ListDirectoryOutput:
    """
    Returns a filtered directory tree structure for a given project path.
    Excludes gitignored / junk directories (.venv, node_modules, .git, etc.) to save context.
    
    Args:
        project_path: Absolute or relative path to project root (default ".").
        max_depth: Optional depth cap for directory walking.
        include_hidden: Whether to include hidden files/folders (default False).
    """
    return build_tree(project_path, max_depth, include_hidden)
