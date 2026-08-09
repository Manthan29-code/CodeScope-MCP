from pathlib import Path

# Common programming language extension mapping
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sql": "sql",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".kt": "kotlin",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
    ".env": "properties",
    ".ini": "ini",
    ".toml": "toml",
    ".txt": "text",
}


def is_binary_file(file_path: Path, sample_size: int = 8192) -> bool:
    """
    Checks if a file is binary by sniffing the first sample_size bytes for null bytes or non-text bytes.
    """
    if not file_path.is_file():
        return False
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(sample_size)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
            non_text = chunk.translate(None, text_characters)
            if len(non_text) / len(chunk) > 0.30:
                return True
            return False
    except Exception:
        return True


def guess_language(file_path: Path) -> str:
    """
    Guesses the programming language or file format from extension or file name.
    """
    name_lower = file_path.name.lower()
    if name_lower in EXTENSION_TO_LANGUAGE:
        return EXTENSION_TO_LANGUAGE[name_lower]

    ext_lower = file_path.suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext_lower, "text")
