"""Jelly Weaver entry point — starts the web server."""

import argparse
import logging
import threading
import webbrowser

import uvicorn

from jelly_weaver.api.app import create_app


def main():
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

    uvicorn.run(
        create_app,
        factory=True,
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
