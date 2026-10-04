import hashlib
import os
import pytest
import config
from core import ignore_manager


@pytest.fixture(autouse=True)
def _clear_caches():
    ignore_manager.clear_cache()
    yield
    ignore_manager.clear_cache()


@pytest.fixture
def project(tmp_path):
    """A small realistic project. Returns its root Path."""
    def put(rel, data):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    put("src/app.py", "import util\n\ndef main():\n    return 1\n")
    put("src/util.py", "def helper():\n    return 'old_name'\n")
    put("README.md", "# Demo\nold_name appears here\n")
    put(".gitignore", "dist/\n*.log\n")
    put("node_modules/pkg/index.js", "module.exports = 'old_name'\n")
    put("dist/out.js", "var x = 'old_name'\n")
    put("debug.log", "old_name\n")
    put(".git/config", "[core]\n")
    put(".env", "SECRET=old_name\n")
    put(".env.example", "SECRET=\n")
    put("data.bin", b"\x00\x01\x02binary")
    put("crlf.txt", b"line1\r\nline2\r\nline3\r\n")
    put("mixed.txt", b"line1\r\nline2\nline3\r\n")
    put("bom.txt", b"\xef\xbb\xbfhello\r\nworld\r\n")
    return tmp_path


@pytest.fixture
def write_enabled(monkeypatch, project):
    monkeypatch.setattr(config, "ENABLE_WRITE_TOOLS", True)
    monkeypatch.setattr(config, "WRITE_ALLOWED_ROOTS", [str(project)])
    return project


@pytest.fixture
def tree_snapshot():
    """Call snapshot(root) -> {relative_path: sha256}; compare before/after."""
    def snapshot(root):
        out = {}
        for dirpath, _, files in os.walk(root):
            for name in files:
                p = os.path.join(dirpath, name)
                with open(p, "rb") as f:
                    out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()
        return out
    return snapshot
