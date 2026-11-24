import os
import sys
import time
import tempfile
import pytest
from pathlib import Path

# Ensure project root is in sys.path when running script directly via `python tests/test_hotreload.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from core.path_security import verify_read_root, ReadRootNotAllowedError


def test_hotreload_dynamic_allowed_roots(monkeypatch):
    """Verifies that editing .env dynamically updates READ_ALLOWED_ROOTS on the fly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        env_file = tmp_path / ".env"

        # Create two test project directories
        project_a = tmp_path / "project_a"
        project_b = tmp_path / "project_b"
        project_a.mkdir()
        project_b.mkdir()

        # Step 1: Initial .env only allows project_a
        env_file.write_text(f"ALLOWED_PROJECT_ROOTS={project_a}\n", encoding="utf-8")

        monkeypatch.setattr(config, "ENV_PATH", env_file)
        monkeypatch.setattr(config, "_last_env_mtime", -1.0)

        # Trigger reload
        reloaded = config.reload_if_changed()
        assert reloaded is True
        assert str(project_a) in config.READ_ALLOWED_ROOTS

        # project_a should be accepted
        res_a = verify_read_root(str(project_a))
        assert res_a == project_a.resolve()

        # project_b should be rejected
        with pytest.raises(ReadRootNotAllowedError):
            verify_read_root(str(project_b))

        # Step 2: Simulate human editing .env to add project_b in mid-conversation
        time.sleep(0.05)  # Ensure mtime increments
        env_file.write_text(
            f"ALLOWED_PROJECT_ROOTS={project_a};{project_b}\n",
            encoding="utf-8"
        )

        # verify_read_root should automatically hot-reload and now ACCEPT project_b!
        res_b = verify_read_root(str(project_b))
        assert res_b == project_b.resolve()
        assert str(project_b) in config.READ_ALLOWED_ROOTS


def test_env_override_beats_client_env(monkeypatch):
    """Verifies that disk .env with override=True always beats stale client environment variables."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        env_file = tmp_path / ".env"

        # Stale client environment variable
        monkeypatch.setenv("READ_ALLOWED_ROOTS", "C:\\StaleClientPath")
        env_file.write_text("READ_ALLOWED_ROOTS=C:\\FreshDiskPath\n", encoding="utf-8")

        monkeypatch.setattr(config, "ENV_PATH", env_file)
        monkeypatch.setattr(config, "_last_env_mtime", -1.0)

        config.reload_if_changed()
        # Fresh disk path must win!
        assert config.READ_ALLOWED_ROOTS == ["C:\\FreshDiskPath"]


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
