"""Create the desktop shortcut via the Windows Script Host COM object.

PowerShell is used because it is present on every supported Windows version;
this keeps the application free of third-party dependencies (no pywin32).
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
from pathlib import Path

from .branding import APP_NAME
from .paths import app_dir, asset_dir, is_frozen

_LOGGER = logging.getLogger(__name__)

SHORTCUT_NAME = APP_NAME
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ShortcutError(RuntimeError):
    """Raised when the desktop shortcut cannot be created."""


def desktop_dir() -> Path:
    """Return the user's Desktop, following OneDrive redirection."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "Desktop")
            if isinstance(value, str) and value:
                candidate = Path(os.path.expandvars(value))
                if candidate.is_dir():
                    return candidate
        except OSError:
            pass
    return Path.home() / "Desktop"


def launch_command() -> tuple[Path, str, Path]:
    """Return ``(executable, arguments, working_directory)`` for the shortcut."""
    if is_frozen():
        executable = Path(sys.executable).resolve()
        return executable, "", executable.parent

    script = app_dir() / "switcher.py"
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.is_file():
        executable = pythonw
    return executable, f'"{script}"', app_dir()


def asset_icon() -> Path | None:
    icon = asset_dir() / "switcher.ico"
    return icon if icon.is_file() else None


def start_menu_dir() -> Path:
    """All-users Start Menu folder that holds the application shortcut."""
    program_data = os.environ.get("PROGRAMDATA")
    base = Path(program_data) if program_data else Path("C:/ProgramData")
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def is_admin() -> bool:
    """Return ``True`` when the process already has administrator rights."""
    if sys.platform != "win32":
        return False
    import ctypes

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin(extra_args: list[str] | None = None) -> bool:
    """Start an elevated copy of the app through the Windows UAC prompt.

    Returns ``True`` when Windows accepted the request; the caller is expected
    to close the current window afterwards. Refusing the prompt returns
    ``False`` instead of raising.
    """
    if sys.platform != "win32":
        return False

    executable, parameters, workdir = _elevation_request(extra_args)

    import ctypes

    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(executable), parameters, str(workdir), 1
    )
    return int(result) > 32


def _elevation_request(
    extra_args: list[str] | None = None,
) -> tuple[Path, str, Path]:
    """Return ``(executable, parameters, workdir)`` for an elevated relaunch."""
    executable, arguments, workdir = launch_command()
    parts = [arguments] if arguments else []
    if extra_args:
        parts.append(subprocess.list2cmdline(list(extra_args)))
    return executable, " ".join(parts), workdir


def create_shortcut(
    link: Path,
    executable: Path,
    *,
    arguments: str = "",
    workdir: Path | None = None,
    icon: Path | None = None,
    description: str | None = None,
) -> Path:
    """Create or replace a ``.lnk`` that runs *executable*."""
    if sys.platform != "win32":
        raise ShortcutError("Desktop shortcuts are only supported on Windows.")

    link = Path(link)
    target = Path(executable)
    script = _build_script(
        link,
        target,
        arguments,
        Path(workdir) if workdir is not None else target.parent,
        icon or target,
        description or link.stem,
    )
    link.parent.mkdir(parents=True, exist_ok=True)
    _run_powershell(script)
    if not link.exists():
        raise ShortcutError(f"PowerShell did not create {link}.")
    _LOGGER.info("Shortcut ready at %s", link)
    return link


def ensure_desktop_shortcut(*, force: bool = False, name: str = SHORTCUT_NAME) -> Path:
    """Create the shortcut if it is missing, or always when ``force`` is set."""
    if sys.platform != "win32":
        raise ShortcutError("Desktop shortcuts are only supported on Windows.")

    target = desktop_dir() / f"{name}.lnk"
    if target.exists() and not force:
        return target

    executable, arguments, workdir = launch_command()
    return create_shortcut(
        target,
        executable,
        arguments=arguments,
        workdir=workdir,
        icon=asset_icon() or executable,
        description=name,
    )


def _quote(value: str | Path) -> str:
    """Quote a value for a PowerShell single-quoted string."""
    return "'" + str(value).replace("'", "''") + "'"


def _build_script(
    link: Path,
    executable: Path,
    arguments: str,
    workdir: Path,
    icon: Path,
    description: str,
) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({_quote(link)})",
            f"$shortcut.TargetPath = {_quote(executable)}",
            f"$shortcut.Arguments = {_quote(arguments)}",
            f"$shortcut.WorkingDirectory = {_quote(workdir)}",
            f"$shortcut.IconLocation = {_quote(str(icon) + ',0')}",
            f"$shortcut.Description = {_quote(description)}",
            "$shortcut.Save()",
            f"Write-Output {_quote(link)}",
        ]
    )


def _run_powershell(script: str, timeout: float = 25.0) -> str:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ShortcutError(f"Could not start PowerShell: {exc}") from exc

    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip() or "unknown error"
        raise ShortcutError(f"PowerShell failed: {message}")
    return completed.stdout.decode("utf-8", "replace").strip()
