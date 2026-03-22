"""Settings routes."""

import platform
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel

from jelly_weaver.api.deps import get_llm, get_state, reset_llm
from jelly_weaver.api.ws import manager
from jelly_weaver.core.state import LLM_SETTINGS_FILE, STATE_DIR, STATE_FILE

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsBody(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


@router.get("")
async def get_settings():
    st = get_state()
    settings = st.load_llm_settings()
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
        "state_file_path": str(STATE_FILE),
        "state_file_exists": STATE_FILE.exists(),
        "llm_settings_file_path": str(LLM_SETTINGS_FILE),
    }


@router.put("")
async def update_settings(body: SettingsBody):
    st = get_state()
    for field in ("api_base", "model"):
        val = getattr(body, field)
        if val is not None:
            st.update_llm_setting(field, val)
    if body.api_key is not None:
        st.update_llm_setting("api_key", body.api_key)
    reset_llm()
    await manager.broadcast({"type": "state_changed", "scope": "settings"})
    return {"ok": True}


@router.post("/open-state-dir")
async def open_state_dir():
    """Open the state directory in the OS file manager."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = str(STATE_DIR)
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["explorer", target])
        elif system == "Darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except OSError:
        pass
    return {"ok": True}


@router.post("/llm-check")
async def llm_check():
    """Test LLM connectivity with a minimal real API call."""
    import asyncio
    client = get_llm()
    if client is None:
        return {"configured": False, "ok": False, "error": "API key not configured"}

    try:
        result = await asyncio.to_thread(client.health_check)
        if result:
            return {"configured": True, "ok": True, "error": None}
        else:
            return {"configured": True, "ok": False, "error": "Health check failed"}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}
