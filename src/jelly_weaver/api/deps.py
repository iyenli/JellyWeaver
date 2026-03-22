"""Singleton dependencies for the API layer."""

from jelly_weaver.core.state import StateManager
from jelly_weaver.llm.client import LLMClient

_state_mgr: StateManager | None = None
_llm_client: LLMClient | None = None


def get_state() -> StateManager:
    global _state_mgr
    if _state_mgr is None:
        _state_mgr = StateManager()
    return _state_mgr


def get_llm() -> LLMClient | None:
    """Return LLMClient if API key is configured, else None."""
    global _llm_client
    settings = get_state().load_llm_settings()
    api_key = settings.get("api_key", "")
    if not api_key:
        return None
    _llm_client = LLMClient(
        api_base=settings.get("api_base", ""),
        api_key=api_key,
        model=settings.get("model", ""),
    )
    return _llm_client


def reset_llm() -> None:
    """Force re-creation on next get_llm() call."""
    global _llm_client
    _llm_client = None
