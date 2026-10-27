import asyncio
import shutil
import subprocess
import pytest
from pathlib import Path
from fastmcp import FastMCP

import config
from services.confirmation_service import ConfirmationService, ApprovalGate
from services.git_service import GitService
from services.verification_service import VerificationService
from tools.git_tools import register_git_tools
from tools.verify_tools import register_verify_tools


@pytest.fixture
def sandbox_repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not installed")

    repo_dir = tmp_path / "sandbox"
    repo_dir.mkdir(parents=True, exist_ok=True)

    def run(*a):
        subprocess.run(["git", *a], cwd=repo_dir, check=True, capture_output=True)

    run("init", "-q")
    run("config", "user.name", "tester")
    run("config", "user.email", "tester@example.com")
    run("config", "commit.gpgsign", "false")
    (repo_dir / "a.txt").write_text("initial\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "initial commit")
    return repo_dir


async def _get_tool_fn(mcp: FastMCP, name: str):
    tool = await mcp.get_tool(name)
    return tool.fn


def test_git_tools_project_path(sandbox_repo, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(sandbox_repo)])
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(sandbox_repo)])
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)

    mcp = FastMCP("test_mcp")
    default_git = GitService(config.PROJECT_ROOT)
    gate = ApprovalGate(ConfirmationService(ttl_seconds=60), mode="code")
    register_git_tools(mcp, default_git, gate, enable_write_tools=True)

    git_status = asyncio.run(_get_tool_fn(mcp, "git_status"))
    git_diff = asyncio.run(_get_tool_fn(mcp, "git_diff"))

    # 1. Calling git_status on sandbox_repo
    res = asyncio.run(git_status(project_path=str(sandbox_repo)))
    assert res["ok"] is True
    assert res["is_clean"] is True
    assert res["head_sha"] is not None

    # 2. Modify a file in sandbox_repo and check git_diff
    (sandbox_repo / "a.txt").write_text("modified\n", encoding="utf-8")
    status_res = asyncio.run(git_status(project_path=str(sandbox_repo)))
    assert status_res["ok"] is True
    assert status_res["is_clean"] is False

    diff_res = asyncio.run(git_diff(project_path=str(sandbox_repo)))
    assert diff_res["ok"] is True
    assert "modified" in diff_res["diff"]

    # 3. Disallowed project_path returns error
    forbidden_path = str(sandbox_repo.parent / "forbidden")
    Path(forbidden_path).mkdir(parents=True, exist_ok=True)
    err_res = asyncio.run(git_status(project_path=forbidden_path))
    assert err_res["ok"] is False
    assert "READ_ALLOWED_ROOTS" in err_res["error"]

    # 4. Non-existent path returns error
    non_existent = str(sandbox_repo / "does_not_exist")
    err_res2 = asyncio.run(git_status(project_path=non_existent))
    assert err_res2["ok"] is False
    assert "does not exist" in err_res2["error"]


def test_verify_tools_project_path(sandbox_repo, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(sandbox_repo)])

    # Put a .codescope.toml in sandbox
    (sandbox_repo / ".codescope.toml").write_text(
        '[checks.custom]\ncmd = ["echo", "sandbox_hello"]\ndescription = "test check"\ntimeout = 10\n',
        encoding="utf-8"
    )

    mcp = FastMCP("test_mcp")
    default_verifier = VerificationService(config.PROJECT_ROOT)
    register_verify_tools(mcp, default_verifier)

    list_checks = asyncio.run(_get_tool_fn(mcp, "list_checks"))
    run_check = asyncio.run(_get_tool_fn(mcp, "run_check"))

    # List checks in sandbox
    list_res = asyncio.run(list_checks(project_path=str(sandbox_repo)))
    assert list_res["ok"] is True
    names = [c["name"] for c in list_res["checks"]]
    assert "custom" in names

    # Run check in sandbox
    run_res = asyncio.run(run_check(name="custom", project_path=str(sandbox_repo)))
    assert run_res["ok"] is True
    assert run_res["passed"] is True
    assert "sandbox_hello" in run_res["stdout_tail"]


def test_dangerous_tool_remembers_project_path(sandbox_repo, monkeypatch):
    monkeypatch.setattr(config, "READ_ALLOWED_ROOTS", [str(sandbox_repo)])
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(sandbox_repo)])
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)

    mcp = FastMCP("test_mcp")
    default_git = GitService(config.PROJECT_ROOT)
    conf_svc = ConfirmationService(ttl_seconds=60)
    gate = ApprovalGate(conf_svc, mode="code")
    register_git_tools(mcp, default_git, gate, enable_write_tools=True)

    git_restore = asyncio.run(_get_tool_fn(mcp, "git_restore"))
    confirm_action = asyncio.run(_get_tool_fn(mcp, "confirm_action"))

    # Modify file
    (sandbox_repo / "a.txt").write_text("change to restore\n", encoding="utf-8")

    # Request git_restore on sandbox_repo
    prep_res = asyncio.run(git_restore(paths=["a.txt"], ctx=None, project_path=str(sandbox_repo)))
    assert prep_res["ok"] is True
    assert prep_res["status"] == "approval_required"
    action_id = prep_res["action_id"]

    # Peek to verify project_path is recorded
    pending = conf_svc.peek(action_id)
    assert pending.project_path == str(sandbox_repo)

    # Confirm action
    code = pending.code
    conf_res = asyncio.run(confirm_action(action_id=action_id, approval_code=code))
    assert conf_res["ok"] is True

    # File in sandbox is restored
    assert (sandbox_repo / "a.txt").read_text(encoding="utf-8") == "initial\n"
