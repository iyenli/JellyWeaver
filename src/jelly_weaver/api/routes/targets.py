"""Target section routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state
from jelly_weaver.api.ws import manager
from jelly_weaver.core.models import TargetSection

router = APIRouter(prefix="/api/targets", tags=["targets"])


class CreateTargetBody(BaseModel):
    name: str = ""
    media_type: str = "movies"
    path: str = ""


class UpdateTargetBody(BaseModel):
    name: str | None = None
    media_type: str | None = None
    path: str | None = None


@router.get("")
def list_targets():
    st = get_state()
    sections = [
        {"id": s.id, "name": s.name, "media_type": s.media_type, "path": s.path}
        for s in st.state.target_sections
    ]
    return {"sections": sections}


@router.post("", status_code=201)
async def add_target(body: CreateTargetBody):
    st = get_state()
    section = TargetSection(name=body.name, media_type=body.media_type, path=body.path)
    try:
        st.add_target_section(section)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await manager.broadcast({"type": "state_changed", "scope": "targets"})
    return {"id": section.id, "name": section.name, "media_type": section.media_type, "path": section.path}


@router.patch("/{section_id}")
async def update_target(section_id: str, body: UpdateTargetBody):
    st = get_state()
    section = st.get_target_section(section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {section_id}")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        st.update_target_section(section_id, **updates)
        await manager.broadcast({"type": "state_changed", "scope": "targets"})
    section = st.get_target_section(section_id)
    return {"id": section.id, "name": section.name, "media_type": section.media_type, "path": section.path}


@router.delete("/{section_id}")
async def delete_target(section_id: str):
    st = get_state()
    if st.get_target_section(section_id) is None:
        raise HTTPException(404, f"Section not found: {section_id}")
    st.remove_target_section(section_id)
    await manager.broadcast({"type": "state_changed", "scope": "targets"})
    return {"ok": True}


@router.get("/{section_id}/contents")
def list_target_contents(section_id: str):
    from pathlib import Path
    st = get_state()
    section = st.get_target_section(section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {section_id}")
    if not section.path or not Path(section.path).is_dir():
        return {"items": []}
    items = []
    for child in sorted(Path(section.path).iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            items.append({"name": child.name, "path": str(child)})
    return {"items": items}
