from datetime import datetime, timezone
from core.path_security import resolve_and_verify
from core.file_classifier import is_binary_file, guess_language
from core.token_estimator import estimate_file_tokens
from models.schemas import FileMetadataOutput


def get_metadata(project_path: str, file_path: str) -> FileMetadataOutput:
    target_path = resolve_and_verify(project_path, file_path)

    if not target_path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not target_path.is_file():
        raise ValueError(f"Target path is not a file: {file_path}")

    stat = target_path.stat()
    size_bytes = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    binary = is_binary_file(target_path)
    lang = guess_language(target_path)
    tokens = estimate_file_tokens(target_path, size_bytes)

    rel_path_str = str(target_path.relative_to(resolve_and_verify(project_path, ""))).replace("\\", "/")

    return FileMetadataOutput(
        file_path=rel_path_str,
        size_bytes=size_bytes,
        last_modified=mtime,
        language=lang,
        token_estimate=tokens,
        is_binary=binary
    )
