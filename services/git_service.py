"""All git operations. Every command is an argument list. No shell is ever used."""
from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from models.git_models import (
    BranchInfo, CommitInfo, DiffResult, GitStatus, OperationResult, Prepared, StatusEntry,
)
from utils.git_validators import to_repo_relative, validate_ref_name, validate_revision
from utils.process_runner import RunResult, base_env, run_command, truncate_middle

MIN_GIT = (2, 23)   # git switch / git restore


class GitError(RuntimeError):
    pass


def parse_status_v2(raw: str) -> GitStatus:
    """Parse `git status --porcelain=v2 --branch -z`."""
    tokens = raw.split("\0")
    branch = head_sha = upstream = None
    ahead = behind = 0
    entries: List[StatusEntry] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if not tok:
            continue
        if tok.startswith("# "):
            parts = tok[2:].split(" ")
            key = parts[0]
            if key == "branch.oid":
                head_sha = None if parts[1] == "(initial)" else parts[1]
            elif key == "branch.head":
                branch = None if parts[1] == "(detached)" else parts[1]
            elif key == "branch.upstream":
                upstream = parts[1]
            elif key == "branch.ab":
                ahead, behind = int(parts[1].lstrip("+")), int(parts[2].lstrip("-"))
        elif tok[0] == "1":
            f = tok.split(" ", 8)
            entries.append(StatusEntry(path=f[8], kind="changed", index_status=f[1][0], worktree_status=f[1][1]))
        elif tok[0] == "2":
            f = tok.split(" ", 9)
            orig = tokens[i] if i < len(tokens) else None   # -z puts the original path in the next token
            i += 1
            entries.append(StatusEntry(path=f[9], kind="renamed", index_status=f[1][0],
                                       worktree_status=f[1][1], orig_path=orig))
        elif tok[0] == "u":
            f = tok.split(" ", 10)
            entries.append(StatusEntry(path=f[10], kind="unmerged", index_status=f[1][0], worktree_status=f[1][1]))
        elif tok[0] == "?":
            entries.append(StatusEntry(path=tok[2:], kind="untracked", index_status="?", worktree_status="?"))
        elif tok[0] == "!":
            entries.append(StatusEntry(path=tok[2:], kind="ignored", index_status="!", worktree_status="!"))
    tracked = any(e.kind in {"changed", "renamed", "unmerged"} for e in entries)
    return GitStatus(branch=branch, head_sha=head_sha, upstream=upstream, ahead=ahead, behind=behind,
                     entries=entries, has_tracked_changes=tracked, is_clean=not entries)


class GitService:
    def __init__(self, project_root, *, timeout: int = 30, max_diff_lines: int = 2000,
                 block_ignored: bool = True):
        self.root = Path(project_root).resolve()
        self.timeout = timeout
        self.max_diff_lines = max_diff_lines
        self.block_ignored = block_ignored
        self._checked = False
        self._write_lock: Optional[asyncio.Lock] = None

    # ------------------------------------------------------------------ plumbing
    def _lock(self) -> asyncio.Lock:
        if self._write_lock is None:
            self._write_lock = asyncio.Lock()
        return self._write_lock

    def _fail(self, args: Sequence[str], res: RunResult) -> GitError:
        sub = next((a for a in args if not a.startswith("-") and "=" not in a), "")
        detail = (res.stderr.strip() or res.stdout.strip() or "no output")[:500]
        detail = detail.replace(str(self.root), "<project>")
        reason = "timed out" if res.timed_out else f"exit {res.exit_code}"
        return GitError(f"git {sub} failed ({reason}): {detail}")

    async def _git(self, *args: str, check: bool = True, timeout: Optional[int] = None) -> RunResult:
        argv = ["git", "--no-pager"]
        if not (args and args[0] == "check-ignore"):
            argv.append("--literal-pathspecs")
        argv.extend(["-c", "core.quotepath=false", "-c", "color.ui=false", *args])
        env = base_env({
            "GIT_TERMINAL_PROMPT": "0",     # never wait for credentials
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_MERGE_AUTOEDIT": "no",     # never open an editor
            "LC_ALL": "C",                  # stable English messages for error handling
        })
        res = await run_command(argv, cwd=self.root, timeout=timeout or self.timeout, env=env)
        if check and not res.ok:
            raise self._fail(args, res)
        return res

    async def ensure_repo(self) -> None:
        if self._checked:
            return
        ver = await self._git("--version")
        m = re.search(r"(\d+)\.(\d+)", ver.stdout)
        if m and (int(m.group(1)), int(m.group(2))) < MIN_GIT:
            raise GitError(f"git {MIN_GIT[0]}.{MIN_GIT[1]}+ is required (found {m.group(0)})")
        inside = await self._git("rev-parse", "--is-inside-work-tree", check=False)
        if inside.stdout.strip() != "true":
            raise GitError("The project folder is not inside a git repository")
        self._checked = True

    async def head_sha(self) -> Optional[str]:
        res = await self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        return res.stdout.strip() or None if res.ok else None

    async def current_branch(self) -> Optional[str]:
        res = await self._git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        return res.stdout.strip() if res.ok else None

    async def resolve_commit(self, rev: str) -> str:
        rev = validate_revision(rev)
        res = await self._git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False)
        sha = res.stdout.strip()
        if not res.ok or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise GitError(f"Unknown revision: {rev}")
        return sha

    async def resolve_branch(self, name: str) -> str:
        name = validate_ref_name(name, "branch")
        res = await self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False)
        sha = res.stdout.strip()
        if not res.ok or not sha:
            raise GitError(f"Branch '{name}' does not exist")
        return sha

    async def _identity_args(self) -> List[str]:
        """Supply a fallback committer identity only when git has none configured."""
        args: List[str] = []
        for key, fallback in (("user.name", "CodeScope"), ("user.email", "codescope@localhost")):
            res = await self._git("config", "--get", key, check=False)
            if not res.ok or not res.stdout.strip():
                args += ["-c", f"{key}={fallback}"]
        return args

    async def _require_clean_tracked(self) -> None:
        if (await self.status()).has_tracked_changes:
            raise GitError("The working tree has uncommitted changes to tracked files. "
                           "Commit or restore them first.")

    async def _is_ignored(self, rel: str) -> bool:
        res = await self._git("check-ignore", "-q", "--", rel, check=False)
        if res.exit_code == 0:
            return True
        if res.exit_code == 1:
            return False
        raise self._fail(["check-ignore"], res)

    async def fingerprint(self, extra: str = "") -> str:
        head = await self.head_sha() or "none"
        st = await self._git("status", "--porcelain=v2", "-z", "--untracked-files=no")
        return hashlib.sha256(f"{head}\0{st.stdout}\0{extra}".encode()).hexdigest()

    async def _backup_ref(self, label: str, include_worktree: bool = False) -> Optional[str]:
        """Save a recovery point under refs/codescope/backup/ before any destructive step."""
        target: Optional[str] = None
        if include_worktree:
            ident = await self._identity_args()
            res = await self._git(*ident, "stash", "create", check=False)   # does not touch the working tree
            target = res.stdout.strip() or None
        if target is None:
            target = await self.head_sha()
        if not target:
            return None
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        ref = f"refs/codescope/backup/{stamp}-{secrets.token_hex(2)}-{label}"
        await self._git("update-ref", ref, target)
        return ref

    def _limit_lines(self, text: str, limit: int) -> DiffResult:
        lines = text.splitlines()
        total = len(lines)
        truncated = total > limit
        body = "\n".join(lines[:limit])
        if len(body) > 200_000:
            body, _ = truncate_middle(body, 200_000)
            truncated = True
        return DiffResult(diff=body, truncated=truncated, total_lines=total)

    # ------------------------------------------------------------------ READ tools
    async def status(self) -> GitStatus:
        res = await self._git("status", "--porcelain=v2", "--branch", "-z", "--untracked-files=normal")
        return parse_status_v2(res.stdout)

    async def diff(self, path: Optional[str] = None, staged: bool = False,
                   base: Optional[str] = None, max_lines: Optional[int] = None) -> DiffResult:
        # --no-ext-diff / --no-textconv stop repo-configured helper programs from running.
        args = ["diff", "--no-color", "--no-ext-diff", "--no-textconv"]
        if staged:
            args.append("--cached")
        if base:
            args.append(await self.resolve_commit(base))
        if path:
            args += ["--", to_repo_relative(self.root, path)]
        res = await self._git(*args)
        return self._limit_lines(res.stdout, min(max_lines or self.max_diff_lines, self.max_diff_lines))

    async def log(self, limit: int = 20, path: Optional[str] = None, rev: Optional[str] = None) -> List[CommitInfo]:
        limit = max(1, min(int(limit), 200))
        args = ["log", f"-n{limit}", "--no-color", "--format=%H%x1f%an%x1f%aI%x1f%s%x1e"]
        if rev:
            args.append(await self.resolve_commit(rev))
        if path:
            args += ["--", to_repo_relative(self.root, path)]
        res = await self._git(*args, check=False)
        if not res.ok:
            if "does not have any commits" in res.stderr:
                return []
            raise self._fail(args, res)
        commits: List[CommitInfo] = []
        for rec in res.stdout.split("\x1e"):
            rec = rec.strip("\n")
            if rec:
                sha, author, date, subject = rec.split("\x1f", 3)
                commits.append(CommitInfo(sha=sha, author=author, date=date, subject=subject))
        return commits

    async def show(self, rev: str = "HEAD", max_lines: Optional[int] = None) -> DiffResult:
        sha = await self.resolve_commit(rev)
        res = await self._git("show", "--no-color", "--no-ext-diff", "--no-textconv",
                              "--format=fuller", "--stat", "--patch", sha)
        return self._limit_lines(res.stdout, min(max_lines or self.max_diff_lines, self.max_diff_lines))

    async def branches(self) -> List[BranchInfo]:
        res = await self._git("for-each-ref", "--format=%(refname:short)%09%(objectname)%09%(HEAD)", "refs/heads")
        out: List[BranchInfo] = []
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                out.append(BranchInfo(name=parts[0], sha=parts[1], is_current=parts[2].strip() == "*"))
        return out

    # ------------------------------------------------------------------ LOW_WRITE tools
    async def create_branch(self, name: str, start_point: Optional[str] = None,
                            checkout: bool = False) -> OperationResult:
        name = validate_ref_name(name, "branch")
        await self._git("check-ref-format", "--branch", name)          # authoritative rules
        if (await self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False)).ok:
            raise GitError(f"Branch '{name}' already exists")
        start = await self.resolve_commit(start_point or "HEAD")
        before = await self.head_sha()
        async with self._lock():
            if checkout:
                await self._git("switch", "-c", name, start)
            else:
                await self._git("branch", name, start)
        return OperationResult(message=f"Created branch '{name}' at {start[:8]}" + (" and switched to it" if checkout else ""),
                               head_before=before, head_after=await self.head_sha())

    async def switch(self, branch: str) -> OperationResult:
        await self.resolve_branch(branch)
        await self._require_clean_tracked()
        before = await self.head_sha()
        async with self._lock():
            await self._git("switch", "--no-guess", branch)
        return OperationResult(message=f"Switched to '{branch}'", head_before=before, head_after=await self.head_sha())

    # ------------------------------------------------------------------ DANGEROUS: prepare
    async def prepare(self, tool: str, args: Dict[str, Any]) -> Prepared:
        if tool == "git_merge":
            return await self.prepare_merge(args["branch"])
        if tool == "git_revert":
            return await self.prepare_revert(args["commit"])
        if tool == "git_restore":
            return await self.prepare_restore(args["paths"])
        if tool == "git_commit":
            return await self.prepare_commit(args["message"], args.get("paths"))
        if tool == "git_push":
            return await self.prepare_push(args.get("remote", "origin"), args.get("branch"), args.get("set_upstream", False))
        raise GitError(f"Unknown action: {tool}")

    async def prepare_merge(self, branch: str) -> Prepared:
        sha = await self.resolve_branch(branch)
        current = await self.current_branch()
        if current == branch:
            raise GitError("Cannot merge a branch into itself")
        await self._require_clean_tracked()
        incoming = await self._git("log", "--oneline", "--no-color", "-n", "30", f"HEAD..{sha}")
        if not incoming.stdout.strip():
            raise GitError("Nothing to merge: the current branch already contains that branch")
        stat = await self._git("diff", "--stat", "--no-color", "--no-ext-diff", f"HEAD...{sha}")
        target = current or "detached HEAD"
        preview = (f"Merge '{branch}' ({sha[:8]}) into '{target}' with a merge commit.\n\n"
                   f"Commits to merge (max 30):\n{incoming.stdout.strip()}\n\nChanges:\n{stat.stdout.strip()}")
        return Prepared(tool="git_merge", args={"branch": branch},
                        summary=f"git_merge: merge '{branch}' into '{target}'",
                        preview=preview, fingerprint=await self.fingerprint(extra=sha))

    async def prepare_revert(self, commit: str) -> Prepared:
        sha = await self.resolve_commit(commit)
        await self._require_clean_tracked()
        parents = (await self._git("rev-list", "--parents", "-n", "1", sha)).stdout.split()
        if len(parents) > 2:
            raise GitError("Reverting merge commits is not supported")
        if not (await self._git("merge-base", "--is-ancestor", sha, "HEAD", check=False)).ok:
            raise GitError("That commit is not part of the current branch history")
        show = await self._git("show", "--no-color", "--no-ext-diff", "--no-textconv",
                               "--stat", "--format=%h %an %aI%n%s", sha)
        return Prepared(tool="git_revert", args={"commit": sha},
                        summary=f"git_revert: undo commit {sha[:8]} with a new commit",
                        preview=f"Create a NEW commit that undoes {sha[:8]}:\n\n{show.stdout.strip()}",
                        fingerprint=await self.fingerprint(extra=sha))

    async def prepare_restore(self, paths: Sequence[str]) -> Prepared:
        if not paths or len(paths) > 100:
            raise ValueError("Provide between 1 and 100 paths")
        rels = [to_repo_relative(self.root, p) for p in paths]
        from core import safety
        for rel in rels:
            safety.assert_not_protected(rel)
        if self.block_ignored:
            for rel in rels:
                if rel != "." and await self._is_ignored(rel):
                    raise PermissionError(f"'{rel}' is ignored by .gitignore and BLOCK_WRITES_TO_IGNORED=true")
        stat = await self._git("diff", "HEAD", "--stat", "--no-color", "--no-ext-diff", "--", *rels)
        if not stat.stdout.strip():
            raise GitError("No uncommitted changes to restore in those paths")
        full = await self._git("diff", "HEAD", "--no-color", "--no-ext-diff", "--no-textconv", "--", *rels)
        digest = hashlib.sha256(full.stdout.encode()).hexdigest()
        preview = ("PERMANENTLY DISCARDS uncommitted changes (staged and unstaged) in these paths "
                   "and resets them to HEAD. A recovery point is saved first. "
                   "Untracked files are not touched.\n\n" + stat.stdout.strip())
        return Prepared(tool="git_restore", args={"paths": rels},
                        summary=f"git_restore: discard uncommitted changes in {len(rels)} path(s)",
                        preview=preview, fingerprint=await self.fingerprint(extra=digest + "|".join(rels)))

    async def prepare_commit(self, message: str, paths: Optional[Sequence[str]] = None) -> Prepared:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Commit message must be a non-empty string")
        message = message.strip()
        from core import safety

        rels: Optional[List[str]] = None
        if paths is not None:
            if not paths:
                raise ValueError("Paths list cannot be empty when provided")
            if len(paths) > 200:
                raise ValueError("Too many paths (max 200)")
            rels = [to_repo_relative(self.root, p) for p in paths]
            for rel in rels:
                safety.assert_not_protected(rel)
                if self.block_ignored and rel != "." and await self._is_ignored(rel):
                    raise PermissionError(f"'{rel}' is ignored by .gitignore and BLOCK_WRITES_TO_IGNORED=true")

        st = await self.status()
        if st.is_clean:
            raise GitError("Working tree is completely clean. Nothing to commit.")

        if rels:
            stat_res = await self._git("diff", "HEAD", "--stat", "--no-color", "--no-ext-diff", "--", *rels)
            diff_text = stat_res.stdout.strip()
            untracked = [e.path for e in st.entries if e.kind == "untracked" and (e.path in rels or any(e.path.startswith(r.rstrip("/") + "/") for r in rels))]
            if not diff_text and not untracked:
                raise GitError(f"No changes to commit in the specified paths: {rels}")
            affected_summary = f"{len(rels)} specified path(s)"
        else:
            valid_entries = [e for e in st.entries if not safety.is_protected(e.path) and e.kind != "ignored"]
            if not valid_entries:
                raise GitError("No valid changes to commit (all changes are protected or ignored)")
            stat_res = await self._git("diff", "HEAD", "--stat", "--no-color", "--no-ext-diff")
            diff_text = stat_res.stdout.strip()
            untracked = [e.path for e in valid_entries if e.kind == "untracked"]
            affected_summary = f"{len(valid_entries)} file(s)"

        branch = await self.current_branch() or "detached HEAD"
        first_line = message.splitlines()[0]
        preview_parts = [
            f"Target branch: {branch}",
            f"Commit message: {first_line}",
            f"Files to commit ({affected_summary}):\n{diff_text or '(new untracked files only)'}",
        ]
        if untracked:
            preview_parts.append(f"Untracked files to stage and commit ({len(untracked)}):\n" + "\n".join(f"  + {u}" for u in untracked[:20]))
            if len(untracked) > 20:
                preview_parts.append(f"  ... and {len(untracked) - 20} more untracked files")

        preview_parts.append("HUMAN-IN-THE-LOOP INTEGRITY: Creates a permanent commit in repository history under your Git author identity.")
        preview = "\n\n".join(preview_parts)

        fingerprint = await self.fingerprint(extra=f"commit:{first_line}:{','.join(rels) if rels else 'all'}")
        return Prepared(
            tool="git_commit",
            args={"message": message, "paths": rels},
            summary=f"git_commit: '{first_line}' ({affected_summary})",
            preview=preview,
            fingerprint=fingerprint
        )

    async def prepare_push(self, remote: str = "origin", branch: Optional[str] = None, set_upstream: bool = False) -> Prepared:
        remote = validate_ref_name(remote, "remote")
        target_branch = branch or await self.current_branch()
        if not target_branch:
            raise GitError("Cannot push in a detached HEAD state. Switch to a branch first.")
        target_branch = validate_ref_name(target_branch, "branch")

        remotes_res = await self._git("remote", check=False)
        existing_remotes = [r.strip() for r in remotes_res.stdout.splitlines() if r.strip()]
        if remote not in existing_remotes:
            raise GitError(f"Remote '{remote}' not found. Configured remotes: {existing_remotes or 'None'}")

        remote_branch_ref = f"{remote}/{target_branch}"
        has_remote_branch = (await self._git("rev-parse", "--verify", "--quiet", remote_branch_ref, check=False)).ok
        if has_remote_branch:
            log_res = await self._git("log", "--oneline", "--no-color", "-n", "30", f"{remote_branch_ref}..HEAD", check=False)
            outgoing_commits = log_res.stdout.strip() if log_res.ok else ""
        else:
            log_res = await self._git("log", "--oneline", "--no-color", "-n", "30", "HEAD", check=False)
            outgoing_commits = log_res.stdout.strip() if log_res.ok else ""

        count = len(outgoing_commits.splitlines()) if outgoing_commits else 0
        preview_lines = [
            f"Remote repository: {remote}",
            f"Target branch: {target_branch}",
            f"Set upstream (-u): {set_upstream}",
            f"Outgoing commits to push ({count}):\n{outgoing_commits or '(branch is up to date or initial push)'}",
            "REMOTE PUSH: Publishes commits to the remote repository (e.g. GitHub). Requires approved authorization."
        ]
        preview = "\n\n".join(preview_lines)

        fingerprint = await self.fingerprint(extra=f"push:{remote}:{target_branch}")
        return Prepared(
            tool="git_push",
            args={"remote": remote, "branch": target_branch, "set_upstream": set_upstream},
            summary=f"git_push: push '{target_branch}' to '{remote}' ({count} commit(s))",
            preview=preview,
            fingerprint=fingerprint
        )

    # ------------------------------------------------------------------ DANGEROUS: execute
    async def execute(self, tool: str, args: Dict[str, Any]) -> OperationResult:
        handlers = {
            "git_merge": self._exec_merge,
            "git_revert": self._exec_revert,
            "git_restore": self._exec_restore,
            "git_commit": self._exec_commit,
            "git_push": self._exec_push,
        }
        handler = handlers.get(tool)
        if handler is None:
            raise GitError(f"Unknown action: {tool}")
        async with self._lock():
            return await handler(args)

    async def _exec_merge(self, args: Dict[str, Any]) -> OperationResult:
        branch = args["branch"]
        sha = await self.resolve_branch(branch)
        await self._require_clean_tracked()
        before = await self.head_sha()
        backup = await self._backup_ref("pre-merge")
        ident = await self._identity_args()
        res = await self._git(*ident, "merge", "--no-ff", "--no-edit",
                              "-m", f"Merge branch '{branch}' (via CodeScope)", sha, check=False)
        if not res.ok:
            await self._git("merge", "--abort", check=False)     # leave the repository clean
            raise GitError("Merge failed (most likely conflicts) and was aborted. "
                           "The repository is unchanged. " + str(self._fail(["merge"], res)))
        return OperationResult(message=f"Merged '{branch}'", head_before=before,
                               head_after=await self.head_sha(), backup_ref=backup)

    async def _exec_revert(self, args: Dict[str, Any]) -> OperationResult:
        sha = await self.resolve_commit(args["commit"])
        await self._require_clean_tracked()
        before = await self.head_sha()
        backup = await self._backup_ref("pre-revert")
        ident = await self._identity_args()
        res = await self._git(*ident, "revert", "--no-edit", sha, check=False)
        if not res.ok:
            await self._git("revert", "--abort", check=False)
            raise GitError("Revert failed (most likely conflicts) and was aborted. "
                           "The repository is unchanged. " + str(self._fail(["revert"], res)))
        return OperationResult(message=f"Reverted {sha[:8]}", head_before=before,
                               head_after=await self.head_sha(), backup_ref=backup)

    async def _exec_restore(self, args: Dict[str, Any]) -> OperationResult:
        rels = [to_repo_relative(self.root, p) for p in args["paths"]]
        before = await self.head_sha()
        backup = await self._backup_ref("pre-restore", include_worktree=True)
        await self._git("restore", "--source=HEAD", "--staged", "--worktree", "--", *rels)
        return OperationResult(message=f"Restored {len(rels)} path(s) to HEAD", head_before=before,
                               head_after=before, backup_ref=backup)

    async def _exec_commit(self, args: Dict[str, Any]) -> OperationResult:
        message = args["message"]
        rels = args.get("paths")
        from core import safety

        before = await self.head_sha()
        backup = await self._backup_ref("pre-commit")

        if rels:
            for rel in rels:
                safety.assert_not_protected(rel)
            await self._git("add", "--", *rels)
        else:
            st = await self.status()
            valid_paths = [e.path for e in st.entries if not safety.is_protected(e.path) and e.kind != "ignored"]
            if not valid_paths:
                raise GitError("No valid files to commit (all modified files are protected or ignored)")
            await self._git("add", "--", *valid_paths)

        ident = await self._identity_args()
        res = await self._git(*ident, "commit", "-m", message, check=False)
        if not res.ok:
            raise GitError("Commit failed: " + str(self._fail(["commit"], res)))

        after = await self.head_sha()
        return OperationResult(
            message=f"Committed {after[:8] if after else ''}: {message.splitlines()[0]}",
            head_before=before,
            head_after=after,
            backup_ref=backup
        )

    async def _exec_push(self, args: Dict[str, Any]) -> OperationResult:
        remote = args["remote"]
        branch = args["branch"]
        set_upstream = args.get("set_upstream", False)

        cmd = ["push"]
        if set_upstream:
            cmd.append("-u")
        cmd.extend([remote, branch])

        before = await self.head_sha()
        res = await self._git(*cmd, timeout=max(self.timeout, 120), check=False)
        if not res.ok:
            raise GitError("Push failed: " + str(self._fail(["push"], res)))

        return OperationResult(
            message=f"Pushed branch '{branch}' to remote '{remote}'",
            head_before=before,
            head_after=before,
            backup_ref=None
        )
