from typing import Any, Dict, Optional, Union
from services.tree_service import build_tree
from models.schemas import ListDirectoryOutput
from utils.error_handler import handle_tool_errors

annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_guard = handle_tool_errors()


@_guard
def list_directory_tree(
    project_path: str = ".",
    max_depth: Optional[int] = None,
    include_hidden: bool = False
) -> Union[ListDirectoryOutput, Dict[str, Any]]:
    """
    Returns a filtered directory tree structure for a given project path.
    Excludes gitignored / junk directories (.venv, node_modules, .git, etc.) to save context.
    
    Args:
        project_path: Absolute or relative path to project root (default "."). Must be within configured READ_ALLOWED_ROOTS.
        max_depth: Optional depth cap for directory walking.
        include_hidden: Whether to include hidden files/folders (default False).
    """
    return build_tree(project_path, max_depth, include_hidden)
