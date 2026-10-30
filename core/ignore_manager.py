from pathlib import Path
from typing import Dict, List, Optional
import pathspec
import config
from utils.logger import logger


class IgnoreManager:
    """
    Handles ignore rules using pathspec with fallback to config.DEFAULT_IGNORE_PATTERNS.
    Caches parsed specs per project root for performance.
    """
    _cache: Dict[str, "IgnoreManager"] = {}

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.spec = self._build_spec()
        self.allow_spec = self._build_allow_spec()

    @classmethod
    def get_for_project(cls, project_root: Path) -> "IgnoreManager":
        key = str(project_root.resolve())
        if key not in cls._cache:
            cls._cache[key] = cls(project_root)
        return cls._cache[key]

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()

    def _build_spec(self) -> pathspec.PathSpec:
        patterns: List[str] = list(config.DEFAULT_IGNORE_PATTERNS)

        # Look for .gitignore in project root
        gitignore_path = self.project_root / ".gitignore"
        if gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception as e:
                logger.warning(f"Error reading .gitignore in {self.project_root}: {e}")

        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def _build_allow_spec(self) -> Optional[pathspec.PathSpec]:
        patterns: List[str] = list(config.CODESCOPE_ALLOW_IGNORED)

        # Optional project-level override files (.codescopeallowed or .codescopeallow)
        for fname in (".codescopeallowed", ".codescopeallow"):
            fpath = self.project_root / fname
            if fpath.is_file():
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                patterns.append(line)
                except Exception as e:
                    logger.warning(f"Error reading {fname} in {self.project_root}: {e}")

        if not patterns:
            return None
        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def is_allowed_override(self, relative_path: str, is_dir: bool = False) -> bool:
        """
        Returns True if relative_path matches any pattern in CODESCOPE_ALLOW_IGNORED,
        allowing it to be accessed for read/write even if ignored by .gitignore.
        Never allows protected paths (.env, .git, keys, .codescope.toml).
        """
        if not self.allow_spec or not relative_path:
            return False

        clean_path = relative_path.replace("\\", "/").strip("/")
        if clean_path.startswith("./"):
            clean_path = clean_path[2:]

        # Defense in depth: Never allow override for protected paths (.env, .git, keys, etc.)
        from core import safety
        if safety.is_protected(clean_path):
            return False

        if is_dir and not clean_path.endswith("/"):
            clean_path_dir = clean_path + "/"
            if self.allow_spec.match_file(clean_path_dir):
                return True

        return self.allow_spec.match_file(clean_path)

    def is_ignored(self, relative_path: str, is_dir: bool = False, allow_overrides: bool = False) -> bool:
        """
        Returns True if relative_path matches ignore rules.
        When allow_overrides=True, paths matching CODESCOPE_ALLOW_IGNORED return False (not ignored).
        By default (allow_overrides=False), strictly respects .gitignore (used by list_directory_tree).
        """
        if not relative_path:
            return False

        if allow_overrides and self.is_allowed_override(relative_path, is_dir=is_dir):
            return False

        clean_path = relative_path.replace("\\", "/").strip("/")
        if clean_path.startswith("./"):
            clean_path = clean_path[2:]

        if is_dir and not clean_path.endswith("/"):
            clean_path_dir = clean_path + "/"
            if self.spec.match_file(clean_path_dir):
                return True

        return self.spec.match_file(clean_path)


def clear_cache():
    """Module-level helper to clear the IgnoreManager cache."""
    IgnoreManager.clear_cache()
