import asyncio
import json
import sys
import pytest
from pathlib import Path

from services.verification_service import VerificationError, VerificationService
from tools.verify_tools import attach_verification


def test_config_parsing_and_python_expansion(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        """
[checks.lint]
description = "Ruff lint"
cmd = ["{python}", "-m", "ruff", "check", "."]
timeout = 60

[checks.custom]
cmd = ["echo", "test"]
cwd = "sub"
timeout = 10
""",
        encoding="utf-8",
    )
    (tmp_path / "sub").mkdir()

    svc = VerificationService(tmp_path)
    checks = svc.load_checks()

    assert "lint" in checks
    assert checks["lint"].description == "Ruff lint"
    assert checks["lint"].timeout == 60
    assert "{python}" not in checks["lint"].cmd[0]
    assert sys.executable in checks["lint"].cmd[0] or "python" in checks["lint"].cmd[0]
    assert checks["lint"].source == "config"

    assert "custom" in checks
    assert checks["custom"].cwd == "sub"
    assert checks["custom"].timeout == 10


def test_config_string_cmd_rejected(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        """
[checks.bad]
cmd = "pytest -q"
""",
        encoding="utf-8",
    )

    svc = VerificationService(tmp_path)
    with pytest.raises(VerificationError, match="must be a non-empty list of strings"):
        svc.load_checks()


def test_config_invalid_check_name(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        """
[checks."bad name with spaces!"]
cmd = ["echo", "hi"]
""",
        encoding="utf-8",
    )

    svc = VerificationService(tmp_path)
    with pytest.raises(VerificationError, match="Invalid check name"):
        svc.load_checks()


def test_unknown_check_run_fails(tmp_path):
    svc = VerificationService(tmp_path, autodetect=False)
    with pytest.raises(VerificationError, match="Unknown check 'nonexistent'"):
        asyncio.run(svc.run_check("nonexistent"))


def test_autodetect_pytest(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    svc = VerificationService(tmp_path, autodetect=True)
    checks = svc.load_checks()

    assert "test" in checks
    assert checks["test"].source == "auto"
    assert "pytest" in " ".join(checks["test"].cmd)


def test_autodetect_node(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(
        json.dumps({"scripts": {"test": "jest", "lint": "eslint .", "build": "vite build"}}),
        encoding="utf-8",
    )

    svc = VerificationService(tmp_path, autodetect=True)
    checks = svc.load_checks()

    assert "test" in checks
    assert "npm run test" in checks["test"].description
    assert "lint" in checks
    assert "build" in checks


def test_autodetect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'\n", encoding="utf-8")

    svc = VerificationService(tmp_path, autodetect=True)
    checks = svc.load_checks()

    assert "build" in checks
    assert checks["build"].cmd == ["cargo", "build"]
    assert "lint" in checks
    assert "test" in checks


def test_autodetect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/test\n", encoding="utf-8")

    svc = VerificationService(tmp_path, autodetect=True)
    checks = svc.load_checks()

    assert "build" in checks
    assert checks["build"].cmd == ["go", "build", "./..."]
    assert "lint" in checks
    assert "test" in checks


def test_run_check_success_and_timeout(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        f"""
[checks.fast]
cmd = ["{sys.executable.replace(chr(92), '/')}", "-c", "print('check passed')"]

[checks.slow]
cmd = ["{sys.executable.replace(chr(92), '/')}", "-c", "import time; time.sleep(10)"]
timeout = 1
""",
        encoding="utf-8",
    )

    svc = VerificationService(tmp_path)

    fast_result = asyncio.run(svc.run_check("fast"))
    assert fast_result.passed is True
    assert fast_result.exit_code == 0
    assert "check passed" in fast_result.stdout_tail

    slow_result = asyncio.run(svc.run_check("slow"))
    assert slow_result.passed is False
    assert slow_result.timed_out is True


def test_run_many_and_stop_on_failure(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        f"""
[checks.c1]
cmd = ["{sys.executable.replace(chr(92), '/')}", "-c", "import sys; sys.exit(1)"]

[checks.c2]
cmd = ["{sys.executable.replace(chr(92), '/')}", "-c", "print('c2')"]
""",
        encoding="utf-8",
    )

    svc = VerificationService(tmp_path)

    # Without stop_on_failure
    summary = asyncio.run(svc.run_many(["c1", "c2"], stop_on_failure=False))
    assert summary.passed is False
    assert len(summary.results) == 2

    # With stop_on_failure
    summary2 = asyncio.run(svc.run_many(["c1", "c2"], stop_on_failure=True))
    assert summary2.passed is False
    assert len(summary2.results) == 1
    assert summary2.results[0].name == "c1"


def test_attach_verification(tmp_path):
    config_file = tmp_path / ".codescope.toml"
    config_file.write_text(
        f"""
[checks.quick]
cmd = ["{sys.executable.replace(chr(92), '/')}", "-c", "print('ok')"]
""",
        encoding="utf-8",
    )
    svc = VerificationService(tmp_path)

    res = {"ok": True, "created": True}
    updated = asyncio.run(attach_verification(res, svc, ["quick"]))
    assert "verification" in updated
    assert updated["verification"]["passed"] is True
