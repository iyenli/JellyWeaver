"""Directory scanning and state diffing."""

from pathlib import Path

from .models import EntryRecord, EntryStatus, AppState
from .media_parser import is_media_file


def scan_source(path: str) -> list[dict]:
    """List first-level subdirectories with media file counts.

    Returns list of {"path": str, "name": str, "file_count": int}.
    """
    root = Path(path)
    if not root.is_dir():
        return []

    results = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        count = sum(
            1 for f in child.rglob("*")
            if f.is_file() and is_media_file(f)
        )
        results.append({
            "path": str(child),
            "name": child.name,
            "file_count": count,
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
