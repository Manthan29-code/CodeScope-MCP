import asyncio
import sys
import pytest
from utils.process_runner import (
    ExecutableNotFound,
    base_env,
    resolve_executable,
    run_command,
    truncate_middle,
)


def test_resolve_executable():
    python_exe = resolve_executable(sys.executable)
    assert python_exe

    with pytest.raises(ExecutableNotFound):
        resolve_executable("non_existent_executable_12345_xyz")


def test_truncate_middle():
    text = "abcdefghij"
    truncated, was_cut = truncate_middle(text, 6)
    assert was_cut is True
    assert "omitted" in truncated
    assert truncated.startswith("abc")
    assert truncated.endswith("hij")

    untruncated, was_cut2 = truncate_middle(text, 20)
    assert was_cut2 is False
    assert untruncated == text


def test_run_command_success(tmp_path):
    res = asyncio.run(
        run_command([sys.executable, "-c", "print('hello from subprocess')"], cwd=tmp_path)
    )
    assert res.ok is True
    assert res.exit_code == 0
    assert not res.timed_out
    assert "hello from subprocess" in res.stdout


def test_run_command_nonzero_exit(tmp_path):
    res = asyncio.run(
        run_command([sys.executable, "-c", "import sys; sys.exit(42)"], cwd=tmp_path)
    )
    assert res.ok is False
    assert res.exit_code == 42
    assert not res.timed_out


def test_run_command_timeout(tmp_path):
    res = asyncio.run(
        run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            cwd=tmp_path,
            timeout=0.5,
        )
    )
    assert res.ok is False
    assert res.timed_out is True


def test_run_command_truncation(tmp_path):
    res = asyncio.run(
        run_command(
            [sys.executable, "-c", "print('x' * 500)"],
            cwd=tmp_path,
            max_output_chars=100,
        )
    )
    assert res.ok is True
    assert res.truncated is True
    assert "characters omitted" in res.stdout
