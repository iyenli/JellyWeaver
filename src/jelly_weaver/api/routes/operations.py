"""LLM parse + hardlink operations."""

import asyncio
import json
import uuid
import logging
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state, get_llm
from jelly_weaver.api.ws import manager
from jelly_weaver.core.models import EntryRecord, EntryStatus
from jelly_weaver.core.hardlink import link_movie, link_tv_show, link_with_plan, link_with_tree, link_file_group, unlink_target, _companion_files
from jelly_weaver.core.scanner import scan_source
from jelly_weaver.core.tree import build_tree, build_file_group_tree, TreeNode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ops", tags=["operations"])


def _collect_tree_keys(node: TreeNode) -> list[str]:
    """Collect Merkle keys of all directory nodes in a tree."""
    keys = [node.key] if node.is_dir else []
    for child in node.children:
        keys.extend(_collect_tree_keys(child))
    return keys


async def _remove_source_cache(source_path: str, st) -> None:
    """Build tree for source and remove all its node keys from name_cache."""
    p = Path(source_path)
    if not p.is_dir():
        return
    try:
        tree = await asyncio.to_thread(build_tree, p)
        keys = _collect_tree_keys(tree)
        st.remove_cached_names(keys)
    except Exception as e:
        logger.warning("Failed to remove cache for %s: %s", source_path, e)

class LinkBody(BaseModel):
    source_path: str | None = None       # directory or single file
    source_paths: list[str] | None = None  # file group (multi-select)
    companion_paths: list[str] | None = None  # user-confirmed companion files
    section_id: str
    media_type: str  # "movie" or "tv"
    title_en: str
    title_zh: str = ""
    year: int
    link_plan: list[dict] | None = None
    tree_plan: dict | None = None  # RenameNode tree with accepted_name fields


class UnlinkBody(BaseModel):
    target_folder_path: str


class RenameTreeBody(BaseModel):
    source_path: str | None = None
    source_paths: list[str] | None = None  # file group


@router.delete("/name-cache")
async def clear_name_cache():
    """Clear the entire LLM rename name cache. Next rename will re-invoke LLM for all entries."""
    st = get_state()
    count = st.clear_name_cache()
    return {"ok": True, "cleared": count}


@router.post("/link")
async def start_link(body: LinkBody):
    st = get_state()
    section = st.get_target_section(body.section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {body.section_id}")
    if not section.path:
        raise HTTPException(400, "Target section has no path configured")

    folder_name = body.tree_plan.get("accepted_name") if body.tree_plan else None
    folder_name = folder_name or f"{body.title_en} ({body.year})"
    task_id = uuid.uuid4().hex[:8]

    # --- File group or single loose file ---
    if body.source_paths or (body.source_path and Path(body.source_path).is_file()):
        files = [Path(p) for p in body.source_paths] if body.source_paths else [Path(body.source_path)]
        for f in files:
            if not f.is_file():
                raise HTTPException(400, f"Not a file: {f}")
        dst = Path(section.path) / folder_name
        source_keys = [str(f) for f in files]
        extra = [Path(p) for p in body.companion_paths] if body.companion_paths is not None else None
        asyncio.create_task(_run_link_group(task_id, files, dst, source_keys, st, extra_files=extra))
        return {"task_id": task_id, "target_path": str(dst)}

    # --- Directory source ---
    if not body.source_path:
        raise HTTPException(400, "source_path is required for directory linking")
    src = Path(body.source_path)
    if not src.is_dir():
        raise HTTPException(400, f"Source not found: {body.source_path}")

    if body.tree_plan:
        root_accepted = body.tree_plan.get("accepted_name") or folder_name
        dst = Path(section.path) / root_accepted
        _tree = body.tree_plan
        _mt = body.media_type
        def link_func(src, dst, cb, *, _t=_tree, _m=_mt):  # noqa: E306
            return link_with_tree(src, dst, _t, cb, media_type=_m)
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

    asyncio.create_task(_run_link(task_id, link_func, src, dst, body.source_path, st, target_display))
    return {"task_id": task_id, "target_path": target_display}


@router.post("/rename-tree")
async def start_rename_tree(body: RenameTreeBody):
    """Build a rename tree for source_path and process it with LLM.

    Returns the initial tree immediately (with cached names already filled).
    Remaining nodes are resolved asynchronously via WebSocket messages:
      rename_node_done: {type, task_id, key, suggested_name, cached}
      rename_tree_done: {type, task_id, tree, media_type}
      rename_error:     {type, task_id, error}
    """
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")

    if body.source_paths:
        # File group: build virtual tree from multiple files
        files = [Path(p) for p in body.source_paths]
        for f in files:
            if not f.is_file():
                raise HTTPException(400, f"Not a file: {f}")
        companions = [{"name": c.name, "path": str(c)} for f in files for c in _companion_files(f)]
        tree = await asyncio.to_thread(build_file_group_tree, files)
    elif body.source_path:
        src = Path(body.source_path)
        if not src.exists():
            raise HTTPException(400, f"Source not found: {body.source_path}")
        if src.is_file():
            # Single loose file: treat as single-item group
            companions = [{"name": c.name, "path": str(c)} for c in _companion_files(src)]
            tree = await asyncio.to_thread(build_file_group_tree, [src])
        else:
            companions = []
            tree = await asyncio.to_thread(build_tree, src)
    else:
        raise HTTPException(400, "source_path or source_paths is required")

    st = get_state()
    task_id = uuid.uuid4().hex[:8]

    asyncio.create_task(
        _run_rename_tree(task_id, tree, client, st)
    )

    return {"task_id": task_id, "tree": _tree_with_suggestions(tree, {}), "companion_files": companions}


async def _run_rename_tree(
    task_id: str,
    root: TreeNode,
    client,
    st,
) -> None:
    """Process the rename tree in a single LLM call, streaming results via WebSocket."""
    try:
        await _run_rename_tree_inner(task_id, root, client, st)
    except Exception as e:
        logger.error("rename tree task %s failed: %s", task_id, e)
        await manager.broadcast({
            "type": "rename_error",
            "task_id": task_id,
            "error": str(e),
        })


async def _run_rename_tree_inner(
    task_id: str,
    root: TreeNode,
    client,
    st,
) -> None:
    # Always call LLM — never read from cache
    new_names, llm_media_type = await asyncio.to_thread(client.rename_tree, root)
    for key, name in new_names.items():
        st.set_cached_name(key, name)
        await manager.broadcast({
            "type": "rename_node_done",
            "task_id": task_id,
            "key": key,
            "suggested_name": name,
            "cached": False,
        })
    if llm_media_type in ("tv", "movie"):
        st.set_cached_media_type(root.key, llm_media_type)

    # Use LLM-provided media_type; fall back to Season-prefix heuristic only as last resort
    if llm_media_type in ("tv", "movie"):
        media_type = llm_media_type
    else:
        has_season = any(
            new_names.get(c.key, c.name).startswith("Season ")
            for c in root.children if c.is_dir
        )
        media_type = "tv" if has_season else "movie"

    final_tree = _tree_with_suggestions(root, new_names)

    await manager.broadcast({
        "type": "rename_tree_done",
        "task_id": task_id,
        "tree": final_tree,
        "media_type": media_type,
    })


def _tree_with_suggestions(node: TreeNode, suggestions: dict[str, str]) -> dict:
    """Serialise tree dict enriched with suggested_name fields."""
    d = node.to_dict()
    d["suggested_name"] = suggestions.get(node.key)
    d["children"] = [
        _tree_with_suggestions(c, suggestions) for c in node.children
    ]
    return d


async def _run_link_group(
    task_id: str,
    files: list[Path],
    dst: Path,
    source_keys: list[str],
    st,
    extra_files: list[Path] | None = None,
) -> None:
    """Link a file group and store one EntryRecord per source file."""
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

        result = await asyncio.to_thread(link_file_group, files, dst, progress_cb, extra_files)

        now = datetime.now().isoformat()
        for key in source_keys:
            st.upsert_entry(key, EntryRecord(
                status=EntryStatus.LINKED,
                target_path=str(dst),
                linked_at=now,
                file_count=1,
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
        logger.error("Link group task %s failed: %s", task_id, e)
        await manager.broadcast({
            "type": "link_error",
            "task_id": task_id,
            "error": str(e),
        })


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
                    await _remove_source_cache(key, st)
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


class RenameLibraryBody(BaseModel):
    section_id: str


class JellyfinScanBody(BaseModel):
    section_id: str


@router.post("/rename-library")
async def rename_library(body: RenameLibraryBody):
    """Rename all subdirectories in a library using the LLM.

    For each subdirectory, builds a Merkle tree, calls LLM to get the correct
    name, writes result to cache (for reconcile_state), and renames in-place
    if the names differ. Also updates any matching state entries.
    """
    st = get_state()
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")
    section = st.get_target_section(body.section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {body.section_id}")
    if not section.path or not Path(section.path).is_dir():
        raise HTTPException(400, "Library path is not configured or does not exist")

    section_dir = Path(section.path)
    renamed = 0
    unchanged = 0
    no_cache = 0
    errors: list[str] = []

    children = sorted(
        [c for c in section_dir.iterdir() if c.is_dir() and not c.name.startswith(".")],
        key=lambda c: c.name,
    )

    for child in children:
        try:
            tree = await asyncio.to_thread(build_tree, child)
            new_names, llm_media_type = await asyncio.to_thread(client.rename_tree, tree)

            # Write to cache so reconcile_state can match source → target
            for key, name in new_names.items():
                st.set_cached_name(key, name)
            if llm_media_type in ("tv", "movie"):
                st.set_cached_media_type(tree.key, llm_media_type)

            correct_name = new_names.get(tree.key)
            if not correct_name:
                no_cache += 1
                continue

            if correct_name == child.name:
                unchanged += 1
                continue

            new_path = section_dir / correct_name
            if new_path.exists():
                errors.append(f"Cannot rename '{child.name}' → '{correct_name}': target already exists")
                continue

            child.rename(new_path)

            # Update any state records that point to the old path
            for key, rec in list(st.state.entries.items()):
                if rec.target_path and Path(rec.target_path).resolve() == child.resolve():
                    st.state.entries[key] = EntryRecord(
                        status=rec.status,
                        target_path=str(new_path),
                        linked_at=rec.linked_at,
                        file_count=rec.file_count,
                    )

            renamed += 1
        except Exception as exc:
            errors.append(f"'{child.name}': {exc}")

    if renamed > 0 or errors:
        st.save()

    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    await manager.broadcast({"type": "state_changed", "scope": "targets"})

    return {
        "ok": True,
        "renamed": renamed,
        "unchanged": unchanged,
        "no_cache": no_cache,
        "errors": errors,
    }


def _jellyfin_get(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("X-Emby-Token", api_key)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _jellyfin_post(url: str, api_key: str, params: dict | None = None) -> int:
    full_url = url
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{qs}"
    req = urllib.request.Request(full_url, data=b"", method="POST")
    req.add_header("X-Emby-Token", api_key)
    req.add_header("Content-Length", "0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


@router.post("/jellyfin-scan")
async def jellyfin_scan(body: JellyfinScanBody):
    """Trigger a Jellyfin library rescan for the given target section.

    Finds the Jellyfin virtual folder whose Locations contain the section path,
    then calls Items/{id}/Refresh. Falls back to a full Library/Refresh if no
    matching folder is found.
    """
    st = get_state()
    section = st.get_target_section(body.section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {body.section_id}")

    settings = st.load_llm_settings()
    jellyfin_url = settings.get("jellyfin_url", "").rstrip("/")
    jellyfin_api_key = settings.get("jellyfin_api_key", "")

    if not jellyfin_url:
        raise HTTPException(400, "Jellyfin URL not configured — set it in Settings")
    if not jellyfin_api_key:
        raise HTTPException(400, "Jellyfin API key not configured — set it in Settings")

    section_path = section.path.replace("\\", "/").rstrip("/")

    try:
        folders = await asyncio.to_thread(
            _jellyfin_get,
            f"{jellyfin_url}/Library/VirtualFolders",
            jellyfin_api_key,
        )
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"Jellyfin API error: {exc.code} {exc.reason}")
    except Exception as exc:
        raise HTTPException(502, f"Cannot reach Jellyfin at {jellyfin_url}: {exc}")

    # Match virtual folder by location path
    matched_id: str | None = None
    if isinstance(folders, list):
        for folder in folders:
            for loc in folder.get("Locations", []):
                if loc.replace("\\", "/").rstrip("/") == section_path:
                    matched_id = folder.get("ItemId") or folder.get("Id")
                    break
            if matched_id:
                break

    try:
        if matched_id:
            await asyncio.to_thread(
                _jellyfin_post,
                f"{jellyfin_url}/Items/{matched_id}/Refresh",
                jellyfin_api_key,
                {"Recursive": "true", "MetadataRefreshMode": "Default", "ImageRefreshMode": "Default"},
            )
        else:
            await asyncio.to_thread(
                _jellyfin_post,
                f"{jellyfin_url}/Library/Refresh",
                jellyfin_api_key,
            )
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"Jellyfin refresh failed: {exc.code} {exc.reason}")
    except Exception as exc:
        raise HTTPException(502, f"Jellyfin refresh error: {exc}")

    return {"ok": True, "matched_library": matched_id is not None}


class RelinkSectionBody(BaseModel):
    section_id: str


@router.post("/relink-section")
async def relink_section(body: RelinkSectionBody):
    """Unlink all tracked items in a section and re-link using LLM.

    For each entry in state that is LINKED with target_path inside this section:
    1. Unlinks the target folder.
    2. Calls LLM to get correct names (writes result to cache for reconcile_state).
    3. If root name is returned: re-links with link_with_tree.
    4. If LLM fails to return a root name: leaves the entry as PENDING.

    Runs as a background task. Progress events via WebSocket:
      relink_progress: {type, task_id, done, total}
      relink_done:     {type, task_id, relinked, unlinked_only, errors}
    """
    st = get_state()
    client = get_llm()
    if client is None:
        raise HTTPException(400, "LLM not configured — set API key in settings")
    section = st.get_target_section(body.section_id)
    if section is None:
        raise HTTPException(404, f"Section not found: {body.section_id}")
    if not section.path or not Path(section.path).is_dir():
        raise HTTPException(400, "Library path not configured or does not exist")

    section_dir = Path(section.path).resolve()

    # Find entries linked to this section
    linked_entries = [
        (key, rec)
        for key, rec in list(st.state.entries.items())
        if rec.status == EntryStatus.LINKED
        and rec.target_path
        and Path(rec.target_path).resolve().parent == section_dir
    ]

    task_id = uuid.uuid4().hex[:8]
    asyncio.create_task(_run_relink_section(task_id, linked_entries, section_dir, st, client))
    return {"task_id": task_id, "total": len(linked_entries)}


async def _run_relink_section(
    task_id: str,
    entries: list,
    section_dir: Path,
    st,
    client,
) -> None:
    relinked = 0
    unlinked_only = 0
    errors: list[str] = []
    total = len(entries)
    done = 0

    for source_key, rec in entries:
        target_path = Path(rec.target_path)
        source_path = Path(source_key)

        try:
            # Unlink the current target folder
            if target_path.is_dir():
                await asyncio.to_thread(unlink_target, target_path)

            # Reset entry to PENDING
            st.state.entries[source_key] = EntryRecord(status=EntryStatus.PENDING)
            st.save()

            if not source_path.is_dir():
                unlinked_only += 1
            else:
                # Call LLM for fresh names
                tree = await asyncio.to_thread(build_tree, source_path)
                new_names, llm_media_type = await asyncio.to_thread(client.rename_tree, tree)

                # Write to cache for reconcile_state
                for key, name in new_names.items():
                    st.set_cached_name(key, name)
                if llm_media_type in ("tv", "movie"):
                    st.set_cached_media_type(tree.key, llm_media_type)

                root_name = new_names.get(tree.key)
                if not root_name:
                    unlinked_only += 1
                else:
                    tree_plan = _tree_with_suggestions(tree, new_names)
                    _set_accepted_from_cache(tree_plan, new_names)

                    dst = section_dir / root_name
                    media_type = llm_media_type or "movie"
                    result = await asyncio.to_thread(
                        link_with_tree, source_path, dst, tree_plan,
                        media_type=media_type,
                    )

                    st.upsert_entry(source_key, EntryRecord(
                        status=EntryStatus.LINKED,
                        target_path=str(dst),
                        linked_at=datetime.now().isoformat(),
                        file_count=result.linked + result.skipped,
                    ))
                    relinked += 1
        except Exception as exc:
            errors.append(f"{source_path.name}: {exc}")

        done += 1
        await manager.broadcast({
            "type": "relink_progress",
            "task_id": task_id,
            "done": done,
            "total": total,
        })

    await manager.broadcast({
        "type": "relink_done",
        "task_id": task_id,
        "relinked": relinked,
        "unlinked_only": unlinked_only,
        "errors": errors,
    })
    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    await manager.broadcast({"type": "state_changed", "scope": "targets"})


def _set_accepted_from_cache(node: dict, suggestions: dict[str, str]) -> None:
    """Recursively set accepted_name from cache suggestions in a tree_plan dict."""
    key = node.get("key", "")
    node["accepted_name"] = suggestions.get(key) or None
    for child in node.get("children", []):
        if child.get("is_dir", True):
            _set_accepted_from_cache(child, suggestions)


@router.post("/unlink")
async def unlink_folder(body: UnlinkBody):
    """Remove a hardlinked target (directory or loose file) and reset source entries."""
    import os
    target_path = Path(body.target_folder_path)

    if not target_path.exists():
        raise HTTPException(404, f"Target not found: {body.target_folder_path}")

    st = get_state()
    # Find ALL source entries pointing to this target
    source_keys = [
        key for key, rec in st.state.entries.items()
        if rec.target_path and Path(rec.target_path) == target_path
    ]

    try:
        if target_path.is_dir():
            removed = await asyncio.to_thread(unlink_target, target_path)
        else:
            await asyncio.to_thread(os.unlink, target_path)
            removed = 1
    except OSError as exc:
        raise HTTPException(500, f"无法删除（可能有文件正被其他程序占用，如 Jellyfin）：{exc}")

    # Reset all matched source entries to pending
    for source_key in source_keys:
        st.upsert_entry(source_key, EntryRecord(status=EntryStatus.PENDING))
        await _remove_source_cache(source_key, st)

    await manager.broadcast({"type": "state_changed", "scope": "entries"})
    await manager.broadcast({"type": "state_changed", "scope": "targets"})
    return {"ok": True, "removed_files": removed, "source_key": source_keys[0] if source_keys else None}
    return {"ok": True, "removed_files": removed, "source_key": source_keys[0] if source_keys else None}
