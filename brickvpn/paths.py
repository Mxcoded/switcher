"""Application paths and small pieces of persisted state.

The app is deliberately portable: ``branches.json``, ``settings.ini`` and the
executable live together in one folder. Per-user state (last branch, custom
settings path, shortcut path) is kept in ``%LOCALAPPDATA%\\BrickVPN`` so the
application folder can be read-only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

APP_NAME = "BrickVPN"
STATE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


def is_frozen() -> bool:
    """Return True when running from a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder containing the executable (frozen) or the project root (source)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def state_file() -> Path:
    return state_dir() / "state.json"


def log_dir() -> Path:
    return state_dir() / "logs"


def load_state() -> dict[str, Any]:
    """Read persisted state, returning an empty dict when absent or corrupt."""
    try:
        data = json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("version") != STATE_VERSION:
        # Unknown/newer state: keep the last-branch hint if it is usable.
        return {k: v for k, v in data.items() if k in {"last_branch", "settings_path", "shortcut_path"}}
    return data


def save_state(state: dict[str, Any]) -> None:
    """Atomically persist state. Failures are logged, never raised."""
    payload = dict(state)
    payload["version"] = STATE_VERSION
    target = state_file()
    tmp_path: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=".state-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, target)
        tmp_path = None
    except OSError:
        _LOGGER.warning("Could not save state to %s", target, exc_info=True)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def default_settings_path() -> Path:
    return app_dir() / "settings.ini"


def default_branches_path() -> Path:
    return app_dir() / "branches.json"


def resolve_settings_path(cli_value: str | None, state: dict[str, Any]) -> Path | None:
    """Pick the settings file to edit.

    Order: explicit command-line value, the folder next to the app, a previously
    located file, then the current working directory. Put the app folder first
    so moving the whole deployment folder never edits a stale copy elsewhere.
    Returns ``None`` when no candidate exists.
    """
    candidates: list[Path] = []
    if cli_value:
        candidates.append(Path(cli_value).expanduser())
    candidates.append(default_settings_path())
    stored = state.get("settings_path")
    if isinstance(stored, str) and stored:
        candidates.append(Path(stored).expanduser())
    candidates.append(Path.cwd() / "settings.ini")

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None
