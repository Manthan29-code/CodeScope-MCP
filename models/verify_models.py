from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CheckSpec(BaseModel):
    name: str
    cmd: List[str]
    description: str = ""
    timeout: int = 300
    cwd: str = "."
    source: str = "config"          # config | auto


class CheckResult(BaseModel):
    name: str
    command: str
    passed: bool
    exit_code: Optional[int] = None
    duration_s: float = 0.0
    timed_out: bool = False
    truncated: bool = False
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: Optional[str] = None


class CheckSummary(BaseModel):
    passed: bool
    results: List[CheckResult] = Field(default_factory=list)
