"""Recursive Merkle-keyed directory tree builder for rename analysis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .media_parser import is_media_file, is_video_file, is_subtitle_file

_SAMPLE_LIMIT = 5
_MAX_DEPTH = 4


def _is_hash_file(path: Path) -> bool:
    """Only video and subtitle files contribute to the Merkle hash.

    Metadata files (.nfo, images, etc.) are excluded because they can be
    added or modified by media managers (e.g. Jellyfin) without changing
    the actual content, which would cause false hash mismatches.
    """
    return is_video_file(path) or is_subtitle_file(path)


def name_hash(name: str) -> str:
    """Hash a file or directory name (identity key — content not read)."""
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def dir_hash(child_keys: list[str]) -> str:
    """Merkle-style hash of sorted child keys.

    Changes when any child name changes, so cache invalidation is automatic.
    """
    combined = "".join(sorted(child_keys))
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


@dataclass
class TreeNode:
    name: str                            # original name on disk
    key: str                             # name_hash (file) or dir_hash (dir)
    is_dir: bool
    depth: int                           # 0 = root entry being analysed
    children: list[TreeNode] = field(default_factory=list)
    sample_files: list[str] = field(default_factory=list)
    file_count: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "key": self.key,
            "is_dir": self.is_dir,
            "depth": self.depth,
            "children": [c.to_dict() for c in self.children],
            "sample_files": self.sample_files,
            "file_count": self.file_count,
        }


def build_tree(path: Path, depth: int = 0, max_depth: int = _MAX_DEPTH) -> TreeNode:
    """Recursively build a TreeNode for *path*.

    Directories collect child TreeNodes and derive their key from children keys
    (Merkle style).  Files use a plain name hash.  Hidden entries are skipped.
    Recursion stops at max_depth — children beyond that depth are represented
    as file-count leaves only.
    """
    if path.is_file():
        return TreeNode(
            name=path.name,
            key=name_hash(path.name),
            is_dir=False,
            depth=depth,
            file_count=1 if _is_hash_file(path) else 0,
        )

    # Directory ---
    children: list[TreeNode] = []
    sample_files: list[str] = []
    total_media: int = 0

    try:
        entries = sorted(path.iterdir())
    except PermissionError:
        entries = []

    for child in entries:
        if child.name.startswith("."):
            continue

        if child.is_file():
            if _is_hash_file(child):
                total_media += 1
                if len(sample_files) < _SAMPLE_LIMIT:
                    sample_files.append(child.name)
        elif child.is_dir():
            if depth < max_depth:
                subtree = build_tree(child, depth + 1, max_depth)
                children.append(subtree)
                total_media += subtree.file_count
                # Collect sample filenames from this child for the current node
                if len(sample_files) < _SAMPLE_LIMIT:
                    remaining = _SAMPLE_LIMIT - len(sample_files)
                    sample_files.extend(subtree.sample_files[:remaining])
            else:
                # Beyond max depth — count files only, no recursion
                count = sum(
                    1 for f in child.rglob("*") if f.is_file() and is_media_file(f)
                )
                stub = TreeNode(
                    name=child.name,
                    key=name_hash(child.name),
                    is_dir=True,
                    depth=depth + 1,
                    file_count=count,
                )
                children.append(stub)
                total_media += count

    # Key: derived from children so it changes if any child changes
    child_keys = [c.key for c in children] + [name_hash(f) for f in sample_files]
    key = dir_hash(child_keys) if child_keys else name_hash(path.name)

    return TreeNode(
        name=path.name,
        key=key,
        is_dir=True,
        depth=depth,
        children=children,
        sample_files=sample_files,
        file_count=total_media,
    )


def build_file_group_tree(files: list[Path]) -> TreeNode:
    """Build a virtual directory TreeNode for a group of loose files.

    The Merkle key is computed identically to a real flat directory containing
    those files, so name_cache lookup works transparently with reconcile.
    """
    sorted_files = sorted(files, key=lambda f: f.name)
    child_keys = [name_hash(f.name) for f in sorted_files]
    key = dir_hash(child_keys) if child_keys else name_hash("empty-group")
    sample = [f.name for f in sorted_files[:_SAMPLE_LIMIT]]
    return TreeNode(
        name="",
        key=key,
        is_dir=True,
        depth=0,
        children=[],
        sample_files=sample,
        file_count=len(sorted_files),
    )



    """Return sibling groups ordered deepest-first (bottom-up BFS).

    Each group is a list of directory siblings sharing the same parent.
    File nodes are excluded — only directories need LLM renaming.
    The root itself is returned as a single-element group last.
    """
    # BFS to collect groups by depth, then reverse
    from collections import deque

    groups_by_depth: dict[int, list[list[TreeNode]]] = {}
    queue: deque[TreeNode] = deque([root])

    while queue:
        node = queue.popleft()
        dir_children = [c for c in node.children if c.is_dir]
        if dir_children:
            depth = dir_children[0].depth
            groups_by_depth.setdefault(depth, []).append(dir_children)
            for child in dir_children:
                queue.append(child)

    # Root as its own group (depth 0)
    root_group = [root]
    groups_by_depth.setdefault(0, []).insert(0, root_group)

    # Sort by depth descending (deepest first), flatten
    result: list[list[TreeNode]] = []
    for depth in sorted(groups_by_depth.keys(), reverse=True):
        for group in groups_by_depth[depth]:
            # Skip root group until the end
            if group is root_group:
                continue
            result.append(group)
    result.append(root_group)
    return result
