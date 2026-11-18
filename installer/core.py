"""Install and uninstall logic for the Switcher setup program.

The setup program is a small Tk application built with PyInstaller. It carries
``Switcher.exe`` and the site defaults inside itself, copies them into
``C:\\hotel``, and never touches the hotel's ``settings.ini``.

This module holds the parts worth testing: planning which files to copy,
creating backups of replaced files, shortcuts and the uninstall registry entry.
It is importable on non-Windows systems; the Windows-only steps fail with a
clear ``InstallerError`` instead of an ``ImportError``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from brickvpn import __version__
from brickvpn.branding import APP_NAME, COMPANY, DEVELOPER
from brickvpn.paths import DEPLOYMENT_DIR

LOGGER = logging.getLogger(__name__)

PAYLOAD_FILES = ("Switcher.exe", "branches.json", "license.json")
REQUIRED_FILES = ("Switcher.exe",)
BACKUP_FOLDER = "installer-backups"
UNINSTALLER_NAME = "SwitcherSetup.exe"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class InstallerError(RuntimeError):
    """Raised when the installation cannot continue."""


@dataclass(frozen=True)
class InstallPlan:
    """Which payload files are copied, and which existing files are kept."""

    source_dir: Path
    target_dir: Path
    copy: tuple[str, ...]
    keep: tuple[str, ...]

    @property
    def executable(self) -> Path:
        return self.target_dir / "Switcher.exe"


def payload_dir() -> Path:
    """Folder holding the bundled payload.

    Frozen builds unpack it beside the setup code; source runs use ``dist`` when
    a build exists, so the installer can be tried without packaging.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle:
        return Path(bundle) / "payload"

    root = Path(__file__).resolve().parent.parent
    dist = root / "dist"
    return dist if (dist / "Switcher.exe").is_file() else root


def build_plan(
    source_dir: Path,
    target_dir: Path = DEPLOYMENT_DIR,
    *,
    replace_license: bool = False,
    replace_branches: bool = False,
) -> InstallPlan:
    """Decide what to copy without changing anything on disk.

    Existing site data wins by default: ``license.json`` and ``branches.json``
    are kept so a reinstall cannot roll back a renewal or a branch edit. The
    executable is always replaced.
    """
    source = Path(source_dir)
    target = Path(target_dir)
    for name in REQUIRED_FILES:
        if not (source / name).is_file():
            raise InstallerError(f"{source / name} was not found in the setup package.")

    copy: list[str] = []
    keep: list[str] = []
    for name in PAYLOAD_FILES:
        if not (source / name).is_file():
            if name in REQUIRED_FILES:
                raise InstallerError(f"The setup package is missing {name}.")
            continue
        if (target / name).exists():
            if name == "license.json" and not replace_license:
                keep.append(name)
                continue
            if name == "branches.json" and not replace_branches:
                keep.append(name)
                continue
        copy.append(name)

    return InstallPlan(source, target, tuple(copy), tuple(keep))


def _backup(target: Path, stamp: str) -> Path:
    folder = target.parent / BACKUP_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{target.stem}-{stamp}{target.suffix}"
    counter = 1
    while candidate.exists():
        candidate = folder / f"{target.stem}-{stamp}-{counter}{target.suffix}"
        counter += 1
    shutil.copy2(target, candidate)
    return candidate


def apply_plan(plan: InstallPlan, *, stamp: str | None = None) -> list[Path]:
    """Copy the planned files, backing up anything that is replaced."""
    plan.target_dir.mkdir(parents=True, exist_ok=True)
    moment = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    copied: list[Path] = []
    for name in plan.copy:
        source = plan.source_dir / name
        target = plan.target_dir / name
        if target.exists():
            backup = _backup(target, moment)
            LOGGER.info("Backed up %s to %s", target, backup)
        shutil.copy2(source, target)
        copied.append(target)
        LOGGER.info("Installed %s", target)
    return copied


def copy_uninstaller(executable: Path, target_dir: Path = DEPLOYMENT_DIR) -> Path:
    """Keep a copy of the setup program for the uninstall entry."""
    target = Path(target_dir) / UNINSTALLER_NAME
    source = Path(executable)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def public_desktop_dir() -> Path:
    public = os.environ.get("PUBLIC")
    base = Path(public) if public else Path("C:/Users/Public")
    return base / "Desktop"


def create_shortcuts(
    executable: Path,
    *,
    desktop: bool = True,
    start_menu: bool = True,
) -> list[Path]:
    """Create all-users shortcuts for the installed executable."""
    from brickvpn.shortcut import create_shortcut, start_menu_dir

    created: list[Path] = []
    if desktop:
        created.append(
            create_shortcut(
                public_desktop_dir() / f"{APP_NAME}.lnk",
                executable,
                workdir=Path(executable).parent,
                icon=Path(executable),
                description=APP_NAME,
            )
        )
    if start_menu:
        created.append(
            create_shortcut(
                start_menu_dir() / f"{APP_NAME}.lnk",
                executable,
                workdir=Path(executable).parent,
                icon=Path(executable),
                description=APP_NAME,
            )
        )
    return created


def register_uninstall(
    target_dir: Path = DEPLOYMENT_DIR,
    uninstaller: Path | None = None,
    *,
    version: str = __version__,
) -> None:
    """Write the Add/Remove Programs entry (machine-wide)."""
    if sys.platform != "win32":
        raise InstallerError("The uninstall entry is only created on Windows.")

    import winreg

    target = Path(target_dir)
    executable = target / "Switcher.exe"
    setup = Path(uninstaller) if uninstaller else target / UNINSTALLER_NAME
    size_kb = 0
    for path in (executable, setup):
        try:
            size_kb += path.stat().st_size // 1024
        except OSError:
            continue

    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, COMPANY)
        winreg.SetValueEx(
            key, "Comments", 0, winreg.REG_SZ, f"Developed by {DEVELOPER}."
        )
        winreg.SetValueEx(
            key, "DisplayIcon", 0, winreg.REG_SZ, f"{executable},0"
        )
        winreg.SetValueEx(
            key, "InstallLocation", 0, winreg.REG_SZ, str(target)
        )
        winreg.SetValueEx(
            key,
            "UninstallString",
            0,
            winreg.REG_SZ,
            f'"{setup}" --uninstall',
        )
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        if size_kb:
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
    LOGGER.info("Registered the uninstall entry for %s", target)


def remove_uninstall_entry() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
    except FileNotFoundError:
        return
    LOGGER.info("Removed the uninstall entry")


def _remove_link(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            LOGGER.info("Removed %s", path)
            return True
    except OSError:
        LOGGER.warning("Could not remove %s", path, exc_info=True)
    return False


def schedule_self_delete(path: Path) -> None:
    """Delete the running uninstaller once this process exits."""
    if sys.platform != "win32":
        path.unlink(missing_ok=True)
        return
    command = f'ping -n 3 127.0.0.1 >nul & del /f /q "{path}"'
    subprocess.Popen(
        ["cmd.exe", "/c", command],
        creationflags=_CREATE_NO_WINDOW,
        close_fds=True,
    )


def uninstall(target_dir: Path = DEPLOYMENT_DIR) -> list[str]:
    """Remove the program, shortcuts and registry entry; keep site data."""
    target = Path(target_dir)
    removed: list[str] = []

    from brickvpn.shortcut import start_menu_dir

    for link in (
        public_desktop_dir() / f"{APP_NAME}.lnk",
        start_menu_dir() / f"{APP_NAME}.lnk",
    ):
        if _remove_link(link):
            removed.append(str(link))

    executable = target / "Switcher.exe"
    if _remove_link(executable):
        removed.append(str(executable))

    remove_uninstall_entry()

    setup = target / UNINSTALLER_NAME
    running = Path(sys.executable).resolve() if getattr(sys, "frozen", False) else None
    if running is not None and running == setup.resolve():
        schedule_self_delete(setup)
    elif _remove_link(setup):
        removed.append(str(setup))

    return removed


def license_summary(path: Path) -> str:
    """One-line description of a licence file, for the setup window."""
    from brickvpn import licensing

    if not Path(path).is_file():
        return "No licence file in the package"
    try:
        license = licensing.load_license(path)
    except licensing.LicenseError as exc:
        return f"The licence file could not be verified: {exc}"
    return (
        f"{license.customer} - valid until "
        f"{license.expires.strftime('%d %b %Y')}"
    )
