# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the BrickVPN branch selector.

Only the application code is bundled. ``branches.json`` and ``settings.ini``
stay next to the executable so staff can edit them without rebuilding.

The exe requests administrator rights because hotel deployments commonly put
``settings.ini`` in a protected folder such as ``C:\\hotel``.
"""

from pathlib import Path

icon_file = Path(SPECPATH) / "assets" / "brickvpn.ico"
icon = str(icon_file) if icon_file.is_file() else None

a = Analysis(
    ["switcher.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="BrickVPN Branch Selector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    uac_admin=True,
)
