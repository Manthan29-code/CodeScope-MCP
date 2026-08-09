import fnmatch
import re
from pathlib import Path
from typing import List, Optional
import config
from core.path_security import resolve_and_verify
from core.ignore_manager import IgnoreManager
from core.file_classifier import is_binary_file
from models.schemas import SearchMatch, SearchFilesOutput


def search(
    project_path: str,
    query: str,
    search_type: str = "content",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 50,
    offset: int = 0
) -> SearchFilesOutput:
    """
    Searches files in the project root by filename or full-text content with pagination support.
    """
    if not query:
        return SearchFilesOutput(matches=[], total_matches=0, has_more=False)

    root_path = resolve_and_verify(project_path, "")
    ignore_mgr = IgnoreManager.get_for_project(root_path)

    all_matches: List[SearchMatch] = []

    # Compile search pattern for content search
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error:
        # Fallback to escaped literal string matching if regex compilation fails
        pattern = re.compile(re.escape(query), flags)

    # Collect candidate files
    def collect_files(current_dir: Path) -> List[Path]:
        files: List[Path] = []
        try:
            entries = sorted(list(current_dir.iterdir()), key=lambda p: p.name.lower())
        except PermissionError:
            return files

        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue

            rel_str = str(entry.relative_to(root_path)).replace("\\", "/")

            if entry.is_dir():
                if not ignore_mgr.is_ignored(rel_str, is_dir=True):
                    files.extend(collect_files(entry))
            elif entry.is_file():
                if not ignore_mgr.is_ignored(rel_str, is_dir=False):
                    if file_pattern:
                        if fnmatch.fnmatch(name, file_pattern) or fnmatch.fnmatch(rel_str, file_pattern):
                            files.append(entry)
                    else:
                        files.append(entry)
        return files

    candidate_files = collect_files(root_path)

    if search_type == "filename":
        query_check = query if case_sensitive else query.lower()
        for fpath in candidate_files:
            rel_str = str(fpath.relative_to(root_path)).replace("\\", "/")
            name_check = fpath.name if case_sensitive else fpath.name.lower()
            rel_check = rel_str if case_sensitive else rel_str.lower()

            if query_check in name_check or query_check in rel_check or fnmatch.fnmatch(name_check, f"*{query_check}*"):
                all_matches.append(SearchMatch(file_path=rel_str, line_number=None, snippet=None))
    else:
        # Search content mode
        for fpath in candidate_files:
            try:
                if fpath.stat().st_size > config.MAX_FILE_SIZE_BYTES:
                    continue
                if is_binary_file(fpath):
                    continue

                rel_str = str(fpath.relative_to(root_path)).replace("\\", "/")

                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line_idx, line in enumerate(f, start=1):
                        if pattern.search(line):
                            snippet_text = line.strip()
                            if len(snippet_text) > 300:
                                snippet_text = snippet_text[:300] + "..."
                            all_matches.append(
                                SearchMatch(
                                    file_path=rel_str,
                                    line_number=line_idx,
                                    snippet=snippet_text
                                )
                            )
            except Exception:
                continue

    # Apply pagination
    if offset < 0:
        offset = 0

    page_matches = all_matches[offset : offset + max_results]
    has_more = (offset + max_results) < len(all_matches)

    return SearchFilesOutput(
        matches=page_matches,
        total_matches=len(page_matches),
        has_more=has_more
    )
