from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    name: str = Field(..., description="Name of the file or directory")
    path: str = Field(..., description="Path relative to the project root")
    type: Literal["file", "directory"] = Field(..., description="Item type: 'file' or 'directory'")
    size_bytes: Optional[int] = Field(None, description="Size in bytes (files only)")
    token_estimate: Optional[int] = Field(None, description="Estimated token count (files only)")
    children: Optional[List["TreeNode"]] = Field(None, description="Child nodes (directories only)")


TreeNode.model_rebuild()


class ListDirectoryInput(BaseModel):
    project_path: str = Field(".", description="Absolute or relative path to the project root directory (defaults to current directory)")
    max_depth: Optional[int] = Field(None, description="Maximum directory traversal depth (None for unlimited)")
    include_hidden: bool = Field(False, description="Whether to include hidden files/directories (starting with '.')")


class ListDirectoryOutput(BaseModel):
    project_path: str = Field(..., description="Absolute project root path")
    tree: TreeNode = Field(..., description="Root tree node containing directory structure")
    total_files: int = Field(..., description="Total count of files listed")
    total_directories: int = Field(..., description="Total count of directories listed")


class FileMetadataInput(BaseModel):
    file_path: str = Field(..., description="Relative path to the target file from project root")
    project_path: str = Field(".", description="Absolute or relative path to the project root directory")


class FileMetadataOutput(BaseModel):
    file_path: str = Field(..., description="Relative path to the file")
    size_bytes: int = Field(..., description="File size in bytes")
    last_modified: str = Field(..., description="ISO 8601 formatted last modification timestamp")
    language: str = Field(..., description="Guessed programming language or file type")
    token_estimate: int = Field(..., description="Rough estimate of token count")
    is_binary: bool = Field(..., description="True if binary content was detected")


class ReadFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path to the target file from project root")
    project_path: str = Field(".", description="Absolute or relative path to the project root directory")
    offset: int = Field(0, description="0-indexed starting line number")
    limit: Optional[int] = Field(None, description="Maximum number of lines to read (defaults to server MAX_LINES_PER_READ)")


class ReadFileOutput(BaseModel):
    file_path: str = Field(..., description="Relative path to the target file")
    content: str = Field(..., description="Read file content text")
    start_line: int = Field(..., description="1-indexed line number of first returned line")
    end_line: int = Field(..., description="1-indexed line number of last returned line")
    total_lines: int = Field(..., description="Total lines in the file")
    truncated: bool = Field(..., description="True if output was truncated due to limit or size cap")
    is_binary: bool = Field(..., description="True if file was detected as binary")
    content_hash: Optional[str] = Field(None, description="SHA-256 hex digest of the entire raw file bytes")
    error: Optional[str] = Field(None, description="Error message if read operation failed for this file")


class ReadMultipleFilesInput(BaseModel):
    file_paths: List[str] = Field(..., description="List of relative file paths to read")
    project_path: str = Field(".", description="Absolute or relative path to the project root directory")
    limit_per_file: Optional[int] = Field(None, description="Maximum lines to read per file")


class ReadMultipleFilesOutput(BaseModel):
    results: List[ReadFileOutput] = Field(..., description="List of read results per file")


class SearchMatch(BaseModel):
    file_path: str = Field(..., description="Relative path to matching file")
    line_number: Optional[int] = Field(None, description="Line number of match (content search mode)")
    snippet: Optional[str] = Field(None, description="Matching line snippet with context (content search mode)")


class SearchFilesInput(BaseModel):
    query: str = Field(..., description="Search term or pattern")
    project_path: str = Field(".", description="Absolute or relative path to project root")
    search_type: Literal["content", "filename"] = Field("content", description="Search content or filename")
    file_pattern: Optional[str] = Field(None, description="Glob pattern to filter target files e.g. '*.py'")
    case_sensitive: bool = Field(False, description="Case-sensitive search flag")
    regex: bool = Field(False, description="Whether to evaluate query as a regular expression (default False)")
    max_results: int = Field(50, description="Maximum results to return")
    offset: int = Field(0, description="Pagination offset index")


class SearchFilesOutput(BaseModel):
    matches: List[SearchMatch] = Field(..., description="Matching search hits")
    total_matches: int = Field(..., description="Count of matches returned in this page")
    has_more: bool = Field(..., description="True if more matches exist beyond current offset/max_results")


# ==========================================
# Write & Edit Operation Schemas (Part 3)
# ==========================================


class WriteFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path to target file from project_path (e.g. 'index.html' or 'css/style.css', do not repeat project folder name)")
    project_path: str = Field(".", description="Absolute or relative path to project root (e.g. 'C:\\MyProject\\WorkPulse')")
    content: str = Field(..., description="Clean, properly indented multi-line source code to write into the file. Never minify or collapse code into a single line unless writing a minified asset.")
    overwrite: bool = Field(False, description="Set to True to allow overwriting an existing file (default False)")
    create_parents: bool = Field(False, description="Set to True to automatically create missing parent directories (e.g. css/, js/modules/)")
    expected_hash: Optional[str] = Field(None, description="Expected SHA-256 hash of existing file for staleness check")
    dry_run: bool = Field(False, description="If True, preview changes with diff without writing to disk")



class WriteFileOutput(BaseModel):
    file_path: str = Field(..., description="Relative path to the file")
    created: bool = Field(..., description="True if a new file was created")
    overwritten: bool = Field(..., description="True if an existing file was overwritten")
    bytes_written: int = Field(..., description="Number of bytes written or would be written")
    new_hash: str = Field(..., description="SHA-256 hex digest of the new file content")
    diff: Optional[str] = Field(None, description="Unified diff preview (for overwrites)")
    dry_run: bool = Field(False, description="True if operation was dry-run preview only")


class EditOperation(BaseModel):
    old_string: str = Field(..., min_length=1, description="Exact string to find and replace in the file")
    new_string: str = Field(..., description="Replacement string (empty string deletes old_string)")
    replace_all: bool = Field(False, description="If True, replace all occurrences; if False, fail if old_string is not unique")


class EditFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path to target file from project root")
    project_path: str = Field(".", description="Absolute or relative path to project root")
    edits: List[EditOperation] = Field(..., min_length=1, max_length=50, description="List of 1-50 edit operations to apply sequentially")
    expected_hash: Optional[str] = Field(None, description="Expected SHA-256 hash of existing file for staleness check")
    dry_run: bool = Field(False, description="If True, preview changes with diff without writing to disk")


class EditFileOutput(BaseModel):
    file_path: str = Field(..., description="Relative path to the file")
    edits_applied: int = Field(..., description="Number of edit operations successfully applied")
    replacements_made: int = Field(..., description="Total string replacements made across all edits")
    diff: str = Field(..., description="Unified diff of the changes")
    new_hash: str = Field(..., description="SHA-256 hex digest of the file after edits")
    dry_run: bool = Field(False, description="True if operation was dry-run preview only")


# ==========================================
# File-Level Operations & Replace (Part 4)
# ==========================================


class DeleteFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path to target file from project root")
    project_path: str = Field(".", description="Absolute or relative path to project root")


class DeleteFileOutput(BaseModel):
    file_path: str = Field(..., description="Relative path of deleted file")
    deleted: bool = Field(..., description="True if file was successfully deleted")
    size_bytes: int = Field(..., description="Size of deleted file in bytes")


class MoveFileInput(BaseModel):
    source_path: str = Field(..., description="Relative path to source file from project root")
    destination_path: str = Field(..., description="Relative path to destination file from project root")
    project_path: str = Field(".", description="Absolute or relative path to project root")
    create_parents: bool = Field(False, description="Whether to create missing parent directories for destination (default False)")


class MoveFileOutput(BaseModel):
    source_path: str = Field(..., description="Relative path to source file")
    destination_path: str = Field(..., description="Relative path to destination file")


class CopyFileInput(BaseModel):
    source_path: str = Field(..., description="Relative path to source file from project root")
    destination_path: str = Field(..., description="Relative path to destination file from project root")
    project_path: str = Field(".", description="Absolute or relative path to project root")
    create_parents: bool = Field(False, description="Whether to create missing parent directories for destination (default False)")


class CopyFileOutput(BaseModel):
    source_path: str = Field(..., description="Relative path to source file")
    destination_path: str = Field(..., description="Relative path to destination file")
    bytes_copied: int = Field(..., description="Number of bytes copied")


class ReplaceInFilesInput(BaseModel):
    find: str = Field(..., min_length=1, description="String or regex pattern to search for across files")
    replace: str = Field(..., description="Replacement string (supports regex back-references in regex mode)")
    file_pattern: str = Field(..., description="Glob pattern to filter target files e.g. '*.py' (required)")
    project_path: str = Field(".", description="Absolute or relative path to project root")
    subpath: Optional[str] = Field(None, description="Optional subdirectory relative to project root to limit scope")
    regex: bool = Field(False, description="Whether find pattern is a regular expression (default False)")
    case_sensitive: bool = Field(True, description="Whether matching should be case-sensitive (default True)")
    dry_run: bool = Field(True, description="If True, preview replacement diffs without modifying files (default True)")
    expected_replacements: Optional[int] = Field(None, description="Expected total replacement count for safety verification")


class ReplaceFileResult(BaseModel):
    file_path: str = Field(..., description="Relative path to changed file")
    replacements: int = Field(..., description="Number of replacements made in this file")
    diff: str = Field(..., description="Unified diff preview of changes in this file")


class ReplaceInFilesOutput(BaseModel):
    dry_run: bool = Field(..., description="True if operation was dry-run preview only")
    files_changed: int = Field(..., description="Total number of files changed (or would be changed)")
    total_replacements: int = Field(..., description="Total string replacements made (or would be made)")
    results: List[ReplaceFileResult] = Field(..., description="List of per-file change results and diffs")
    skipped: List[dict] = Field(default_factory=list, description="List of skipped files with reasons (e.g. binary, protected, changed)")
    partial: bool = Field(False, description="True if operation stopped mid-way due to an error")
    error: Optional[str] = Field(None, description="Error message if operation encountered a fatal error or mismatch")

