#!/usr/bin/env python3
"""Switcher - application entry point."""

from __future__ import annotations

import argparse
import ctypes
import logging
import logging.handlers
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from brickvpn import __version__, paths
from brickvpn.branding import APP_NAME
from brickvpn.ui import BranchSelectorApp

LOGGER = logging.getLogger("switcher")


def _env_flag(name: str, legacy: str | None = None) -> bool:
    """Read a boolean environment flag, accepting a legacy name."""
    if os.environ.get(name) == "1":
        return True
    return bool(legacy and os.environ.get(legacy) == "1")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="switcher.py",
        description="Switch the hotel software's settings.ini to another branch server.",
    )
    parser.add_argument(
        "--settings",
        help="Path to settings.ini (default: the file next to the application).",
    )
    parser.add_argument(
        "--branches",
        help="Path to branches.json (default: the file next to the application).",
    )
    parser.add_argument(
        "--no-shortcut",
        action="store_true",
        help="Do not create the desktop shortcut automatically.",
    )
    parser.add_argument(
        "--license",
        help="Path to license.json (default: the file next to the application).",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser.parse_args(argv)


def setup_logging() -> None:
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    try:
        folder = paths.log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                folder / "switcher.log",
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
    except OSError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers or [logging.NullHandler()],
    )


def enable_dpi_awareness() -> None:
    """Ask Windows for crisp text on high-DPI displays."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def apply_tk_scaling(root: tk.Tk) -> None:
    if sys.platform != "win32":
        return
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except (AttributeError, OSError, tk.TclError):
        pass


def install_excepthook() -> None:
    def hook(exc_type, exc, traceback) -> None:
        LOGGER.critical("Unhandled error", exc_info=(exc_type, exc, traceback))
        try:
            messagebox.showerror(
                APP_NAME,
                f"An unexpected error occurred:\n\n{exc}\n\nSee the log for details.",
            )
        except tk.TclError:
            pass

    sys.excepthook = hook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()
    enable_dpi_awareness()
    install_excepthook()

    state = paths.load_state()
    settings_path = paths.resolve_settings_path(args.settings, state)
    if args.settings and settings_path is None:
        LOGGER.warning("Requested settings file %s was not found", args.settings)

    branches_path = (
        Path(args.branches).expanduser().resolve()
        if args.branches
        else paths.default_branches_path()
    )

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        LOGGER.critical("Could not start the UI: %s", exc)
        return 1

    apply_tk_scaling(root)
    LOGGER.info(
        "Starting %s %s (settings=%s, branches=%s)",
        APP_NAME,
        __version__,
        settings_path or "not found",
        branches_path,
    )

    BranchSelectorApp(
        root,
        settings_path=settings_path,
        branches_path=branches_path,
        auto_shortcut=not args.no_shortcut
        and not _env_flag("SWITCHER_NO_SHORTCUT", "BRICKVPN_NO_SHORTCUT"),
        license_path=(
            Path(args.license).expanduser().resolve() if args.license else None
        ),
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
