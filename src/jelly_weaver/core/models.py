"""Data models for Jelly Weaver."""

import uuid
from dataclasses import dataclass, field
from enum import Enum


class EntryStatus(Enum):
    PENDING = "pending"
    LINKED = "linked"
    IGNORED = "ignored"


class SourceStructure(Enum):
    HAS_SEASON_DIRS = "has_season_dirs"
    FLAT_WITH_EPISODES = "flat_with_episodes"
    SIMPLE = "simple"


@dataclass
class TargetSection:
    """A user-defined library slot (e.g. Movies, Anime, TV Shows)."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    media_type: str = "movies"  # "movies" or "tv"
    path: str = ""


@dataclass
class EntryRecord:
    status: EntryStatus = EntryStatus.PENDING
    target_path: str | None = None
    linked_at: str | None = None
    file_count: int = 0


@dataclass
class LinkResult:
    linked: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class AppState:
    sources: list[str] = field(default_factory=list)
    target_sections: list[TargetSection] = field(default_factory=list)
    entries: dict[str, EntryRecord] = field(default_factory=dict)
    settings: dict = field(default_factory=lambda: {
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
    })
    # Merkle-key → LLM-suggested name (persisted cache)
    name_cache: dict[str, str] = field(default_factory=dict)
    # root Merkle-key → "tv" | "movie" (persisted alongside name_cache)
    media_type_cache: dict[str, str] = field(default_factory=dict)
