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
    project_path: str = Field(..., description="Absolute path to the project root directory")
    max_depth: Optional[int] = Field(None, description="Maximum directory traversal depth (None for unlimited)")
    include_hidden: bool = Field(False, description="Whether to include hidden files/directories (starting with '.')")


class ListDirectoryOutput(BaseModel):
    project_path: str = Field(..., description="Absolute project root path")
    tree: TreeNode = Field(..., description="Root tree node containing directory structure")
    total_files: int = Field(..., description="Total count of files listed")
    total_directories: int = Field(..., description="Total count of directories listed")


class FileMetadataInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to the project root directory")
    file_path: str = Field(..., description="Relative path to the target file from project root")


class FileMetadataOutput(BaseModel):
    file_path: str = Field(..., description="Relative path to the file")
    size_bytes: int = Field(..., description="File size in bytes")
    last_modified: str = Field(..., description="ISO 8601 formatted last modification timestamp")
    language: str = Field(..., description="Guessed programming language or file type")
    token_estimate: int = Field(..., description="Rough estimate of token count")
    is_binary: bool = Field(..., description="True if binary content was detected")


class ReadFileInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to the project root directory")
    file_path: str = Field(..., description="Relative path to the target file from project root")
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
    error: Optional[str] = Field(None, description="Error message if read operation failed for this file")


class ReadMultipleFilesInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to the project root directory")
    file_paths: List[str] = Field(..., description="List of relative file paths to read")
    limit_per_file: Optional[int] = Field(None, description="Maximum lines to read per file")


class ReadMultipleFilesOutput(BaseModel):
    results: List[ReadFileOutput] = Field(..., description="List of read results per file")


class SearchMatch(BaseModel):
    file_path: str = Field(..., description="Relative path to matching file")
    line_number: Optional[int] = Field(None, description="Line number of match (content search mode)")
    snippet: Optional[str] = Field(None, description="Matching line snippet with context (content search mode)")


class SearchFilesInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to project root")
    query: str = Field(..., description="Search term or pattern")
    search_type: Literal["content", "filename"] = Field("content", description="Search content or filename")
    file_pattern: Optional[str] = Field(None, description="Glob pattern to filter target files e.g. '*.py'")
    case_sensitive: bool = Field(False, description="Case-sensitive search flag")
    max_results: int = Field(50, description="Maximum results to return")
    offset: int = Field(0, description="Pagination offset index")


class SearchFilesOutput(BaseModel):
    matches: List[SearchMatch] = Field(..., description="Matching search hits")
    total_matches: int = Field(..., description="Count of matches returned in this page")
    has_more: bool = Field(..., description="True if more matches exist beyond current offset/max_results")
