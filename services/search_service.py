import fnmatch
from pathlib import Path
from typing import List, Optional, Iterator
import config
from core.path_security import resolve_and_verify, is_within
from core.ignore_manager import IgnoreManager
from core.file_classifier import is_binary_file
from core.regex_utils import compile_pattern, safe_search, PatternError
from models.schemas import SearchMatch, SearchFilesOutput


def iter_searchable_files(
    project_root: Path,
    *,
    subpath: Optional[str] = None,
    file_pattern: Optional[str] = None
) -> Iterator[Path]:
    """
    Yields searchable non-ignored file paths within project_root (or subpath)
    that match file_pattern.
    """
    root_path = project_root.resolve()
    if subpath:
        start_dir = resolve_and_verify(str(root_path), subpath)
        if not start_dir.is_dir():
            return
    else:
        start_dir = root_path

    ignore_mgr = IgnoreManager.get_for_project(root_path)

    def _walk(current_dir: Path) -> Iterator[Path]:
        try:
            entries = sorted(list(current_dir.iterdir()), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return

        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue

            try:
                rel_str = str(entry.relative_to(root_path)).replace("\\", "/")
            except ValueError:
                continue

            if entry.is_dir():
                if not ignore_mgr.is_ignored(rel_str, is_dir=True):
                    yield from _walk(entry)
            elif entry.is_file():
                if not ignore_mgr.is_ignored(rel_str, is_dir=False):
                    if file_pattern:
                        if fnmatch.fnmatch(name, file_pattern) or fnmatch.fnmatch(rel_str, file_pattern):
                            yield entry
                    else:
                        yield entry

    yield from _walk(start_dir)


def search(
    project_path: str,
    query: str,
    search_type: str = "content",
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    regex: bool = False,
    max_results: int = 50,
    offset: int = 0
) -> SearchFilesOutput:
    """
    Searches files in the project root by filename or full-text content with pagination and regex support.
    """
    if not query:
        return SearchFilesOutput(matches=[], total_matches=0, has_more=False)

    root_path = resolve_and_verify(project_path, "")

    all_matches: List[SearchMatch] = []

    # Compile search pattern
    pattern = compile_pattern(query, regex_mode=regex, case_sensitive=case_sensitive)

    candidate_files = list(iter_searchable_files(root_path, file_pattern=file_pattern))

    if search_type == "filename":
        for fpath in candidate_files:
            rel_str = str(fpath.relative_to(root_path)).replace("\\", "/")
            name_str = fpath.name

            if regex:
                if safe_search(pattern, rel_str) or safe_search(pattern, name_str):
                    all_matches.append(SearchMatch(file_path=rel_str, line_number=None, snippet=None))
            else:
                query_check = query if case_sensitive else query.lower()
                name_check = name_str if case_sensitive else name_str.lower()
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
                        if safe_search(pattern, line):
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

