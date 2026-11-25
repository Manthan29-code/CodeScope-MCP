import os
import re
from pathlib import Path
from typing import List
from dotenv import load_dotenv, dotenv_values

SERVER_DIR: Path = Path(__file__).resolve().parent
ENV_PATH: Path = SERVER_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)
try:
    _last_env_mtime: float = ENV_PATH.stat().st_mtime if ENV_PATH.is_file() else -1.0
except OSError:
    _last_env_mtime = -1.0

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
if GIT_CONFIRM_MODE not in {"auto", "elicit", "code", "direct"}:
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



def reload_if_changed() -> bool:
    """
    Checks if .env has been modified on disk. If modified, reloads .env
    with override=True and updates all dynamic configuration variables in memory.
    Returns True if a reload occurred, False otherwise.
    Takes ~5 microseconds when file has not changed.
    """
    global _last_env_mtime, ALLOWED_PROJECT_ROOTS, READ_ALLOWED_ROOTS, WRITE_ALLOWED_ROOTS
    global ENABLE_WRITE_TOOLS, MAX_WRITE_SIZE_BYTES, MAX_EDITS_PER_CALL, MAX_DIFF_CHARS
    global BLOCK_WRITES_TO_IGNORED, CODESCOPE_ALLOW_IGNORED, _allow_ignored_raw
    global MAX_FILES_PER_REPLACE, REGEX_TIMEOUT_SECONDS, MAX_REGEX_PATTERN_LENGTH
    global ENABLE_GIT_TOOLS, GIT_CONFIRM_MODE, GIT_CONFIRM_TTL_SECONDS
    global GIT_COMMAND_TIMEOUT_SECONDS, GIT_MAX_DIFF_LINES
    global ENABLE_VERIFICATION_TOOLS, VERIFY_CONFIG_FILENAME, VERIFY_AUTODETECT
    global VERIFY_DEFAULT_TIMEOUT_SECONDS, VERIFY_MAX_OUTPUT_CHARS

    try:
        if not ENV_PATH.is_file():
            return False
        mtime = ENV_PATH.stat().st_mtime
    except OSError:
        return False

    if mtime <= _last_env_mtime:
        return False

    load_dotenv(dotenv_path=ENV_PATH, override=True)
    _last_env_mtime = mtime

    vals = dotenv_values(dotenv_path=ENV_PATH)
    for k, v in vals.items():
        if v is not None:
            os.environ[k] = v

    # Project Roots & Access Control (SEC-002)
    _central_roots_raw = vals.get("ALLOWED_PROJECT_ROOTS", os.getenv("ALLOWED_PROJECT_ROOTS", "")).strip()
    ALLOWED_PROJECT_ROOTS = _parse_roots(_central_roots_raw)

    if "READ_ALLOWED_ROOTS" in vals:
        _read_roots_raw = (vals["READ_ALLOWED_ROOTS"] or "").strip()
        READ_ALLOWED_ROOTS = _parse_roots(_read_roots_raw)
    elif ALLOWED_PROJECT_ROOTS:
        READ_ALLOWED_ROOTS = list(ALLOWED_PROJECT_ROOTS)
    else:
        _read_roots_raw = os.getenv("READ_ALLOWED_ROOTS", "").strip()
        READ_ALLOWED_ROOTS = _parse_roots(_read_roots_raw) if _read_roots_raw else []

    # Write Operations Settings
    if "ENABLE_WRITE_TOOLS" in vals:
        ENABLE_WRITE_TOOLS = (vals["ENABLE_WRITE_TOOLS"] or "false").lower() in ("true", "1", "yes")
    else:
        ENABLE_WRITE_TOOLS = os.getenv("ENABLE_WRITE_TOOLS", "false").lower() in ("true", "1", "yes")

    if "WRITE_ALLOWED_ROOTS" in vals:
        _allowed_roots_raw = (vals["WRITE_ALLOWED_ROOTS"] or "").strip()
        WRITE_ALLOWED_ROOTS = _parse_roots(_allowed_roots_raw)
    elif ALLOWED_PROJECT_ROOTS:
        WRITE_ALLOWED_ROOTS = list(ALLOWED_PROJECT_ROOTS)
    else:
        _allowed_roots_raw = os.getenv("WRITE_ALLOWED_ROOTS", "").strip()
        WRITE_ALLOWED_ROOTS = _parse_roots(_allowed_roots_raw) if _allowed_roots_raw else []

    _allow_ignored_raw = os.getenv("CODESCOPE_ALLOW_IGNORED", "").strip()
    CODESCOPE_ALLOW_IGNORED = [
        p.strip() for p in re.split(r"[,;]", _allow_ignored_raw) if p.strip()
    ] if _allow_ignored_raw else []

    BLOCK_WRITES_TO_IGNORED = os.getenv("BLOCK_WRITES_TO_IGNORED", "true").lower() in ("true", "1", "yes")
    MAX_WRITE_SIZE_BYTES = int(os.getenv("MAX_WRITE_SIZE_BYTES", "1000000"))
    MAX_EDITS_PER_CALL = int(os.getenv("MAX_EDITS_PER_CALL", "50"))
    MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "20000"))
    MAX_FILES_PER_REPLACE = int(os.getenv("MAX_FILES_PER_REPLACE", "100"))
    REGEX_TIMEOUT_SECONDS = float(os.getenv("REGEX_TIMEOUT_SECONDS", "2.0"))
    MAX_REGEX_PATTERN_LENGTH = int(os.getenv("MAX_REGEX_PATTERN_LENGTH", "500"))
    MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))
    MAX_LINES_PER_READ = int(os.getenv("MAX_LINES_PER_READ", "1000"))
    ALLOW_SYMLINKS = os.getenv("ALLOW_SYMLINKS", "false").lower() in ("true", "1", "yes")

    ENABLE_GIT_TOOLS = _env_bool("ENABLE_GIT_TOOLS", False)
    _git_mode = os.getenv("GIT_CONFIRM_MODE", "auto").strip().lower()
    GIT_CONFIRM_MODE = _git_mode if _git_mode in {"auto", "elicit", "code", "direct"} else "auto"
    GIT_CONFIRM_TTL_SECONDS = _env_int("GIT_CONFIRM_TTL_SECONDS", 300)
    GIT_COMMAND_TIMEOUT_SECONDS = _env_int("GIT_COMMAND_TIMEOUT_SECONDS", 30)
    GIT_MAX_DIFF_LINES = _env_int("GIT_MAX_DIFF_LINES", 2000)

    ENABLE_VERIFICATION_TOOLS = _env_bool("ENABLE_VERIFICATION_TOOLS", False)
    VERIFY_CONFIG_FILENAME = os.getenv("VERIFY_CONFIG_FILENAME", ".codescope.toml")
    VERIFY_AUTODETECT = _env_bool("VERIFY_AUTODETECT", True)
    VERIFY_DEFAULT_TIMEOUT_SECONDS = _env_int("VERIFY_DEFAULT_TIMEOUT_SECONDS", 300)
    VERIFY_MAX_OUTPUT_CHARS = _env_int("VERIFY_MAX_OUTPUT_CHARS", 20000)

    try:
        from core import ignore_manager
        ignore_manager.clear_cache()
    except Exception:
        pass

    try:
        from utils.logger import logger
        logger.info(f"Hot-reloaded .env: READ_ALLOWED_ROOTS={READ_ALLOWED_ROOTS}, WRITE_ALLOWED_ROOTS={WRITE_ALLOWED_ROOTS}")
    except Exception:
        pass

    return True
