"""Hardlink engine: create hardlinks from source to Jellyfin-standard target."""

import os
import shutil
import stat
from pathlib import Path

from .models import LinkResult, SourceStructure
from .media_parser import (
    classify_source,
    is_media_file,
    is_video_file,
    parse_episode,
    parse_season_dir,
)


def _check_same_device(src: Path, dst_parent: Path) -> None:
    """Raise if src and dst are on different filesystems."""
    # Use the nearest existing ancestor of dst_parent
    check_path = dst_parent
    while not check_path.exists():
        check_path = check_path.parent
    if os.stat(src).st_dev != os.stat(check_path).st_dev:
        raise OSError(
            f"Cannot hardlink across volumes: "
            f"{src} and {dst_parent} are on different filesystems."
        )


def _hardlink_file(
    src_file: Path, dst_file: Path, result: LinkResult,
) -> None:
    """Hardlink a single file, skipping if target exists."""
    if dst_file.exists():
        result.skipped += 1
        return
    try:
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        os.link(src_file, dst_file)
        result.linked += 1
    except OSError as e:
        result.errors.append(f"{src_file}: {e}")


def link_movie(
    src: Path,
    dst: Path,
    progress_cb=None,
) -> LinkResult:
    """Hardlink all media files from src into dst, preserving relative paths."""
    _check_same_device(src, dst)
    result = LinkResult()
    media_files = [
        f for f in src.rglob("*")
        if f.is_file() and is_media_file(f)
    ]
    for i, f in enumerate(media_files):
        rel = f.relative_to(src)
        _hardlink_file(f, dst / rel, result)
        if progress_cb:
            progress_cb(i + 1, len(media_files))
    return result


def link_tv_show(
    src: Path,
    dst: Path,
    progress_cb=None,
) -> LinkResult:
    """Hardlink TV show files, auto-organizing into Season XX dirs."""
    _check_same_device(src, dst)
    structure = classify_source(src)

    if structure == SourceStructure.SIMPLE:
        return link_movie(src, dst, progress_cb)

    result = LinkResult()

    if structure == SourceStructure.HAS_SEASON_DIRS:
        media_files = [
            f for f in src.rglob("*")
            if f.is_file() and is_media_file(f)
        ]
        total = len(media_files)
        count = 0
        for child in sorted(src.iterdir()):
            if not child.is_dir():
                continue
            snum = parse_season_dir(child.name)
            if snum is None:
                continue
            season_dir = dst / f"Season {snum:02d}"
            for f in sorted(child.rglob("*")):
                if f.is_file() and is_media_file(f):
                    rel = f.relative_to(child)
                    _hardlink_file(f, season_dir / rel, result)
                    count += 1
                    if progress_cb:
                        progress_cb(count, total)

    elif structure == SourceStructure.FLAT_WITH_EPISODES:
        # Group files by season number from SxxExx pattern
        grouped: dict[int, list[Path]] = {}
        for f in src.rglob("*"):
            if not f.is_file() or not is_media_file(f):
                continue
            ep = parse_episode(f.name)
            season = ep[0] if ep else 1  # default to Season 01
            grouped.setdefault(season, []).append(f)

        total = sum(len(v) for v in grouped.values())
        count = 0
        for season, files in sorted(grouped.items()):
            season_dir = dst / f"Season {season:02d}"
            for f in sorted(files):
                _hardlink_file(f, season_dir / f.name, result)
                count += 1
                if progress_cb:
                    progress_cb(count, total)

    return result


def link_with_plan(
    src: Path,
    dst: Path,
    progress_cb=None,
    *,
    plan_items: list[dict],
    title_en: str,
    year: int,
) -> LinkResult:
    """Hardlink files using an LLM-generated link plan.

    For movie_collection: each item with title_en creates its own Title (Year)/ folder.
    For TV/other: creates title_en (year)/ under dst, then maps source_subdir -> target_subdir.
    """
    _check_same_device(src, dst)
    result = LinkResult()

    is_collection = any(item.get("title_en") for item in plan_items)

    # Collect all media files first for progress tracking
    all_files: list[tuple[Path, Path]] = []

    for item in plan_items:
        source_subdir = item.get("source_subdir", "")
        target_subdir = item.get("target_subdir", "")
        source_dir = src / source_subdir if source_subdir else src

        if is_collection:
            item_title = item.get("title_en") or title_en
            item_year = item.get("year") or year
            target_dir = dst / f"{item_title} ({item_year})"
        else:
            show_dir = dst / f"{title_en} ({year})"
            target_dir = show_dir / target_subdir if target_subdir else show_dir

        if not source_dir.is_dir():
            continue

        for f in sorted(source_dir.rglob("*")):
            if f.is_file() and is_media_file(f):
                rel = f.relative_to(source_dir)
                all_files.append((f, target_dir / rel))

    # Execute hardlinks
    for i, (src_file, dst_file) in enumerate(all_files):
        _hardlink_file(src_file, dst_file, result)
        if progress_cb:
            progress_cb(i + 1, len(all_files))

    return result


def _lcp_len(a: str, b: str) -> int:
    """Case-insensitive longest common prefix length."""
    al, bl = a.lower(), b.lower()
    n = min(len(al), len(bl))
    for i in range(n):
        if al[i] != bl[i]:
            return i
    return n


def _companion_files(video_file: Path) -> list[Path]:
    """Find companion subtitle/meta files via longest-common-prefix matching.

    A sibling is a companion when:
      LCP(video_stem, sibling_name) >= min(len(video_stem), 8)

    This tolerates common real-world patterns:
      Movie.Name.2022.1080p.mkv  →  Movie.Name.2022.chi.srt   (exact stem prefix)
      Movie.Name.2022.1080p.mkv  →  Movie.Name.2022.srt        (shorter subtitle)
      Movie.Name.2022.mkv        →  Movie.Name.srt             (8-char LCP: "Movie.Na")
    """
    video_stem = video_file.stem
    threshold = min(len(video_stem), 8)
    result = []
    for sibling in sorted(video_file.parent.iterdir()):
        if sibling == video_file or not sibling.is_file():
            continue
        if not (is_media_file(sibling) and not is_video_file(sibling)):
            continue
        if _lcp_len(video_stem, sibling.name) >= threshold:
            result.append(sibling)
    return result


def link_file_group(
    src_files: list[Path],
    dst: Path,
    progress_cb=None,
    extra_files: list[Path] | None = None,
) -> LinkResult:
    """Hardlink video files + companion subtitles into dst.

    If extra_files is provided it is used as the companion list (user-confirmed
    selection). Otherwise companions are discovered automatically via LCP matching.
    """
    all_files: list[Path] = []
    for f in src_files:
        all_files.append(f)
        companions = extra_files if extra_files is not None else _companion_files(f)
        all_files.extend(companions)

    if all_files:
        _check_same_device(all_files[0], dst)
    result = LinkResult()
    for i, f in enumerate(all_files):
        _hardlink_file(f, dst / f.name, result)
        if progress_cb:
            progress_cb(i + 1, len(all_files))
    return result


def _handle_rmtree_error(func, path, exc_info):
    """Error handler for shutil.rmtree: make read-only files writable before retry.

    On Windows, files can be marked read-only, causing shutil.rmtree to fail.
    This handler clears the read-only attribute and retries the operation.
    Note: since these are hardlinks, this also affects the source file's attributes.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def unlink_target(target_dir: Path) -> int:
    """Remove a hardlinked target directory. Returns the number of files removed.

    Since these are hardlinks, removing them does not delete the original source files.
    Raises OSError if files are locked by another process (e.g. Jellyfin streaming).
    """
    if not target_dir.is_dir():
        return 0
    count = sum(1 for f in target_dir.rglob("*") if f.is_file())
    shutil.rmtree(target_dir, onerror=_handle_rmtree_error)
    return count


def link_with_tree(
    src: Path,
    dst: Path,
    tree: dict,
    progress_cb=None,
    *,
    media_type: str = "movie",
) -> LinkResult:
    """Hardlink files using a rename tree (accepted-name recursive mapping).

    The tree dict mirrors the TreeNode.to_dict() output with an added
    'accepted_name' key at each directory node (the name the user confirmed).
    Files are never renamed — they are hardlinked under the accepted directory
    structure.

    Layout produced (example):
        src/老友记S01.Friends.1994/ → dst/Season 01/
        src/老友记S02.Friends.1995/ → dst/Season 02/

    For the root node the accepted name is already baked into dst by the caller
    (dst = target_section_path / root_accepted_name).

    For flat TV shows (media_type="tv", no dir children in tree), episode files
    are automatically grouped into Season XX subfolders by SxxExx pattern.

    Args:
        src: Source directory (root entry on disk).
        dst: Destination directory (already includes root accepted name).
        tree: Serialised TreeNode dict (with 'accepted_name' fields added).
        progress_cb: Optional (current, total) callback.
        media_type: "tv" or "movie" — controls flat-file season grouping.
    """
    _check_same_device(src, dst)
    result = LinkResult()

    # For flat TV shows (no dir children in tree), group episodes into Season XX/
    dir_children = [c for c in tree.get("children", []) if c.get("is_dir", True)]
    if media_type == "tv" and not dir_children:
        grouped: dict[int, list[Path]] = {}
        for f in src.rglob("*"):
            if not f.is_file() or not is_media_file(f):
                continue
            ep = parse_episode(f.name)
            season = ep[0] if ep else 1
            grouped.setdefault(season, []).append(f)
        total = sum(len(v) for v in grouped.values())
        count = 0
        for season, files in sorted(grouped.items()):
            season_dir = dst / f"Season {season:02d}"
            for f in sorted(files):
                _hardlink_file(f, season_dir / f.name, result)
                count += 1
                if progress_cb:
                    progress_cb(count, total)
        return result

    # Collect all (src_file, dst_file) pairs by walking the tree
    all_files: list[tuple[Path, Path]] = []
    _collect_tree_files(src, dst, tree, all_files)

    for i, (src_file, dst_file) in enumerate(all_files):
        _hardlink_file(src_file, dst_file, result)
        if progress_cb:
            progress_cb(i + 1, len(all_files))

    return result


def _collect_tree_files(
    src_dir: Path,
    dst_dir: Path,
    node: dict,
    out: list[tuple[Path, Path]],
) -> None:
    """Recursively walk tree nodes and collect (src, dst) file pairs."""
    children = node.get("children", [])

    if not children:
        # Leaf directory or file — hardlink all media files directly
        for f in sorted(src_dir.rglob("*")):
            if f.is_file() and is_media_file(f):
                rel = f.relative_to(src_dir)
                out.append((f, dst_dir / rel))
        return

    # Separate dir children and any loose files at this level
    loose_files = [
        f for f in src_dir.iterdir()
        if f.is_file() and is_media_file(f)
    ]
    for f in sorted(loose_files):
        out.append((f, dst_dir / f.name))

    for child_node in children:
        if not child_node.get("is_dir", True):
            continue
        original_name = child_node["name"]
        accepted_name = child_node.get("accepted_name") or original_name
        child_src = src_dir / original_name
        child_dst = dst_dir / accepted_name
        if child_src.is_dir():
            _collect_tree_files(child_src, child_dst, child_node, out)
