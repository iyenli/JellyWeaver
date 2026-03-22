"""LLM parse + hardlink operations."""

import asyncio
import uuid
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state, get_llm
from jelly_weaver.api.ws import manager
from jelly_weaver.core.models import EntryRecord, EntryStatus
from jelly_weaver.core.hardlink import link_movie, link_tv_show, link_with_plan, unlink_target
from jelly_weaver.core.scanner import list_entry_tree

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ops", tags=["operations"])


class ParseBody(BaseModel):
    name: str
    hint: str | None = None


class LinkBody(BaseModel):
    source_path: str
    section_id: str
    media_type: str  # "movie" or "tv"
    title_en: str
    title_zh: str = ""
    year: int
    link_plan: list[dict] | None = None


class UnlinkBody(BaseModel):
    target_folder_path: str


class AnalyzeBody(BaseModel):
    source_path: str
    folder_name: str


@router.post("/parse")
async def parse_folder(body: ParseBody):
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")
    result = await asyncio.to_thread(client.parse_folder_name, body.name, body.hint)
    if result is None:
        raise HTTPException(502, "LLM parsing failed after retries")
    return {
        "media_type": result.media_type.value,
        "title_en": result.title_en,
        "title_zh": result.title_zh,
        "year": result.year,
    }


@router.post("/link")
async def start_link(body: LinkBody):
    st = get_state()
    section = st.get_target_section(body.section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {body.section_id}")
    if not section.path:
        raise HTTPException(400, "Target section has no path configured")

    src = Path(body.source_path)
    if not src.is_dir():
        raise HTTPException(400, f"Source not found: {body.source_path}")

    folder_name = f"{body.title_en} ({body.year})"
    task_id = uuid.uuid4().hex[:8]

    if body.link_plan:
        from functools import partial
        is_collection = any(item.get("title_en") for item in body.link_plan)
        dst = Path(section.path)
        link_func = partial(
            link_with_plan,
            plan_items=body.link_plan,
            title_en=body.title_en,
            year=body.year,
        )
        target_display = str(dst) if is_collection else str(dst / folder_name)
    else:
        dst = Path(section.path) / folder_name
        link_func = link_tv_show if body.media_type == "tv" else link_movie
        target_display = str(dst)

    # Run hardlink in background
    asyncio.create_task(_run_link(task_id, link_func, src, dst, body.source_path, st, target_display))
    return {"task_id": task_id, "target_path": target_display}


@router.post("/analyze")
async def analyze_structure(body: AnalyzeBody):
    """Analyze source directory structure and return a link plan."""
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")

    src = Path(body.source_path)
    if not src.is_dir():
        raise HTTPException(400, f"Source not found: {body.source_path}")

    tree = list_entry_tree(body.source_path)
    result = await asyncio.to_thread(client.analyze_structure, body.folder_name, tree)
    if result is None:
        raise HTTPException(502, "Structure analysis failed after retries")

    # Merge actual file counts from tree into the plan
    subdir_counts = {d["name"]: d["file_count"] for d in tree.get("subdirs", [])}
    items = []
    for item in result.items:
        items.append({
            "source_subdir": item.source_subdir,
            "target_subdir": item.target_subdir,
            "title_en": item.title_en,
            "year": item.year,
            "file_count": subdir_counts.get(item.source_subdir, len(tree.get("root_files", []))),
        })

    return {
        "structure_type": result.structure_type.value,
        "items": items,
    }


async def _run_link(task_id, link_func, src, dst, source_key, st, target_display=None):
    loop = asyncio.get_running_loop()
    try:
        def progress_cb(current, total):
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "link_progress",
                    "task_id": task_id,
                    "current": current,
                    "total": total,
                }),
                loop,
            )

        result = await asyncio.to_thread(link_func, src, dst, progress_cb)

        # Update state
        st.upsert_entry(source_key, EntryRecord(
            status=EntryStatus.LINKED,
            target_path=target_display or str(dst),
            linked_at=datetime.now().isoformat(),
            file_count=result.linked + result.skipped,
        ))

        await manager.broadcast({
            "type": "link_done",
            "task_id": task_id,
            "result": {
                "linked": result.linked,
                "skipped": result.skipped,
                "errors": result.errors,
            },
        })
        await manager.broadcast({"type": "state_changed", "scope": "entries"})
    except Exception as e:
        logger.error("Link task %s failed: %s", task_id, e)
        await manager.broadcast({
            "type": "link_error",
            "task_id": task_id,
            "error": str(e),
        })


@router.post("/unlink")
async def unlink_folder(body: UnlinkBody):
    """Remove a hardlinked target folder and reset the source entry to pending."""
    target_path = Path(body.target_folder_path)
    if not target_path.is_dir():
        raise HTTPException(404, f"Target folder not found: {body.target_folder_path}")

    # Find the source entry that produced this target folder
    st = get_state()
    source_key = None
    for key, rec in st.state.entries.items():
        if rec.target_path and Path(rec.target_path) == target_path:
            source_key = key
            break

    # Remove the hardlinked folder from disk
    removed = await asyncio.to_thread(unlink_target, target_path)

    # Reset source entry to pending
    if source_key:
        st.upsert_entry(source_key, EntryRecord(status=EntryStatus.PENDING))

    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    await manager.broadcast({"type": "state_changed", "scope": "targets"})
    return {"ok": True, "removed_files": removed, "source_key": source_key}
