# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the LTE downlink power dashboard (run from `dashboard/`)."""
from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

SPEC_DIR = Path(os.path.abspath(SPEC)).parent

datas = [
    (str(SPEC_DIR / "app" / "templates"), "app/templates"),
    (str(SPEC_DIR / "app" / "static"), "app/static"),
]
binaries: list = []
hiddenimports = [
    "serial",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

for pkg in ("uvicorn", "starlette", "anyio", "pydantic_settings", "websockets"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run_release.py"],
    pathex=[str(SPEC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LTE-Downlink-Power-Monitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
