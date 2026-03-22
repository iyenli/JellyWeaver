"""JSON-based state persistence for Jelly Weaver."""

import json
from pathlib import Path

from .models import AppState, EntryRecord, EntryStatus, TargetSection


STATE_DIR = Path.home() / ".jelly-weaver"
STATE_FILE = STATE_DIR / "state.json"


class StateManager:
    def __init__(self, path: Path = STATE_FILE):
        self._path = path
        self._state: AppState | None = None

    @property
    def state(self) -> AppState:
        if self._state is None:
            self.load()
        return self._state

    def load(self) -> AppState:
        if self._path.exists():
            raw = json.loads(self._path.read_text("utf-8"))
            self._state = self._deserialize(raw)
        else:
            self._state = AppState()
        return self._state

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self._serialize(self.state)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- CRUD helpers ---

    def add_source(self, path: str) -> None:
        if path not in self.state.sources:
            self.state.sources.append(path)
            self.save()

    def remove_source(self, path: str) -> None:
        if path in self.state.sources:
            self.state.sources.remove(path)
            self.save()

    def add_target_section(self, section: TargetSection | None = None) -> TargetSection:
        if len(self.state.target_sections) >= 4:
            raise ValueError("Maximum 4 target sections allowed")
        if section is None:
            section = TargetSection(name=f"Library {len(self.state.target_sections) + 1}")
        self.state.target_sections.append(section)
        self.save()
        return section

    def remove_target_section(self, section_id: str) -> None:
        self.state.target_sections = [
            s for s in self.state.target_sections if s.id != section_id
        ]
        self.save()

    def update_target_section(self, section_id: str, **kwargs) -> None:
        for s in self.state.target_sections:
            if s.id == section_id:
                for k, v in kwargs.items():
                    setattr(s, k, v)
                break
        self.save()

    def get_target_section(self, section_id: str) -> TargetSection | None:
        for s in self.state.target_sections:
            if s.id == section_id:
                return s
        return None

    def upsert_entry(self, key: str, record: EntryRecord) -> None:
        self.state.entries[key] = record
        self.save()

    def update_setting(self, key: str, value: str) -> None:
        self.state.settings[key] = value
        self.save()

    # --- Serialization ---

    @staticmethod
    def _serialize(state: AppState) -> dict:
        entries = {}
        for k, v in state.entries.items():
            entries[k] = {
                "status": v.status.value,
                "target_path": v.target_path,
                "linked_at": v.linked_at,
                "file_count": v.file_count,
            }
        sections = []
        for s in state.target_sections:
            sections.append({
                "id": s.id,
                "name": s.name,
                "media_type": s.media_type,
                "path": s.path,
            })
        return {
            "sources": state.sources,
            "target_sections": sections,
            "entries": entries,
            "settings": state.settings,
        }

    @staticmethod
    def _deserialize(raw: dict) -> AppState:
        entries = {}
        for k, v in raw.get("entries", {}).items():
            entries[k] = EntryRecord(
                status=EntryStatus(v.get("status", "pending")),
                target_path=v.get("target_path"),
                linked_at=v.get("linked_at"),
                file_count=v.get("file_count", 0),
            )

        # Backward compat: migrate old "targets" dict to target_sections
        sections = []
        if "target_sections" in raw:
            for s in raw["target_sections"]:
                sections.append(TargetSection(
                    id=s["id"],
                    name=s.get("name", ""),
                    media_type=s.get("media_type", "movies"),
                    path=s.get("path", ""),
                ))
        elif "targets" in raw:
            old = raw["targets"]
            if old.get("movies"):
                sections.append(TargetSection(
                    name="Movies", media_type="movies", path=old["movies"],
                ))
            if old.get("tv"):
                sections.append(TargetSection(
                    name="TV Shows", media_type="tv", path=old["tv"],
                ))

        return AppState(
            sources=raw.get("sources", []),
            target_sections=sections,
            entries=entries,
            settings=raw.get("settings", AppState().settings),
        )
