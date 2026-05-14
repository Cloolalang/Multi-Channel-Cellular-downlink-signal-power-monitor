"""
Desktop / PyInstaller entry: run Uvicorn without --reload.

Build (from `dashboard/`):  pyinstaller pyinstaller.spec
Release folder: copy repo `flows.json` next to the `.exe`. Bands visualiser assets are embedded in the exe when built from a repo tree that includes `lte-visualizer/`; optional sidecar `lte-visualizer/` next to the exe overrides embedded files.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path


def main() -> None:
    import uvicorn

    # Import ASGI app object here so PyInstaller traces `app.*`; string refs like "app.main:app"
    # fail at runtime in one-file builds because `app` is not on PYTHONPATH as a plain package.
    from app.main import app as fastapi_app

    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)
    multiprocessing.freeze_support()
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        factory=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
