import pytest
from core.safety import (
    ProtectedPathError,
    Risk,
    TOOL_RISK,
    assert_not_protected,
    is_protected,
    tool_enabled,
)


def test_tool_risk_tiers():
    expected_tools = {
        "git_status": Risk.READ,
        "git_diff": Risk.READ,
        "git_log": Risk.READ,
        "git_show": Risk.READ,
        "git_branch_list": Risk.READ,
        "git_branch_create": Risk.LOW_WRITE,
        "git_switch": Risk.LOW_WRITE,
        "git_merge": Risk.DANGEROUS,
        "git_revert": Risk.DANGEROUS,
        "git_restore": Risk.DANGEROUS,
        "confirm_action": Risk.DANGEROUS,
        "list_checks": Risk.READ,
        "run_check": Risk.EXECUTE,
        "run_all_checks": Risk.EXECUTE,
    }
    for tool, risk in expected_tools.items():
        assert tool in TOOL_RISK
        assert TOOL_RISK[tool] == risk


def test_tool_enabled_rules():
    # Git disabled
    assert not tool_enabled("git_status", enable_git=False, enable_write=True, enable_verify=True)
    assert not tool_enabled("git_merge", enable_git=False, enable_write=True, enable_verify=True)

    # Git enabled, write disabled
    assert tool_enabled("git_status", enable_git=True, enable_write=False, enable_verify=False)
    assert not tool_enabled("git_branch_create", enable_git=True, enable_write=False, enable_verify=False)
    assert not tool_enabled("git_merge", enable_git=True, enable_write=False, enable_verify=False)

    # Git enabled, write enabled
    assert tool_enabled("git_branch_create", enable_git=True, enable_write=True, enable_verify=False)
    assert tool_enabled("git_merge", enable_git=True, enable_write=True, enable_verify=False)

    # Verification tools
    assert not tool_enabled("run_check", enable_git=True, enable_write=True, enable_verify=False)
    assert tool_enabled("run_check", enable_git=False, enable_write=False, enable_verify=True)
    assert tool_enabled("list_checks", enable_git=False, enable_write=False, enable_verify=True)


def test_is_protected():
    # Protected paths
    assert is_protected(".git")
    assert is_protected(".git/config")
    assert is_protected(".git/HEAD")
    assert is_protected("sub/.git/config")
    assert is_protected(".codescope.toml")
    assert is_protected("sub/.codescope.toml")
    assert is_protected(".env")
    assert is_protected(".ENV")
    assert is_protected(".env.local")
    assert is_protected(".env.production")
    assert is_protected("sub/.env")

    # Not protected
    assert not is_protected(".env.example")
    assert not is_protected(".env.sample")
    assert not is_protected(".env.template")
    assert not is_protected("src/main.py")
    assert not is_protected("README.md")
    assert not is_protected("package.json")


def test_assert_not_protected():
    with pytest.raises(ProtectedPathError):
        assert_not_protected(".git/config")

    with pytest.raises(ProtectedPathError):
        assert_not_protected(".codescope.toml")

    with pytest.raises(ProtectedPathError):
        assert_not_protected(".env")

    # Should not raise
    assert_not_protected(".env.example")
    assert_not_protected("src/index.ts")
