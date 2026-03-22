"""Source directory routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state
from jelly_weaver.api.ws import manager
from jelly_weaver.core.scanner import scan_source

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
    from pathlib import Path
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
    result = []
    for item in scanned:
        key = item["path"]
        rec = st.state.entries.get(key)
        status = rec.status.value if rec else "pending"
        result.append({**item, "status": status})
    return {"entries": result}
