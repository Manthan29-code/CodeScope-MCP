import asyncio
import shutil
import subprocess
import pytest
from pathlib import Path

from services.git_service import GitError, GitService, parse_status_v2


def test_parse_status_v2():
    # porcelain v2 with branch info, changed, renamed, unmerged, untracked, ignored
    raw = (
        "# branch.oid 1234567890abcdef1234567890abcdef12345678\0"
        "# branch.head main\0"
        "# branch.upstream origin/main\0"
        "# branch.ab +1 -2\0"
        "1 M. N... 100644 100644 100644 1234567 1234567 modified.txt\0"
        "2 R. N... 100644 100644 100644 1234567 1234567 R100 new_name.txt\0old_name.txt\0"
        "u UU N... 100644 100644 100644 100644 1234567 1234567 1234567 conflict.txt\0"
        "? untracked.txt\0"
        "! ignored.log\0"
    )
    status = parse_status_v2(raw)
    assert status.branch == "main"
    assert status.head_sha == "1234567890abcdef1234567890abcdef12345678"
    assert status.upstream == "origin/main"
    assert status.ahead == 1
    assert status.behind == 2
    assert not status.is_clean
    assert status.has_tracked_changes is True

    kinds = {e.kind: e for e in status.entries}
    assert "changed" in kinds
    assert kinds["changed"].path == "modified.txt"
    assert kinds["changed"].index_status == "M"

    assert "renamed" in kinds
    assert kinds["renamed"].path == "new_name.txt"
    assert kinds["renamed"].orig_path == "old_name.txt"

    assert "unmerged" in kinds
    assert kinds["unmerged"].path == "conflict.txt"

    assert "untracked" in kinds
    assert kinds["untracked"].path == "untracked.txt"

    assert "ignored" in kinds
    assert kinds["ignored"].path == "ignored.log"


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not installed")

    def run(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    run("config", "user.name", "tester")
    run("config", "user.email", "tester@example.com")
    run("config", "commit.gpgsign", "false")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "init")
    return tmp_path


def test_status_clean(repo):
    svc = GitService(repo)
    status = asyncio.run(svc.status())
    assert status.is_clean
    assert status.head_sha is not None
    assert not status.has_tracked_changes


def test_diff_and_log_and_show(repo):
    svc = GitService(repo)
    (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")

    diff = asyncio.run(svc.diff())
    assert "+two" in diff.diff
    assert not diff.truncated

    log = asyncio.run(svc.log(limit=5))
    assert len(log) >= 1
    assert log[0].subject == "init"

    show = asyncio.run(svc.show("HEAD"))
    assert "init" in show.diff


def test_branches_and_create_and_switch(repo):
    svc = GitService(repo)
    branches = asyncio.run(svc.branches())
    assert len(branches) == 1
    default_branch = branches[0].name

    # Create new branch
    res = asyncio.run(svc.create_branch("feature-1"))
    assert "Created branch 'feature-1'" in res.message

    # Duplicate branch creation raises GitError
    with pytest.raises(GitError, match="already exists"):
        asyncio.run(svc.create_branch("feature-1"))

    # Switch branch
    res = asyncio.run(svc.switch("feature-1"))
    assert "Switched to 'feature-1'" in res.message
    curr = asyncio.run(svc.current_branch())
    assert curr == "feature-1"

    # Switch refuses when tracked files have uncommitted changes
    (repo / "a.txt").write_text("dirty tracked\n", encoding="utf-8")
    with pytest.raises(GitError, match="uncommitted changes"):
        asyncio.run(svc.switch(default_branch))


def test_merge_flow_and_conflict_abort(repo):
    svc = GitService(repo)
    branches = asyncio.run(svc.branches())
    default_branch = branches[0].name

    # Create branch feature-add
    asyncio.run(svc.create_branch("feature-add", checkout=True))
    (repo / "b.txt").write_text("b content\n", encoding="utf-8")
    subprocess.run(["git", "add", "b.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "add b"], cwd=repo, check=True)

    # Switch back to default branch
    asyncio.run(svc.switch(default_branch))

    # Prepare merge
    prepared = asyncio.run(svc.prepare_merge("feature-add"))
    assert prepared.tool == "git_merge"
    assert "Merge 'feature-add'" in prepared.preview

    # Execute merge
    res = asyncio.run(svc.execute("git_merge", {"branch": "feature-add"}))
    assert "Merged 'feature-add'" in res.message
    assert (repo / "b.txt").exists()

    # Now create a conflict
    asyncio.run(svc.create_branch("conflict-branch", checkout=True))
    (repo / "b.txt").write_text("conflict on branch\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "conflict commit 1"], cwd=repo, check=True)

    asyncio.run(svc.switch(default_branch))
    (repo / "b.txt").write_text("conflict on main\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "conflict commit 2"], cwd=repo, check=True)

    # Merge conflict should fail and abort automatically, leaving repo clean
    with pytest.raises(GitError, match="Merge failed"):
        asyncio.run(svc.execute("git_merge", {"branch": "conflict-branch"}))

    status = asyncio.run(svc.status())
    assert status.is_clean


def test_revert_flow(repo):
    svc = GitService(repo)
    (repo / "c.txt").write_text("c content\n", encoding="utf-8")
    subprocess.run(["git", "add", "c.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "add c"], cwd=repo, check=True)
    commit_sha = asyncio.run(svc.head_sha())

    # Prepare revert
    prepared = asyncio.run(svc.prepare_revert(commit_sha))
    assert prepared.tool == "git_revert"
    assert commit_sha[:8] in prepared.summary

    # Execute revert
    res = asyncio.run(svc.execute("git_revert", {"commit": commit_sha}))
    assert f"Reverted {commit_sha[:8]}" in res.message
    assert not (repo / "c.txt").exists()


def test_restore_flow_and_ignored(repo):
    svc = GitService(repo, block_ignored=True)
    (repo / "a.txt").write_text("modified uncommitted\n", encoding="utf-8")

    # Prepare restore
    prepared = asyncio.run(svc.prepare_restore(["a.txt"]))
    assert prepared.tool == "git_restore"
    assert "DISCARDS" in prepared.preview

    # Execute restore
    res = asyncio.run(svc.execute("git_restore", {"paths": ["a.txt"]}))
    assert "Restored 1 path(s)" in res.message
    assert (repo / "a.txt").read_text(encoding="utf-8") == "one\n"
    assert res.backup_ref is not None

    # Test restore of ignored path is refused
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("ignored content\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="is ignored"):
        asyncio.run(svc.prepare_restore(["ignored.txt"]))


def test_commit_flow(repo):
    svc = GitService(repo)
    (repo / "a.txt").write_text("modified a\n", encoding="utf-8")
    (repo / "new.txt").write_text("new content\n", encoding="utf-8")

    # Empty message should fail
    with pytest.raises(ValueError, match="Commit message"):
        asyncio.run(svc.prepare_commit(""))

    # Prepare commit
    prepared = asyncio.run(svc.prepare_commit("feat: update a and add new file"))
    assert prepared.tool == "git_commit"
    assert "update a" in prepared.summary
    assert "HUMAN-IN-THE-LOOP" in prepared.preview

    # Execute commit
    res = asyncio.run(svc.execute("git_commit", prepared.args))
    assert "Committed" in res.message

    status = asyncio.run(svc.status())
    assert status.is_clean


def test_commit_protected_path_refused(repo):
    svc = GitService(repo)
    (repo / ".env").write_text("SECRET=123\n", encoding="utf-8")
    from core.safety import ProtectedPathError
    with pytest.raises(ProtectedPathError):
        asyncio.run(svc.prepare_commit("commit secret", paths=[".env"]))


def test_push_flow(repo, tmp_path):
    svc = GitService(repo)
    remote_bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote_bare)], cwd=repo, check=True)

    branch = asyncio.run(svc.current_branch())

    # Prepare push
    prepared = asyncio.run(svc.prepare_push("origin", branch=branch, set_upstream=True))
    assert prepared.tool == "git_push"
    assert "origin" in prepared.summary
    assert "REMOTE PUSH" in prepared.preview

    # Execute push
    res = asyncio.run(svc.execute("git_push", prepared.args))
    assert "Pushed branch" in res.message

    # Verify remote received commits
    clone_dir = tmp_path / "clone_verify"
    subprocess.run(["git", "clone", str(remote_bare), str(clone_dir)], check=True)
    assert (clone_dir / "a.txt").exists()

