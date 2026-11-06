# -*- mode: python ; coding: utf-8 -*-
# Build on Windows: pyinstaller --noconfirm yaformcreator.spec
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'app.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=["form_preview"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='YaFormCreator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)