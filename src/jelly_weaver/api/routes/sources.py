"""Source directory routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state
from jelly_weaver.api.ws import manager
from jelly_weaver.core.scanner import scan_source, build_target_hash_map
from jelly_weaver.core.tree import build_tree

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceBody(BaseModel):
    path: str


@router.get("")
def list_sources():
    st = get_state()
    entries_by_source: dict[str, list] = {}
    for src in st.state.sources:
        entries = []
        for key, rec in st.state.entries.items():
            if key.startswith(src + "/") or key.startswith(src + "\\"):
                entries.append({
                    "path": key,
                    "status": rec.status.value,
                    "target_path": rec.target_path,
                    "linked_at": rec.linked_at,
                    "file_count": rec.file_count,
                })
        entries_by_source[src] = entries
    return {"sources": st.state.sources, "entries": entries_by_source}


@router.post("", status_code=201)
async def add_source(body: SourceBody):
    if not Path(body.path).is_dir():
        raise HTTPException(400, f"Not a directory: {body.path}")
    st = get_state()
    st.add_source(body.path)
    await manager.broadcast({"type": "state_changed", "scope": "sources"})
    return {"ok": True}


@router.delete("")
async def remove_source(body: SourceBody):
    st = get_state()
    st.remove_source(body.path)
    await manager.broadcast({"type": "state_changed", "scope": "sources"})
    return {"ok": True}


@router.get("/scan")
def scan(path: str):
    scanned = scan_source(path)
    st = get_state()

    # Build target child name map for fast exact-name matching (Fallback 1)
    target_names: dict[str, str] = {}
    for section in st.state.target_sections:
        if not section.path:
            continue
        section_dir = Path(section.path)
        if not section_dir.is_dir():
            continue
        for child in section_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                target_names[child.name.lower()] = str(child)

    result = []
    needs_hash_check = []

    for item in scanned:
        key = item["path"]
        rec = st.state.entries.get(key)
        if rec:
            # Primary: state record is the authoritative source
            result.append({**item, "status": rec.status.value, "target_path": rec.target_path})
        else:
            # Fallback 1: exact case-insensitive name match
            matched_path = target_names.get(item["name"].lower())
            if matched_path:
                result.append({**item, "status": "linked", "target_path": matched_path})
            else:
                # Needs Merkle hash check — defer until we know it's required
                needs_hash_check.append(item)

    # Fallback 2: Merkle hash match — only built once when there are unresolved entries.
    # Skipped entirely when all entries are resolved by state records or name matches,
    # which avoids an expensive full tree walk on every scan.
    if needs_hash_check:
        target_hash_map = build_target_hash_map(st.state.target_sections)
        for item in needs_hash_check:
            source_tree = build_tree(Path(item["path"]), depth=0)
            matched_path = target_hash_map.get(source_tree.key)
            result.append({**item, "status": "linked" if matched_path else "pending",
                           "target_path": matched_path})

    return {"entries": result}
