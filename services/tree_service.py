from pathlib import Path
from typing import Optional
from core.path_security import resolve_and_verify
from core.ignore_manager import IgnoreManager
from core.token_estimator import estimate_file_tokens
from models.schemas import TreeNode, ListDirectoryOutput


def build_tree(
    project_path: str,
    max_depth: Optional[int] = None,
    include_hidden: bool = False
) -> ListDirectoryOutput:
    root_path = resolve_and_verify(project_path, "")
    ignore_mgr = IgnoreManager.get_for_project(root_path)

    total_files = 0
    total_dirs = 0

    def traverse(current_path: Path, current_depth: int) -> TreeNode:
        nonlocal total_files, total_dirs

        rel_path_str = str(current_path.relative_to(root_path)).replace("\\", "/")
        if rel_path_str == ".":
            rel_path_str = ""

        node = TreeNode(
            name=current_path.name if rel_path_str != "" else root_path.name,
            path=rel_path_str,
            type="directory",
            children=[]
        )
        total_dirs += 1

        if max_depth is not None and current_depth >= max_depth:
            return node

        try:
            entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return node

        for entry in entries:
            name = entry.name
            if not include_hidden and name.startswith("."):
                continue

            entry_rel_str = str(entry.relative_to(root_path)).replace("\\", "/")

            if entry.is_dir():
                if ignore_mgr.is_ignored(entry_rel_str, is_dir=True):
                    continue
                child_node = traverse(entry, current_depth + 1)
                node.children.append(child_node)
            elif entry.is_file():
                if ignore_mgr.is_ignored(entry_rel_str, is_dir=False):
                    continue
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0

                tokens = estimate_file_tokens(entry, size)
                file_node = TreeNode(
                    name=name,
                    path=entry_rel_str,
                    type="file",
                    size_bytes=size,
                    token_estimate=tokens
                )
                node.children.append(file_node)
                total_files += 1

        return node

    tree_root = traverse(root_path, 0)
    return ListDirectoryOutput(
        project_path=str(root_path),
        tree=tree_root,
        total_files=total_files,
        total_directories=total_dirs
    )
