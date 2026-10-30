import os
import re
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Server Settings
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
DEFAULT_PROJECT_PATH: str = os.getenv("DEFAULT_PROJECT_PATH", str(Path.cwd().resolve()))
PROJECT_ROOT: Path = Path(DEFAULT_PROJECT_PATH).resolve()

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

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

# Whitelist of patterns ignored in .gitignore that CodeScope MCP is allowed to access
# (e.g. "*.md,plan/**,spec.md")
_allow_ignored_raw = os.getenv("CODESCOPE_ALLOW_IGNORED", "").strip()
CODESCOPE_ALLOW_IGNORED: List[str] = [
    p.strip() for p in re.split(r"[,;]", _allow_ignored_raw) if p.strip()
] if _allow_ignored_raw else []

def _parse_roots(raw_str: str) -> List[str]:
    if not raw_str:
        return []
    if os.pathsep in raw_str:
        tokens = raw_str.split(os.pathsep)
    elif "," in raw_str:
        tokens = raw_str.split(",")
    else:
        tokens = [raw_str]
    return [t.strip() for t in tokens if t.strip()]


# Project Roots & Access Control (SEC-002)
_central_roots_raw = os.getenv("ALLOWED_PROJECT_ROOTS", "").strip()
ALLOWED_PROJECT_ROOTS: List[str] = _parse_roots(_central_roots_raw)

_read_roots_raw = os.getenv("READ_ALLOWED_ROOTS", "").strip()
if _read_roots_raw:
    READ_ALLOWED_ROOTS: List[str] = _parse_roots(_read_roots_raw)
elif ALLOWED_PROJECT_ROOTS:
    READ_ALLOWED_ROOTS: List[str] = list(ALLOWED_PROJECT_ROOTS)
else:
    READ_ALLOWED_ROOTS: List[str] = []

# Write Operations Settings (Part 3)
ENABLE_WRITE_TOOLS: bool = os.getenv("ENABLE_WRITE_TOOLS", "false").lower() in ("true", "1", "yes")

_allowed_roots_raw = os.getenv("WRITE_ALLOWED_ROOTS", "").strip()
if _allowed_roots_raw:
    WRITE_ALLOWED_ROOTS: List[str] = _parse_roots(_allowed_roots_raw)
elif ALLOWED_PROJECT_ROOTS:
    WRITE_ALLOWED_ROOTS: List[str] = list(ALLOWED_PROJECT_ROOTS)
else:
    WRITE_ALLOWED_ROOTS: List[str] = []

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
    ".codescope.toml",
]

# Replace and Regex Operations Settings (Part 4)
MAX_FILES_PER_REPLACE: int = int(os.getenv("MAX_FILES_PER_REPLACE", "100"))
REGEX_TIMEOUT_SECONDS: float = float(os.getenv("REGEX_TIMEOUT_SECONDS", "2.0"))
MAX_REGEX_PATTERN_LENGTH: int = int(os.getenv("MAX_REGEX_PATTERN_LENGTH", "500"))

# Git Integration Settings
ENABLE_GIT_TOOLS: bool = _env_bool("ENABLE_GIT_TOOLS", False)
GIT_CONFIRM_MODE: str = os.getenv("GIT_CONFIRM_MODE", "auto").strip().lower()
if GIT_CONFIRM_MODE not in {"auto", "elicit", "code"}:
    GIT_CONFIRM_MODE = "auto"
GIT_CONFIRM_TTL_SECONDS: int = _env_int("GIT_CONFIRM_TTL_SECONDS", 300)
GIT_COMMAND_TIMEOUT_SECONDS: int = _env_int("GIT_COMMAND_TIMEOUT_SECONDS", 30)
GIT_MAX_DIFF_LINES: int = _env_int("GIT_MAX_DIFF_LINES", 2000)

# Automated Verification Settings
ENABLE_VERIFICATION_TOOLS: bool = _env_bool("ENABLE_VERIFICATION_TOOLS", False)
VERIFY_CONFIG_FILENAME: str = os.getenv("VERIFY_CONFIG_FILENAME", ".codescope.toml")
VERIFY_AUTODETECT: bool = _env_bool("VERIFY_AUTODETECT", True)
VERIFY_DEFAULT_TIMEOUT_SECONDS: int = _env_int("VERIFY_DEFAULT_TIMEOUT_SECONDS", 300)
VERIFY_MAX_OUTPUT_CHARS: int = _env_int("VERIFY_MAX_OUTPUT_CHARS", 20000)

