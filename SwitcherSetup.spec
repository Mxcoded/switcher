# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the Switcher installer (``SwitcherSetup.exe``).

Build ``Switcher.exe`` first. The payload is bundled inside the setup program:
the application, the branch catalogue and the site licence. The installer
copies them into ``C:\\hotel`` and never writes ``settings.ini``.

The setup requests administrator rights up front because it writes to
``C:\\hotel`` and to the machine-wide uninstall registry key.
"""

from pathlib import Path

root = Path(SPECPATH)
payload_exe = root / "dist" / "Switcher.exe"
if not payload_exe.is_file():
    raise SystemExit("Build dist\\Switcher.exe before packaging the installer.")

icon_file = root / "assets" / "switcher.ico"
icon = str(icon_file) if icon_file.is_file() else None
version_file = root / "version_info_setup.txt"

datas = [
    (str(payload_exe), "payload"),
    (str(root / "branches.json"), "payload"),
    (str(root / "license.json"), "payload"),
    (str(icon_file), "assets"),
    (str(root / "assets" / "logo_mark.png"), "assets"),
]

a = Analysis(
    ["switcher_setup.py"],
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
    name="SwitcherSetup",
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
