"""Jelly Weaver entry point — starts the web server."""

import argparse
import logging
import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path


def _redirect_streams_to_log() -> None:
    """When running as a no-console frozen EXE, sys.stdout/stderr are None.
    Redirect them to a log file so uvicorn's formatter doesn't crash on .isatty().
    """
    log_path = Path(tempfile.gettempdir()) / "jellyweaver.log"
    f = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = f
    sys.stderr = f


def _make_tray_icon(port: int) -> None:
    """Run a system tray icon in a background thread (Windows/macOS/Linux)."""
    try:
        import pystray
        from PIL import Image as PILImage

        # Reuse the app icon if available (frozen bundle), else generate a tiny one
        icon_path = Path(sys._MEIPASS) / "icon.ico" if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent / "icon.ico"
        if icon_path.is_file():
            img = PILImage.open(icon_path).resize((64, 64))
        else:
            # Minimal fallback icon
            img = PILImage.new("RGBA", (64, 64), (18, 22, 38, 255))

        def on_open(_icon, _item):
            webbrowser.open(f"http://localhost:{port}")

        def on_quit(icon, _item):
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("打开 JellyWeaver", on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit),
        )
        icon = pystray.Icon("JellyWeaver", img, "JellyWeaver", menu)
        icon.run()
    except Exception as e:
        logging.getLogger(__name__).warning("Tray icon failed: %s", e)


def main():
    if getattr(sys, "frozen", False) and sys.stdout is None:
        _redirect_streams_to_log()

    parser = argparse.ArgumentParser(description="Jelly Weaver")
    parser.add_argument("--port", type=int, default=9470)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(f"http://localhost:{args.port}",)).start()

    # Start tray icon in background thread (only when running as frozen EXE)
    if getattr(sys, "frozen", False):
        tray_thread = threading.Thread(target=_make_tray_icon, args=(args.port,), daemon=True)
        tray_thread.start()

    import uvicorn
    from jelly_weaver.api.app import create_app

    uvicorn.run(
        create_app,
        factory=True,
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
