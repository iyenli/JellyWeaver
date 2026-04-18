"""Directory scanning and state diffing."""

from pathlib import Path

from .models import EntryRecord, EntryStatus, AppState, TargetSection
from .media_parser import is_media_file, is_video_file
from .tree import build_tree, name_hash


def scan_source(path: str) -> list[dict]:
    """List first-level subdirectories and loose media files with counts.

    Returns list of {"path": str, "name": str, "file_count": int, "is_file": bool}.
    """
    root = Path(path)
    if not root.is_dir():
        return []

    results = []
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            count = sum(
                1 for f in child.rglob("*")
                if f.is_file() and is_media_file(f)
            )
            results.append({
                "path": str(child),
                "name": child.name,
                "file_count": count,
                "is_file": False,
            })
        elif child.is_file() and is_video_file(child):
            # Count companion files (subtitles, etc.) that share the same stem
            companions = [
                f for f in root.iterdir()
                if f != child and f.is_file()
                and is_media_file(f) and not is_video_file(f)
                and f.name.startswith(child.stem)
            ]
            results.append({
                "path": str(child),
                "name": child.name,
                "file_count": 1 + len(companions),
                "is_file": True,
            })
    return results


def diff_with_state(
    scanned: list[dict], state: AppState,
) -> list[dict]:
    """Return entries not yet in state or still pending."""
    pending = []
    for item in scanned:
        key = item["path"]
        entry = state.entries.get(key)
        if entry is None or entry.status == EntryStatus.PENDING:
            pending.append(item)
    return pending


def reconcile_entries(
    entries: list[dict],
    state: AppState,
    target_sections: list[TargetSection],
) -> list[dict]:
    """Auto-detect manually-linked entries by matching cached names to target dirs.

    For each PENDING entry whose root key is in name_cache, check if the
    cached name exists as a child directory under any target section.  If
    found, update the entry dict status to 'linked'.  This lets the frontend
    show the correct status without the user having to drag-and-drop again.
    """
    # Build a set of lowercase names present in any target section
    target_names: dict[str, str] = {}  # lowercase name -> full path
    for section in target_sections:
        if not section.path:
            continue
        section_dir = Path(section.path)
        if not section_dir.is_dir():
            continue
        for child in section_dir.iterdir():
            if child.is_dir():
                target_names[child.name.lower()] = str(child)

    result = []
    for item in entries:
        entry_path = item["path"]
        existing = state.entries.get(entry_path)
        if existing and existing.status != EntryStatus.PENDING:
            result.append(item)
            continue

        # Compute root key for this entry
        root_path = Path(entry_path)
        if root_path.is_dir():
            tree = build_tree(root_path, depth=0)
            root_key = tree.key
        else:
            root_key = name_hash(root_path.name)

        cached_name = state.name_cache.get(root_key)
        if cached_name:
            matched_path = target_names.get(cached_name.lower())
            if matched_path:
                item = dict(item)
                item["status"] = "linked"
                item["target_path"] = matched_path
                result.append(item)
                continue

        result.append(item)
    return result


def build_target_hash_map(target_sections: list[TargetSection]) -> dict[str, str]:
    """Compute Merkle hashes for all first-level subdirectories in every target section.

    Returns {merkle_hash: full_path}.  Used to detect source entries whose file
    tree is identical to an existing target directory (e.g. hardlinks created
    outside of Jelly Weaver, or entries linked before state tracking began).
    """
    result: dict[str, str] = {}
    for section in target_sections:
        if not section.path:
            continue
        section_dir = Path(section.path)
        if not section_dir.is_dir():
            continue
        for child in section_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                tree = build_tree(child, depth=0)
                result[tree.key] = str(child)
    return result


def list_entry_tree(entry_path: str, sample_count: int = 3) -> dict:
    """Return a compact directory tree of a source entry for LLM consumption.

    Returns {"root_files": [...], "subdirs": [{"name", "sample_files", "file_count"}, ...]}.
    """
    root = Path(entry_path)
    if not root.is_dir():
        return {"root_files": [], "subdirs": []}

    root_files: list[str] = []
    subdirs: list[dict] = []

    for child in sorted(root.iterdir()):
        if child.is_file() and is_media_file(child):
            if len(root_files) < sample_count:
                root_files.append(child.name)
        elif child.is_dir() and not child.name.startswith("."):
            media_files = sorted(
                f for f in child.rglob("*")
                if f.is_file() and is_media_file(f)
            )
            subdirs.append({
                "name": child.name,
                "sample_files": [f.name for f in media_files[:sample_count]],
                "file_count": len(media_files),
            })

    return {"root_files": root_files, "subdirs": subdirs}
