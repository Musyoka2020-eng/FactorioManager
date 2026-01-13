# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['factorio_mod_manager\\main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'bs4', 'lxml', 'requests', 'dotenv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['selenium', 'playwright', 'greenlet'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FactorioModManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
