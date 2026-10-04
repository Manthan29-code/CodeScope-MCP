from typing import Optional
from services.write_service import write_one
from models.schemas import WriteFileOutput

annotations = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}


def write_file(
    file_path: str,
    content: str,
    project_path: str = ".",
    overwrite: bool = False,
    create_parents: bool = False,
    expected_hash: Optional[str] = None,
    dry_run: bool = False
) -> WriteFileOutput:
    """
    Creates a new file or completely overwrites an existing file.
    
    Guidelines for AI Agents:
      - Code Formatting & Indentation: ALWAYS write clean, properly indented, multi-line code with standard newlines (\\n).
        * HTML: Indent tags properly (2 spaces), separate <head>, <body>, scripts, and elements onto their own lines.
        * CSS: Use standard block formatting with selectors, newlines, and indented properties (2 spaces).
        * JavaScript / TypeScript / React (JSX/TSX): Format functions, imports, objects, and JSX tags across multiple lines with proper 2-space indentation.
        * Python: Follow PEP 8 style with 4-space indentation and proper blank lines between functions/classes.
        * Java / C / C++: Use standard 4-space indentation and brace formatting across multiple lines.
      - NEVER minify or concatenate multiple lines of code into a single line unless creating a minified asset (.min.js, .min.css).
      - Always set create_parents=True when writing files located in subdirectories (e.g. 'css/variables.css', 'js/modules/state.js') so parent directories are created automatically.
      - file_path must be relative to project_path (e.g. if project_path='C:\\MyProject\\WorkPulse', use file_path='css/style.css', NOT 'WorkPulse/css/style.css').
      - Set overwrite=True if the target file already exists and you want to replace it.
      - Prefer edit_file for partial updates to existing files.
      - Use dry_run=True to preview diffs before writing to disk.
    
    Args:
        file_path: Relative path to target file from project_path (e.g. 'index.html' or 'css/base.css').
        content: Multi-line, cleanly indented source code content to write into the file.
        project_path: Absolute or relative path to project root (default ".").
        overwrite: Set to True to allow replacing an existing file (default False).
        create_parents: Always set to True when target file is inside subdirectories that may not exist yet.
        expected_hash: Optional SHA-256 hash from read_file for staleness check.
        dry_run: If True, previews changes with unified diff without modifying disk (default False).
    """
    return write_one(
        project_path=project_path,
        file_path=file_path,
        content=content,
        overwrite=overwrite,
        create_parents=create_parents,
        expected_hash=expected_hash,
        dry_run=dry_run
    )
