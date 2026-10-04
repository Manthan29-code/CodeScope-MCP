from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional
import chardet


@dataclass
class TextFile:
    text: str
    encoding: str
    bom: bool
    newline: str
    trailing_newline: bool
    mixed_newlines: bool
    raw_hash: str


def sha256_bytes(data: bytes) -> str:
    """Returns SHA256 hex digest of the raw bytes."""
    return hashlib.sha256(data).hexdigest()


def read_text_with_style(path: Path) -> TextFile:
    """
    Reads a file preserving style metadata: encoding, BOM, newline style,
    trailing newline, and mixed newline indicators.
    Normalizes text to standard '\\n' in the returned TextFile.text.
    """
    raw_bytes = path.read_bytes()
    raw_hash = sha256_bytes(raw_bytes)

    # Detect UTF-8 BOM
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        bom = True
        encoding = "utf-8"
        content_bytes = raw_bytes[3:]
        decoded_text = content_bytes.decode("utf-8")
    else:
        bom = False
        try:
            decoded_text = raw_bytes.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            detected = chardet.detect(raw_bytes)
            encoding = detected.get("encoding") or "utf-8"
            decoded_text = raw_bytes.decode(encoding, errors="replace")

    # Detect newline style
    crlf_count = decoded_text.count("\r\n")
    stripped_crlf = decoded_text.replace("\r\n", "")
    standalone_lf_count = stripped_crlf.count("\n")
    standalone_cr_count = stripped_crlf.count("\r")

    # Check for mixed newlines
    has_crlf = crlf_count > 0
    has_standalone_lf = standalone_lf_count > 0
    has_standalone_cr = standalone_cr_count > 0

    mixed_count = sum([1 if x else 0 for x in (has_crlf, has_standalone_lf, has_standalone_cr)])
    mixed_newlines = mixed_count > 1

    # Dominant newline
    if crlf_count > standalone_lf_count:
        newline = "\r\n"
    else:
        newline = "\n"

    trailing_newline = (
        decoded_text.endswith("\n") or decoded_text.endswith("\r")
    ) if decoded_text else False

    # Normalize all line endings to \n
    text = decoded_text.replace("\r\n", "\n").replace("\r", "\n")

    return TextFile(
        text=text,
        encoding=encoding,
        bom=bom,
        newline=newline,
        trailing_newline=trailing_newline,
        mixed_newlines=mixed_newlines,
        raw_hash=raw_hash
    )


def encode_text_with_style(text: str, style: TextFile) -> bytes:
    """
    Encodes normalized '\\n' text back to bytes preserving the original file's
    newline style, encoding, and BOM.
    """
    # Convert \n to target newline style
    if style.newline == "\r\n":
        out_text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    else:
        out_text = text.replace("\r\n", "\n")

    encoded = out_text.encode(style.encoding)

    if style.bom and style.encoding.lower().replace("-", "") in ("utf8", "utf8sig"):
        encoded = b"\xef\xbb\xbf" + encoded

    return encoded


def atomic_write_bytes(target: Path, data: bytes) -> None:
    """
    Writes raw bytes to target atomically using a temporary file in the same directory.
    Copies permissions if target exists, then replaces atomically.
    Cleans up temp file on failure.
    """
    parent = target.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path_str = tempfile.mkstemp(dir=parent, prefix=".codescope-", suffix=".tmp")
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if target.exists():
            try:
                shutil.copymode(str(target), str(temp_path))
            except Exception:
                pass

        os.replace(str(temp_path), str(target))
    except Exception:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        raise
