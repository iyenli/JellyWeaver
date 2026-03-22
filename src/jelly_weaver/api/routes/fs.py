"""Filesystem browsing routes (replaces native file dialogs)."""

import platform
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/fs", tags=["filesystem"])


@router.get("/roots")
def list_roots():
    """Return platform root directories."""
    system = platform.system()
    if system == "Windows":
        import string
        roots = [
            f"{d}:\\" for d in string.ascii_uppercase
            if Path(f"{d}:\\").exists()
        ]
    else:
        roots = ["/"]
    home = str(Path.home())
    return {"roots": roots, "home": home}


@router.get("/list")
def list_dir(path: str):
    p = Path(path)
    if not p.is_dir():
        raise HTTPException(400, f"Not a directory: {path}")
    items = []
    try:
        for child in sorted(p.iterdir()):
            if child.name.startswith("."):
                continue
            items.append({
                "name": child.name,
                "path": str(child),
                "is_dir": child.is_dir(),
            })
    except PermissionError:
        raise HTTPException(403, f"Permission denied: {path}")
    return {"path": str(p), "parent": str(p.parent), "items": items}
