"""Resolve filesystem roots for dev vs PyInstaller-frozen runs."""
from __future__ import annotations

import sys
from pathlib import Path


def _frozen() -> bool:
    return getattr(sys, "frozen", False)


def package_dir() -> Path:
    """`dashboard/app/` — templates, static, Python modules (inside one-file bundle when frozen)."""
    return Path(__file__).resolve().parent


def deployment_root() -> Path:
    """
    Directory that holds `flows.json` and optional `lte-visualizer/` (repo root from source;
    folder containing the `.exe` when frozen).
    """
    if _frozen():
        return Path(sys.executable).resolve().parent
    return package_dir().parent.parent


def dashboard_state_dir() -> Path:
    """Writable folder for `dashboard_config.json` (`dashboard/` from source; exe dir when frozen)."""
    if _frozen():
        return Path(sys.executable).resolve().parent
    return package_dir().parent


def lte_visualizer_dir() -> Path | None:
    """
    Static LTE band HTML/JS next to `flows.json`, or embedded under PyInstaller `_MEIPASS/lte-visualizer`.
    Sidecar folder wins when present so installs can override bundled assets.
    """
    sidecar = deployment_root() / "lte-visualizer"
    if sidecar.is_dir():
        return sidecar
    if _frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / "lte-visualizer"
            if bundled.is_dir():
                return bundled
    return None
