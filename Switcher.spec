# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Switcher.

Only the application code is bundled. ``branches.json`` and ``settings.ini``
stay next to the executable so staff can edit them without rebuilding.

The exe requests administrator rights because hotel deployments commonly put
``settings.ini`` in a protected folder such as ``C:\\hotel``.
"""

from pathlib import Path

icon_file = Path(SPECPATH) / "assets" / "switcher.ico"
icon = str(icon_file) if icon_file.is_file() else None
version_file = Path(SPECPATH) / "version_info.txt"

# Window icon and header mark travel inside the exe, so a lone Switcher.exe in
# C:\hotel still looks right. The hotel's branches.json/license.json stay beside
# the exe and are never bundled.
datas = [
    (str(icon_file), "assets"),
    (str(Path(SPECPATH) / "assets" / "logo_mark.png"), "assets"),
]

a = Analysis(
    ["switcher.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
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
    name="Switcher",
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
    version=str(version_file),
    uac_admin=True,
)
