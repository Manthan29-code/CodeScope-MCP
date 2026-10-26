"""Cross-platform subprocess runner. Never uses a shell."""
from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

IS_WINDOWS = sys.platform.startswith("win")


class ExecutableNotFound(RuntimeError):
    """A required executable is not on PATH."""


@dataclass(frozen=True)
class RunResult:
    argv: List[str]
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def resolve_executable(name: str) -> str:
    """Resolve an executable on PATH. On Windows this honours PATHEXT (.exe, .cmd, .bat)."""
    found = shutil.which(name)
    if not found:
        raise ExecutableNotFound(f"'{name}' was not found on PATH")
    return found


def truncate_middle(text: str, limit: int) -> Tuple[str, bool]:
    """Keep the head and tail of long output, which is where errors usually are."""
    if limit <= 0 or len(text) <= limit:
        return text, False
    half = limit // 2
    omitted = len(text) - 2 * half
    return f"{text[:half]}\n... [{omitted} characters omitted] ...\n{text[-half:]}", True


def base_env(extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    env.update({"NO_COLOR": "1", "PYTHONIOENCODING": "utf-8", "CI": "true"})
    if extra:
        env.update(extra)
    return env


def _kill_tree(proc: "subprocess.Popen[bytes]") -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            # taskkill ships with Windows and terminates the whole child tree.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=False,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _run_blocking(argv: List[str], cwd: str, env: Dict[str, str],
                  timeout: float, max_output_chars: int) -> RunResult:
    start = time.monotonic()
    spawn_kwargs = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS
        else {"start_new_session": True}   # own process group, so the tree can be killed
    )
    proc = subprocess.Popen(
        argv, cwd=cwd, env=env, shell=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **spawn_kwargs,
    )
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = b"", b""

    out_text, out_cut = truncate_middle(out.decode("utf-8", errors="replace"), max_output_chars)
    err_text, err_cut = truncate_middle(err.decode("utf-8", errors="replace"), max_output_chars)
    return RunResult(
        argv=argv, exit_code=proc.returncode, stdout=out_text, stderr=err_text,
        duration_s=round(time.monotonic() - start, 3),
        timed_out=timed_out, truncated=out_cut or err_cut,
    )


async def run_command(argv: Sequence[str], *, cwd, timeout: float = 30,
                      env: Optional[Mapping[str, str]] = None,
                      max_output_chars: int = 20000) -> RunResult:
    args = list(argv)
    args[0] = resolve_executable(args[0])
    return await asyncio.to_thread(
        _run_blocking, args, str(cwd), dict(env) if env else base_env(), timeout, max_output_chars
    )
