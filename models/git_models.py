from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatusEntry(BaseModel):
    path: str
    kind: str                      # changed | renamed | unmerged | untracked | ignored
    index_status: str
    worktree_status: str
    orig_path: Optional[str] = None


class GitStatus(BaseModel):
    branch: Optional[str] = None   # None when HEAD is detached
    head_sha: Optional[str] = None
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    entries: List[StatusEntry] = Field(default_factory=list)
    has_tracked_changes: bool = False
    is_clean: bool = True


class DiffResult(BaseModel):
    diff: str
    truncated: bool
    total_lines: int


class CommitInfo(BaseModel):
    sha: str
    author: str
    date: str
    subject: str


class BranchInfo(BaseModel):
    name: str
    sha: str
    is_current: bool


class OperationResult(BaseModel):
    message: str
    head_before: Optional[str] = None
    head_after: Optional[str] = None
    backup_ref: Optional[str] = None


class Prepared(BaseModel):
    """A dangerous action that has been validated and previewed but not executed."""
    tool: str
    args: Dict[str, Any]
    summary: str
    preview: str
    fingerprint: str
