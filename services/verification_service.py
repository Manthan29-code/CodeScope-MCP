"""Runs named build/lint/test checks. The LLM can only run checks defined here, never raw commands."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import tomllib                      # Python 3.11+
except ModuleNotFoundError:             # pragma: no cover
    import tomli as tomllib

from models.verify_models import CheckResult, CheckSpec, CheckSummary
from utils.git_validators import to_repo_relative
from utils.process_runner import IS_WINDOWS, ExecutableNotFound, base_env, run_command

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class VerificationError(RuntimeError):
    pass


class VerificationService:
    def __init__(self, project_root, *, config_filename: str = ".codescope.toml", autodetect: bool = True,
                 default_timeout: int = 300, max_output_chars: int = 20000):
        self.root = Path(project_root).resolve()
        self.config_filename = config_filename
        self.autodetect = autodetect
        self.default_timeout = default_timeout
        self.max_output_chars = max_output_chars
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ---------------------------------------------------------------- python lookup
    def project_python(self) -> str:
        """Prefer the project's own virtualenv. Layout differs: Scripts\\python.exe on Windows, bin/python elsewhere."""
        rel = Path("Scripts") / "python.exe" if IS_WINDOWS else Path("bin") / "python"
        for folder in (".venv", "venv", "env"):
            candidate = self.root / folder / rel
            if candidate.is_file():
                return str(candidate)
        return sys.executable

    # ---------------------------------------------------------------- loading
    def load_checks(self) -> Dict[str, CheckSpec]:
        """Re-read on every call so human edits to the config apply immediately."""
        configured = self._load_config()
        if configured:
            return configured
        return self._autodetect() if self.autodetect else {}

    def _load_config(self) -> Dict[str, CheckSpec]:
        path = self.root / self.config_filename
        if not path.is_file():
            return {}
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, ValueError) as exc:
            raise VerificationError(f"Cannot read {self.config_filename}: {exc}") from None
        py = self.project_python()
        out: Dict[str, CheckSpec] = {}
        for name, raw in (data.get("checks") or {}).items():
            if not _NAME_RE.fullmatch(name):
                raise VerificationError(f"Invalid check name '{name}'")
            cmd = raw.get("cmd")
            if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
                raise VerificationError(f"checks.{name}.cmd must be a non-empty list of strings (shell strings are not allowed)")
            out[name] = CheckSpec(
                name=name, cmd=[x.replace("{python}", py) for x in cmd],
                description=str(raw.get("description", "")),
                timeout=int(raw.get("timeout", self.default_timeout)),
                cwd=to_repo_relative(self.root, str(raw.get("cwd", "."))), source="config",
            )
        return out

    def _autodetect(self) -> Dict[str, CheckSpec]:
        r, py = self.root, self.project_python()
        out: Dict[str, CheckSpec] = {}

        def add(name: str, cmd: List[str], desc: str) -> None:
            if name not in out:
                out[name] = CheckSpec(name=name, cmd=cmd, description=desc,
                                      timeout=self.default_timeout, source="auto")

        # Python
        pyproject = r / "pyproject.toml"
        py_text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.is_file() else ""
        if any((r / f).is_file() for f in ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "requirements.txt")):
            if (r / "ruff.toml").is_file() or (r / ".ruff.toml").is_file() or "[tool.ruff" in py_text:
                add("lint", [py, "-m", "ruff", "check", "."], "Ruff lint")
            if any((r / f).is_file() for f in ("pytest.ini", "tox.ini", "setup.cfg")) or "[tool.pytest" in py_text or (r / "tests").is_dir():
                add("test", [py, "-m", "pytest", "-q"], "pytest")

        # Node (script names come from a fixed tuple, so package.json cannot inject names)
        pkg = r / "package.json"
        if pkg.is_file():
            try:
                scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {}) or {}
            except (OSError, ValueError):
                scripts = {}
            pm = "pnpm" if (r / "pnpm-lock.yaml").is_file() else "yarn" if (r / "yarn.lock").is_file() else "npm"
            for name in ("build", "lint", "typecheck", "test"):
                if name in scripts:
                    add(name, [pm, "run", name], f"{pm} run {name}")

        # Rust
        if (r / "Cargo.toml").is_file():
            add("build", ["cargo", "build"], "cargo build")
            add("lint", ["cargo", "clippy"], "cargo clippy")
            add("test", ["cargo", "test"], "cargo test")

        # Go
        if (r / "go.mod").is_file():
            add("build", ["go", "build", "./..."], "go build")
            add("lint", ["go", "vet", "./..."], "go vet")
            add("test", ["go", "test", "./..."], "go test")
        return out

    # ---------------------------------------------------------------- running
    async def run_check(self, name: str) -> CheckResult:
        checks = self.load_checks()
        spec = checks.get(name)
        if spec is None:
            raise VerificationError(f"Unknown check '{name}'. Available: {', '.join(checks) or 'none'}")
        display = " ".join(spec.cmd)
        try:
            async with self._get_lock():            # one check at a time
                res = await run_command(spec.cmd, cwd=self.root / spec.cwd, timeout=spec.timeout,
                                        env=base_env(), max_output_chars=self.max_output_chars)
        except ExecutableNotFound as exc:
            return CheckResult(name=name, command=display, passed=False, error=str(exc))
        return CheckResult(name=name, command=display, passed=res.ok, exit_code=res.exit_code,
                           duration_s=res.duration_s, timed_out=res.timed_out, truncated=res.truncated,
                           stdout_tail=res.stdout, stderr_tail=res.stderr)

    async def run_many(self, names: Optional[List[str]] = None, stop_on_failure: bool = False) -> CheckSummary:
        selected = names or list(self.load_checks().keys())
        if not selected:
            raise VerificationError("No checks are configured. Create .codescope.toml (see .codescope.toml.example).")
        results: List[CheckResult] = []
        for name in selected:
            result = await self.run_check(name)
            results.append(result)
            if stop_on_failure and not result.passed:
                break
        return CheckSummary(passed=all(r.passed for r in results), results=results)
