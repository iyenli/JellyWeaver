"""LLM parse + hardlink operations."""

import asyncio
import uuid
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state, get_llm
from jelly_weaver.api.ws import manager
from jelly_weaver.core.models import EntryRecord, EntryStatus
from jelly_weaver.core.hardlink import link_movie, link_tv_show, link_with_plan, link_with_tree, unlink_target
from jelly_weaver.core.scanner import list_entry_tree, scan_source
from jelly_weaver.core.tree import build_tree, collect_sibling_groups, TreeNode

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
    tree_plan: dict | None = None  # RenameNode tree with accepted_name fields


class UnlinkBody(BaseModel):
    target_folder_path: str


class AnalyzeBody(BaseModel):
    source_path: str
    folder_name: str


class RenameTreeBody(BaseModel):
    source_path: str


@router.delete("/name-cache")
async def clear_name_cache():
    """Clear the LLM rename name cache. Next drag will re-invoke LLM for all entries."""
    st = get_state()
    count = st.clear_name_cache()
    return {"ok": True, "cleared": count}


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

    if body.tree_plan:
        # New tree-based linking
        dst = Path(section.path) / folder_name
        root_accepted = body.tree_plan.get("accepted_name") or folder_name
        dst = Path(section.path) / root_accepted
        from functools import partial
        link_func = partial(link_with_tree, tree=body.tree_plan)
        target_display = str(dst)
    elif body.link_plan:
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


@router.post("/rename-tree")
async def start_rename_tree(body: RenameTreeBody):
    """Build a rename tree for source_path and process it bottom-up with LLM.

    Returns the initial tree immediately (with cached names already filled).
    Remaining nodes are resolved asynchronously via WebSocket messages:
      rename_node_done: {type, task_id, key, suggested_name, cached}
      rename_tree_done: {type, task_id, tree, media_type}
      rename_error:     {type, task_id, error}
    """
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")

    src = Path(body.source_path)
    if not src.is_dir() and not src.is_file():
        raise HTTPException(400, f"Source not found: {body.source_path}")

    st = get_state()
    settings = st.load_llm_settings()
    max_parallel = int(settings.get("max_parallel", 5))

    task_id = uuid.uuid4().hex[:8]

    # Build the tree synchronously (fast — only reads names, not file contents)
    tree = await asyncio.to_thread(build_tree, src)

    # Resolve cached names immediately so the client sees them in the response
    _apply_cache(tree, st)

    asyncio.create_task(
        _run_rename_tree(task_id, tree, client, st, max_parallel)
    )

    return {"task_id": task_id, "tree": tree.to_dict()}


def _apply_cache(node: TreeNode, st) -> None:
    """Fill suggested_name from cache for all nodes that have a hit."""
    # We attach a transient attribute; to_dict() must include it.
    # Since TreeNode is a dataclass we can set it directly.
    cached = st.get_cached_name(node.key)
    if cached:
        node._suggested = cached  # transient, read in to_dict patch below
    for child in node.children:
        if child.is_dir:
            _apply_cache(child, st)


async def _run_rename_tree(
    task_id: str,
    root: TreeNode,
    client,
    st,
    max_parallel: int,
) -> None:
    """Process the rename tree bottom-up, streaming results via WebSocket."""
    semaphore = asyncio.Semaphore(max_parallel)
    # suggested_name map: key -> name (built up during processing)
    suggestions: dict[str, str] = {}

    # Pre-populate from cache
    def _collect_cached(node: TreeNode) -> None:
        cached = st.get_cached_name(node.key)
        if cached:
            suggestions[node.key] = cached
        for c in node.children:
            if c.is_dir:
                _collect_cached(c)
    _collect_cached(root)

    sibling_groups = collect_sibling_groups(root)

    for group in sibling_groups:
        # Split into cached (instant) and uncached (need LLM)
        cached_in_group = [n for n in group if n.key in suggestions]
        uncached = [n for n in group if n.key not in suggestions]

        # Broadcast cached hits immediately
        for node in cached_in_group:
            await manager.broadcast({
                "type": "rename_node_done",
                "task_id": task_id,
                "key": node.key,
                "suggested_name": suggestions[node.key],
                "cached": True,
            })

        if not uncached:
            continue

        # Build sibling context for LLM
        parent_context = _parent_context(group[0], root, suggestions)
        siblings_payload = []
        for node in uncached:
            children_info = []
            for c in node.children:
                suggested = suggestions.get(c.key, c.name)
                children_info.append(f"{suggested}/ ({c.file_count} files)")
            siblings_payload.append({
                "original_name": node.name,
                "children_info": children_info[:8],
                "sample_files": node.sample_files[:5],
            })

        async with semaphore:
            names = await asyncio.to_thread(
                client.rename_batch, siblings_payload, parent_context, group[0].depth
            )

        for node, suggested in zip(uncached, names):
            final_name = suggested or node.name
            suggestions[node.key] = final_name
            st.set_cached_name(node.key, final_name)
            await manager.broadcast({
                "type": "rename_node_done",
                "task_id": task_id,
                "key": node.key,
                "suggested_name": final_name,
                "cached": False,
            })

    # Infer media_type from root suggestion
    root_name = suggestions.get(root.key, root.name)
    has_season = any(
        suggestions.get(c.key, c.name).startswith("Season ")
        for c in root.children if c.is_dir
    )
    media_type = "tv" if has_season else "movie"

    # Build final tree dict with suggested names
    final_tree = _tree_with_suggestions(root, suggestions)

    await manager.broadcast({
        "type": "rename_tree_done",
        "task_id": task_id,
        "tree": final_tree,
        "media_type": media_type,
    })


def _parent_context(node: TreeNode, root: TreeNode, suggestions: dict[str, str]) -> str:
    """Build a human-readable parent context string for the LLM prompt."""
    if node.depth == 0:
        return "根目录"
    # For depth > 0 nodes, parent is the node at depth-1 — find it via root name
    root_name = suggestions.get(root.key, root.name)
    if node.depth == 1:
        return f"根目录 (原名: {root.name}, 建议名: {root_name})"
    return f"{root_name} 的子目录 (depth {node.depth - 1})"


def _tree_with_suggestions(node: TreeNode, suggestions: dict[str, str]) -> dict:
    """Serialise tree dict enriched with suggested_name fields."""
    d = node.to_dict()
    d["suggested_name"] = suggestions.get(node.key)
    d["children"] = [
        _tree_with_suggestions(c, suggestions) for c in node.children
    ]
    return d


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


@router.post("/reconcile")
async def reconcile_state():
    """Re-scan all sources and update entry states without re-running LLM.

    - LINKED entries whose target dir no longer exists → reset to PENDING.
    - PENDING/missing entries are matched to target dirs via two methods:
        1. name_cache lookup (fast, requires prior rename-tree run).
        2. Merkle key comparison: build_tree on both source and each target dir.
           If keys match, the files inside are identical → declare linked.
           This works even when files were linked/copied manually, because the
           Merkle key depends only on leaf file names, not directory names.
    - State entries whose source path no longer exists on disk → removed.
    - LLM name cache is NOT cleared.
    """
    st = get_state()

    # Build target directory map and pre-compute their Merkle keys once.
    # target_names: lower_name -> full_path
    # target_key_map: merkle_key -> full_path (for direct key comparison)
    target_names: dict[str, str] = {}
    target_key_map: dict[str, str] = {}

    for section in st.state.target_sections:
        if not section.path:
            continue
        section_dir = Path(section.path)
        if not section_dir.is_dir():
            continue
        for child in section_dir.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            target_names[child.name.lower()] = str(child)
            try:
                t = await asyncio.to_thread(build_tree, child)
                target_key_map[t.key] = str(child)
            except Exception:
                pass

    newly_linked = 0
    reset_to_pending = 0
    removed = 0
    changed = False

    for source_path in list(st.state.sources):
        scanned = await asyncio.to_thread(scan_source, source_path)
        scanned_paths = {item["path"] for item in scanned}

        # Remove state entries for paths no longer on disk
        stale = [
            k for k in list(st.state.entries)
            if (k.startswith(source_path + "/") or k.startswith(source_path + "\\"))
            and k not in scanned_paths
        ]
        for k in stale:
            del st.state.entries[k]
            removed += 1
            changed = True

        # Reset LINKED entries whose target dir was deleted
        for key, rec in list(st.state.entries.items()):
            if not (key.startswith(source_path + "/") or key.startswith(source_path + "\\")):
                continue
            if rec.status == EntryStatus.LINKED and rec.target_path:
                if not Path(rec.target_path).is_dir():
                    st.state.entries[key] = EntryRecord(status=EntryStatus.PENDING)
                    reset_to_pending += 1
                    changed = True

        # Detect PENDING entries → try cache lookup then Merkle key comparison
        for item in scanned:
            key = item["path"]
            rec = st.state.entries.get(key)
            if rec and rec.status != EntryStatus.PENDING:
                continue
            root_path = Path(key)
            if not root_path.is_dir():
                continue
            try:
                tree = await asyncio.to_thread(build_tree, root_path)
            except Exception:
                continue

            matched: str | None = None

            # Method 1: name_cache → target name lookup
            cached_name = st.get_cached_name(tree.key)
            if cached_name:
                matched = target_names.get(cached_name.lower())

            # Method 2: direct Merkle key comparison against all target dirs
            if not matched:
                matched = target_key_map.get(tree.key)

            if matched:
                st.state.entries[key] = EntryRecord(
                    status=EntryStatus.LINKED,
                    target_path=matched,
                )
                newly_linked += 1
                changed = True

    if changed:
        st.save()

    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    return {"ok": True, "newly_linked": newly_linked, "reset_to_pending": reset_to_pending, "removed": removed}


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
