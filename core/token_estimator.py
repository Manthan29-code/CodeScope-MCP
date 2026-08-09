from pathlib import Path


def estimate_tokens(text: str) -> int:
    """
    Provides a fast heuristic estimate of token count for a text string (~4 chars per token).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_file_tokens(file_path: Path, size_bytes: int) -> int:
    """
    Provides a fast estimate of token count from file size in bytes (~4 bytes per token).
    """
    if size_bytes <= 0:
        return 0
    return max(1, size_bytes // 4)
