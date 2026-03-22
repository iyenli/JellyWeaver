"""Settings routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from jelly_weaver.api.deps import get_state, reset_llm
from jelly_weaver.api.ws import manager

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsBody(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


@router.get("")
async def get_settings():
    st = get_state()
    settings = st.state.settings
    api_key = settings.get("api_key", "")
    return {
        "api_base": settings.get("api_base", ""),
        "model": settings.get("model", ""),
        "api_key": "",
        "api_key_configured": bool(api_key),
        "api_key_preview": (
            api_key[:6] + "..." + api_key[-4:]
            if len(api_key) > 10
            else ("***" if api_key else "")
        ),
    }


@router.put("")
async def update_settings(body: SettingsBody):
    st = get_state()
    for field in ("api_base", "model"):
        val = getattr(body, field)
        if val is not None:
            st.update_setting(field, val)
    if body.api_key is not None:
        st.update_setting("api_key", body.api_key)
    reset_llm()
    await manager.broadcast({"type": "state_changed", "scope": "settings"})
    return {"ok": True}
