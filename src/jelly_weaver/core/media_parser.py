"""Media file parsing: SxxExx extraction, season detection, source classification."""

import re
from pathlib import Path

from .models import SourceStructure

# Supported file extensions
VIDEO_EXTS = frozenset({
    ".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".mov",
})
SUBTITLE_EXTS = frozenset({
    ".ass", ".ssa", ".srt", ".sup", ".sub", ".idx",
})
META_EXTS = frozenset({".nfo"})
MEDIA_EXTS = VIDEO_EXTS | SUBTITLE_EXTS | META_EXTS

# Regex patterns
_EPISODE_RE = re.compile(
    r"S(\d{1,2})[.\-_ ]?E(\d{1,3})", re.IGNORECASE,
)
_SEASON_DIR_RE = re.compile(
    r"^(?:Season\s*|S)(\d{1,2})$", re.IGNORECASE,
)


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTS


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def is_subtitle_file(path: Path) -> bool:
    return path.suffix.lower() in SUBTITLE_EXTS


def parse_episode(filename: str) -> tuple[int, int] | None:
    """Extract (season, episode) from a filename. Returns None if not found."""
    m = _EPISODE_RE.search(filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def parse_season_dir(dirname: str) -> int | None:
    """Check if a directory name is a season folder. Returns season number or None."""
    m = _SEASON_DIR_RE.match(dirname.strip())
    if m:
        return int(m.group(1))
    return None


def classify_source(path: Path) -> SourceStructure:
    """Classify the internal structure of a source directory."""
    if not path.is_dir():
        return SourceStructure.SIMPLE

    has_season_dirs = False
    has_episodes = False

    for child in path.iterdir():
        if child.is_dir() and parse_season_dir(child.name) is not None:
            has_season_dirs = True
            break

    if has_season_dirs:
        return SourceStructure.HAS_SEASON_DIRS

    # Check files for SxxExx patterns
    for child in path.rglob("*"):
        if child.is_file() and is_video_file(child):
            if parse_episode(child.name) is not None:
                has_episodes = True
                break

    if has_episodes:
        return SourceStructure.FLAT_WITH_EPISODES

    return SourceStructure.SIMPLE
