import difflib
from typing import Tuple
import config


def unified_diff(
    old_text: str,
    new_text: str,
    rel_path: str,
    context_lines: int = 3
) -> str:
    """
    Generates a unified diff between old_text and new_text with POSIX file labels.
    Returns empty string if identical.
    Truncates output if longer than config.MAX_DIFF_CHARS.
    """
    if old_text == new_text:
        return ""

    rel_posix = rel_path.replace("\\", "/").lstrip("/")
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_posix}",
            tofile=f"b/{rel_posix}",
            lineterm="",
            n=context_lines
        )
    )

    full_diff = "\n".join(diff_lines)
    max_chars = config.MAX_DIFF_CHARS

    if len(full_diff) <= max_chars:
        return full_diff

    kept_lines = []
    current_len = 0
    for idx, line in enumerate(diff_lines):
        remaining = len(diff_lines) - idx
        marker = f"\n... diff truncated ({remaining} more lines)"
        if current_len + len(line) + 1 + len(marker) > max_chars and kept_lines:
            remaining_total = len(diff_lines) - len(kept_lines)
            return "\n".join(kept_lines) + f"\n... diff truncated ({remaining_total} more lines)"
        kept_lines.append(line)
        current_len += len(line) + 1

    if kept_lines:
        remaining_total = len(diff_lines) - len(kept_lines)
        if remaining_total > 0:
            return "\n".join(kept_lines) + f"\n... diff truncated ({remaining_total} more lines)"
        return "\n".join(kept_lines)

    # If even the first line is longer than max_chars
    return full_diff[:max_chars] + f"\n... diff truncated ({len(diff_lines)} more lines)"


def count_changed_lines(old_text: str, new_text: str) -> Tuple[int, int]:
    """
    Counts added and removed lines between old_text and new_text.
    Returns (added_count, removed_count).
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    added = 0
    removed = 0
    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    return added, removed
