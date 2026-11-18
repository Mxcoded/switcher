"""Switcher setup program.

Installs ``Switcher.exe`` and the site defaults into ``C:\\hotel`` while leaving
the hotel's ``settings.ini`` and any existing site data untouched. Ships as
``SwitcherSetup.exe`` and also handles ``--uninstall`` for Add/Remove Programs.

Usage::

    SwitcherSetup.exe                 # graphical installer
    SwitcherSetup.exe --silent        # unattended install (keeps site data)
    SwitcherSetup.exe --uninstall     # remove the program, keep site data
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

if __package__ in (None, ""):  # running switcher_setup.py directly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brickvpn import __version__, paths, theme
from brickvpn.branding import APP_NAME, COMPANY, DEVELOPER
from brickvpn.shortcut import asset_icon, is_admin
from installer import core

LOGGER = logging.getLogger("switcher_setup")


def setup_logging() -> None:
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    try:
        folder = paths.log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                folder / "installer.log",
                maxBytes=500_000,
                backupCount=2,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="SwitcherSetup", add_help=True)
    parser.add_argument(
        "--silent", action="store_true", help="Install without showing a window."
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="Remove the installed program."
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} Setup {__version__}"
    )
    return parser.parse_args(argv)


def _relaunch_elevated(argv: list[str]) -> bool:
    """Ask Windows for an elevated copy; return True when it was started."""
    if sys.platform != "win32":
        return False
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        parameters = subprocess.list2cmdline(list(argv))
    else:
        executable = Path(sys.executable)
        script = Path(__file__).resolve().parent / "setup.py"
        parameters = subprocess.list2cmdline([str(script), *argv])

    import ctypes

    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(executable), parameters, None, 1
    )
    return int(result) > 32


def _require_frozen() -> None:
    """Refuse to install from a source checkout (would copy python.exe)."""
    if not getattr(sys, "frozen", False):
        raise core.InstallerError(
            "Run the installer as SwitcherSetup.exe; a source checkout cannot "
            "register an uninstaller."
        )


def _silent_install() -> int:
    _require_frozen()
    plan = core.build_plan(core.payload_dir(), core.DEPLOYMENT_DIR)
    copied = core.apply_plan(plan)
    uninstaller = core.copy_uninstaller(Path(sys.executable), core.DEPLOYMENT_DIR)
    core.create_shortcuts(plan.executable)
    core.register_uninstall(core.DEPLOYMENT_DIR, uninstaller)
    LOGGER.info("Installed %s files into %s", len(copied), core.DEPLOYMENT_DIR)
    return 0


def _run_uninstall(quiet: bool) -> int:
    removed = core.uninstall(core.DEPLOYMENT_DIR)
    LOGGER.info("Uninstalled; removed %s entries", len(removed))
    if not quiet:
        messagebox.showinfo(
            f"{APP_NAME} Setup",
            f"{APP_NAME} was removed from this workstation.\n\n"
            "settings.ini, branches.json, license.json and the settings "
            "backups were kept.",
        )
    return 0


class SetupApp:
    """Graphical installer window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.source = core.payload_dir()
        self.target = core.DEPLOYMENT_DIR
        self.busy = False
        self._tasks: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self._logo: tk.PhotoImage | None = None

        self.replace_license = tk.BooleanVar(value=False)
        self.replace_branches = tk.BooleanVar(value=False)
        self.make_shortcuts = tk.BooleanVar(value=True)
        self.launch_after = tk.BooleanVar(value=True)

        self._build()
        self.root.after(120, self._poll)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.root.title(f"{APP_NAME} Setup")
        self.root.resizable(False, False)
        icon = asset_icon()
        if icon is not None:
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                LOGGER.warning("Could not apply the setup icon", exc_info=True)

        theme.install(self.root)
        self.root.geometry("660x585")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._build_header()
        body = tk.Frame(self.root, bg=theme.BG, padx=22, pady=18)
        body.pack(fill="both", expand=True)
        self._build_destination(body)
        self._build_licence(body)
        self._build_options(body)
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=theme.NAVY, padx=24, pady=18)
        header.pack(fill="x")
        logo_path = paths.asset_dir() / "logo_mark.png"
        if logo_path.is_file():
            try:
                self._logo = tk.PhotoImage(file=str(logo_path))
            except tk.TclError:
                self._logo = None
        if self._logo is not None:
            tk.Label(header, image=self._logo, bg=theme.NAVY).pack(
                side="left", padx=(0, 14)
            )

        text = tk.Frame(header, bg=theme.NAVY)
        text.pack(side="left", anchor="w")
        tk.Label(
            text,
            text=f"{APP_NAME} Setup",
            bg=theme.NAVY,
            fg="#ffffff",
            font=theme.FONT_TITLE,
        ).pack(anchor="w")
        tk.Label(
            text,
            text=f"Version {__version__} - {COMPANY}, developed by {DEVELOPER}",
            bg=theme.NAVY,
            fg="#b9c6dd",
            font=theme.FONT_SMALL,
        ).pack(anchor="w", pady=(3, 0))

        tk.Frame(self.root, bg=theme.ACCENT, height=3).pack(fill="x")

    def _build_destination(self, parent: tk.Frame) -> None:
        card = theme.card(parent)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=theme.CARD, padx=16, pady=14)
        inner.pack(fill="x")

        tk.Label(
            inner,
            text="INSTALL FOLDER",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).pack(anchor="w")

        installed = (self.target / "Switcher.exe").is_file()
        settings_exists = (self.target / "settings.ini").is_file()
        tk.Label(
            inner,
            text=str(self.target),
            bg=theme.CARD,
            fg=theme.INK,
            font=theme.FONT_VALUE,
        ).pack(anchor="w", pady=(4, 2))
        if installed:
            note = (
                "Switcher is already installed here. The exe will be replaced; "
                "your settings.ini, branches and licence are kept."
            )
        elif settings_exists:
            note = (
                "The hotel software's settings.ini lives here. "
                "It is never modified."
            )
        else:
            note = (
                "No settings.ini was found in this folder yet. Switcher looks "
                "for C:\\hotel\\settings.ini when it starts; the hotel software "
                "can be installed before or after Switcher."
            )
        tk.Label(
            inner,
            text=note,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            wraplength=570,
            justify="left",
        ).pack(anchor="w")

    def _build_licence(self, parent: tk.Frame) -> None:
        card = theme.card(parent)
        card.pack(fill="x", pady=(12, 0))
        inner = tk.Frame(card, bg=theme.CARD, padx=16, pady=14)
        inner.pack(fill="x")
        tk.Label(
            inner,
            text="SITE LICENCE",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).pack(anchor="w")
        tk.Label(
            inner,
            text=core.license_summary(self.source / "license.json"),
            bg=theme.CARD,
            fg=theme.INK,
            font=theme.FONT,
            wraplength=570,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _build_options(self, parent: tk.Frame) -> None:
        card = theme.card(parent)
        card.pack(fill="x", pady=(12, 0))
        inner = tk.Frame(card, bg=theme.CARD, padx=16, pady=12)
        inner.pack(fill="x")

        tk.Label(
            inner,
            text="OPTIONS",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).pack(anchor="w", pady=(0, 4))

        licence_exists = (self.target / "license.json").is_file()
        branches_exists = (self.target / "branches.json").is_file()

        ttk.Checkbutton(
            inner,
            text="Replace the existing branches.json",
            variable=self.replace_branches,
            state="normal" if branches_exists else "disabled",
        ).pack(anchor="w", pady=1)
        ttk.Checkbutton(
            inner,
            text="Replace the existing licence.json",
            variable=self.replace_license,
            state="normal" if licence_exists else "disabled",
        ).pack(anchor="w", pady=1)
        ttk.Checkbutton(
            inner,
            text="Create Desktop and Start menu shortcuts for all users",
            variable=self.make_shortcuts,
        ).pack(anchor="w", pady=1)
        ttk.Checkbutton(
            inner,
            text=f"Open {APP_NAME} when the installation finishes",
            variable=self.launch_after,
        ).pack(anchor="w", pady=1)

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=theme.CARD, padx=22, pady=14)
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=theme.BORDER, height=1).pack(fill="x", pady=(0, 12))

        row = tk.Frame(footer, bg=theme.CARD)
        row.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready to install.")
        tk.Label(
            row,
            textvariable=self.status_var,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            wraplength=380,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Exit", command=self._close).pack(side="right")
        self.install_btn = ttk.Button(
            row,
            text="Install",
            style="Accent.TButton",
            command=self._install,
        )
        self.install_btn.pack(side="right", padx=(0, 8))

        self.progress = ttk.Progressbar(
            footer, mode="determinate", maximum=100, length=615
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _install(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.install_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.progress.pack(fill="x", pady=(12, 0))
        self.status_var.set("Preparing...")

        replace_license = bool(self.replace_license.get())
        replace_branches = bool(self.replace_branches.get())
        shortcuts = bool(self.make_shortcuts.get())
        threading.Thread(
            target=self._worker,
            args=(replace_license, replace_branches, shortcuts),
            name="switcher-setup",
            daemon=True,
        ).start()

    def _worker(
        self, replace_license: bool, replace_branches: bool, shortcuts: bool
    ) -> None:
        try:
            _require_frozen()
            self._post(0.05, "Checking the setup package...")
            plan = core.build_plan(
                self.source,
                self.target,
                replace_license=replace_license,
                replace_branches=replace_branches,
            )
            self._post(0.20, f"Installing into {self.target}...")
            copied = core.apply_plan(plan)

            self._post(0.55, "Preparing the uninstaller...")
            uninstaller = core.copy_uninstaller(Path(sys.executable), self.target)

            created: list[Path] = []
            if shortcuts:
                self._post(0.70, "Creating shortcuts...")
                created = core.create_shortcuts(plan.executable)

            self._post(0.90, "Registering the installation...")
            core.register_uninstall(self.target, uninstaller)
            self._tasks.put(("done", (plan, copied, created)))
        except Exception as exc:  # noqa: BLE001 - shown in the window
            LOGGER.exception("Installation failed")
            self._tasks.put(("done", exc))

    def _on_done(self, result: Any) -> None:
        self.busy = False
        self.progress.configure(value=100)
        if isinstance(result, Exception):
            self.install_btn.configure(state="normal")
            self.status_var.set("Installation failed.")
            messagebox.showerror(
                f"{APP_NAME} Setup",
                f"The installation could not be completed:\n\n{result}",
            )
            return

        plan, copied, created = result
        kept = ", ".join(plan.keep) if plan.keep else "none"
        LOGGER.info("Installed %s files into %s; kept %s", len(copied), self.target, kept)
        self.status_var.set(f"{APP_NAME} {__version__} is installed in {self.target}.")
        self.install_btn.configure(text="Close", command=self._close)

        lines = [f"{APP_NAME} {__version__} is now installed in {self.target}."]
        if plan.keep:
            lines.append("Existing files kept: " + ", ".join(plan.keep) + ".")
        lines.append("The hotel software's settings.ini was not modified.")
        if created:
            lines.append(f"{len(created)} shortcut(s) created.")

        if self.launch_after.get():
            executable = self.target / "Switcher.exe"
            try:
                subprocess.Popen([str(executable)], cwd=str(self.target))
            except OSError as exc:
                messagebox.showwarning(
                    f"{APP_NAME} Setup",
                    f"{APP_NAME} was installed, but it could not be started:\n\n{exc}",
                )
                return
            messagebox.showinfo(f"{APP_NAME} Setup", "\n\n".join(lines))
            self.root.after(150, self.root.destroy)
            return
        messagebox.showinfo(f"{APP_NAME} Setup", "\n\n".join(lines))

    def _close(self) -> None:
        if self.busy:
            if not messagebox.askyesno(
                f"{APP_NAME} Setup",
                "The installation is still running. Close anyway?",
            ):
                return
        self.root.destroy()

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------

    def _post(self, fraction: float, message: str) -> None:
        self._tasks.put(("progress", (fraction, message)))

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._tasks.get_nowait()
                if kind == "progress":
                    fraction, message = payload
                    self.progress.configure(value=int(round(fraction * 100)))
                    self.status_var.set(message)
                elif kind == "done":
                    self._on_done(payload)
        except queue.Empty:
            pass
        try:
            self.root.after(120, self._poll)
        except tk.TclError:
            pass


def _confirm_uninstall() -> bool:
    return messagebox.askyesno(
        f"{APP_NAME} Setup",
        f"Remove {APP_NAME} from this workstation?\n\n"
        "settings.ini, branches.json, license.json and the settings backups "
        "are kept.",
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(arguments)
    setup_logging()

    if sys.platform != "win32":
        LOGGER.error("The installer only runs on Windows.")
        return 1

    if not is_admin():
        if _relaunch_elevated(arguments):
            return 0
        messagebox.showerror(
            f"{APP_NAME} Setup",
            "Administrator rights are required to install into "
            f"{core.DEPLOYMENT_DIR}.\n\n"
            "Right-click SwitcherSetup.exe and choose Run as administrator.",
        )
        return 1

    try:
        if args.uninstall:
            if not args.silent and not _confirm_uninstall():
                return 0
            return _run_uninstall(args.silent)
        if args.silent:
            return _silent_install()

        root = tk.Tk()
        SetupApp(root)
        root.mainloop()
        return 0
    except core.InstallerError as exc:
        LOGGER.error("Installer error: %s", exc)
        if not args.silent:
            messagebox.showerror(f"{APP_NAME} Setup", str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - last resort dialog
        LOGGER.exception("Unexpected installer error")
        if not args.silent:
            messagebox.showerror(
                f"{APP_NAME} Setup", f"An unexpected error occurred:\n\n{exc}"
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
