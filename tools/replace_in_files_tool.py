from typing import Optional
from services.replace_service import replace_in_files as _replace_in_files
from models.schemas import ReplaceInFilesOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}


def replace_in_files(
    find: str,
    replace: str,
    file_pattern: str,
    project_path: str = ".",
    subpath: Optional[str] = None,
    regex: bool = False,
    case_sensitive: bool = True,
    dry_run: bool = True,
    expected_replacements: Optional[int] = None
) -> ReplaceInFilesOutput:
    """
    Finds and replaces text across multiple matching files within the project.
    
    Recommended Workflow:
      1. Call first with dry_run=True (the default) to inspect matched files and unified diffs.
      2. Verify the total_replacements count in the preview output.
      3. Call again with dry_run=False and expected_replacements set to the previewed total to apply changes safely.
    
    Guidelines:
      - file_pattern is required (e.g. '*.py', '*.ts') to constrain the search space.
      - Default mode is exact literal match; set regex=True to use regular expression matching.
      - In regex mode, back-references like \\1 or \\g<1> in the replace string are supported.
      - Protected files (.git, .env, keys) and ignored paths (node_modules, dist) are automatically excluded.
    
    Args:
        find: Search string or regular expression pattern.
        replace: Replacement text (supports back-references in regex mode).
        file_pattern: Glob pattern to filter target files (e.g. '*.py', '*.js').
        project_path: Absolute or relative path to project root (default ".").
        subpath: Optional directory path relative to project root to limit the search.
        regex: If True, treats find as a regular expression (default False).
        case_sensitive: If True, performs case-sensitive replacement (default True).
        dry_run: If True, previews changes and diffs without modifying files (default True).
        expected_replacements: Optional safety check on total replacement count before writing.
    """
    return _replace_in_files(
        project_path=project_path,
        find=find,
        replace=replace,
        file_pattern=file_pattern,
        subpath=subpath,
        regex=regex,
        case_sensitive=case_sensitive,
        dry_run=dry_run,
        expected_replacements=expected_replacements
    )
