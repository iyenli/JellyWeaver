"""FastAPI application factory."""

import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from jelly_weaver.api.ws import manager


def create_app() -> FastAPI:
    app = FastAPI(title="Jelly Weaver", version="0.1.0")

    # CORS for dev (Vite dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from jelly_weaver.api.routes import (
        sources, targets, entries, settings, fs, operations,
    )
    app.include_router(sources.router)
    app.include_router(targets.router)
    app.include_router(entries.router)
    app.include_router(settings.router)
    app.include_router(fs.router)
    app.include_router(operations.router)

    # WebSocket endpoint
    @app.websocket("/api/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)

    # Serve frontend static files (production build)
    if getattr(sys, "frozen", False):
        static_dir = Path(sys._MEIPASS) / "jelly_weaver" / "static"
    else:
        static_dir = Path(__file__).parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True))

    return app
