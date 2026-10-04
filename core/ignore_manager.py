from pathlib import Path
from typing import Dict, List
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

    def is_ignored(self, relative_path: str, is_dir: bool = False) -> bool:
        """
        Returns True if relative_path matches ignore rules.
        """
        if not relative_path:
            return False

        clean_path = relative_path.replace("\\", "/").strip("/")
        if is_dir and not clean_path.endswith("/"):
            clean_path_dir = clean_path + "/"
            if self.spec.match_file(clean_path_dir):
                return True

        return self.spec.match_file(clean_path)


def clear_cache():
    """Module-level helper to clear the IgnoreManager cache."""
    IgnoreManager.clear_cache()
