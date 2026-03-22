"""Entry record routes."""

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state
from jelly_weaver.api.ws import manager
from jelly_weaver.core.models import EntryStatus

router = APIRouter(prefix="/api/entries", tags=["entries"])


class PatchEntryBody(BaseModel):
    status: str  # "ignored" or "pending"


@router.patch("/{path:path}")
async def update_entry(path: str, body: PatchEntryBody):
    st = get_state()
    key = path
    if not path.startswith("/") and not re.match(r"^[A-Za-z]:[\\/]", path):
        key = "/" + path
    rec = st.state.entries.get(key)
    if rec is None:
        from jelly_weaver.core.models import EntryRecord
        rec = EntryRecord()
    try:
        rec.status = EntryStatus(body.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {body.status}")
    st.upsert_entry(key, rec)
    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    return {"ok": True, "path": key, "status": rec.status.value}
