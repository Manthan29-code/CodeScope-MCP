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
    "pnpm-lock.yaml",
    ".DS_Store",
    "Thumbs.db",
]
