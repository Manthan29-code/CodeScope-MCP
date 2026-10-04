import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Server Settings
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
DEFAULT_PROJECT_PATH: str = os.getenv("DEFAULT_PROJECT_PATH", str(Path.cwd().resolve()))

# Security & Constraints
MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))  # 10 MB
MAX_LINES_PER_READ: int = int(os.getenv("MAX_LINES_PER_READ", "1000"))
ALLOW_SYMLINKS: bool = os.getenv("ALLOW_SYMLINKS", "false").lower() in ("true", "1", "yes")

# Default Ignore Patterns (fallback for projects without .gitignore or for common junk dirs)
DEFAULT_IGNORE_PATTERNS: List[str] = [
    "node_modules",
    "node_modules/",
    ".venv",
    ".venv/",
    "venv",
    "venv/",
    "env",
    "env/",
    ".git",
    ".git/",
    ".hg",
    ".svn",
    "__pycache__",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
    "dist",
    "dist/",
    "build",
    "build/",
    ".next",
    ".next/",
    ".nuxt",
    ".nuxt/",
    "*.egg-info",
    "*.egg-info/",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    ".DS_Store",
    "Thumbs.db",
]

# Write Operations Settings (Part 3)
ENABLE_WRITE_TOOLS: bool = os.getenv("ENABLE_WRITE_TOOLS", "false").lower() in ("true", "1", "yes")

_allowed_roots_raw = os.getenv("WRITE_ALLOWED_ROOTS", "").strip()
WRITE_ALLOWED_ROOTS: List[str] = [
    r.strip() for r in _allowed_roots_raw.split(os.pathsep) if r.strip()
] if _allowed_roots_raw else []

MAX_WRITE_SIZE_BYTES: int = int(os.getenv("MAX_WRITE_SIZE_BYTES", "1000000"))
MAX_EDITS_PER_CALL: int = int(os.getenv("MAX_EDITS_PER_CALL", "50"))
MAX_DIFF_CHARS: int = int(os.getenv("MAX_DIFF_CHARS", "20000"))
BLOCK_WRITES_TO_IGNORED: bool = os.getenv("BLOCK_WRITES_TO_IGNORED", "true").lower() in ("true", "1", "yes")

PROTECTED_PATH_PATTERNS: List[str] = [
    ".git/",
    ".env",
    ".env.*",
    "!.env.example",
    "*.pem",
    "*.key",
    "id_rsa*",
    "id_ed25519*",
]
