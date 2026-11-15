"""Tkinter user interface for the BrickVPN branch selector."""

from __future__ import annotations

import logging
import os
import platform
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from . import __version__, paths, theme
from .branch_editor import BranchEditorDialog
from .branches import (
    DEFAULT_CHECK_PORTS,
    DEFAULT_PROBE_TIMEOUT,
    Branch,
    BranchCatalog,
    BranchesError,
    load_or_create,
)
from .netcheck import CheckOutcome, TwingateStatus, detect_twingate, probe
from .settings_file import SettingsAccessError, SettingsDocument, SettingsError
from .shortcut import (
    ShortcutError,
    asset_icon,
    ensure_desktop_shortcut,
    is_admin,
    launch_command,
    relaunch_as_admin,
)

_LOGGER = logging.getLogger(__name__)

COLOR_OK = theme.OK
COLOR_WARN = theme.WARN
COLOR_ERROR = theme.ERROR
COLOR_MUTED = theme.MUTED


def _shorten(text: str, limit: int = 70) -> str:
    if len(text) <= limit:
        return text
    keep = (limit - 3) // 2
    return text[:keep] + "..." + text[-keep:]


class BranchSelectorApp:
    """Main window. All slow work runs on worker threads via ``_submit``."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        settings_path: Path | None,
        branches_path: Path,
        auto_shortcut: bool = True,
    ) -> None:
        self.root = root
        self.state = paths.load_state()
        self.settings_path = settings_path
        self.branches_path = branches_path
        self.auto_shortcut = auto_shortcut

        self.catalog: BranchCatalog | None = None
        self.catalog_error: str | None = None
        self.busy = False
        self._branches_mtime: float | None = None

        self._tasks: "queue.Queue[tuple[Callable[[Any], None], Any]]" = queue.Queue()

        self._load_catalog(initial=True)
        self._build_ui()
        self._restore_selection()

        self.root.after(120, self._poll_tasks)
        self.root.after(250, self.refresh_status)
        if self.settings_path is None:
            self.root.after(700, self._prompt_for_settings)
        if auto_shortcut:
            self.root.after(1500, self._auto_shortcut)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title("BrickVPN Branch Selector")
        icon = asset_icon()
        if icon is not None:
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                _LOGGER.warning("Could not apply the window icon", exc_info=True)

        theme.install(self.root)
        self.root.geometry("840x720")
        self.root.minsize(740, 620)

        self._build_menu()
        self._build_header()
        self._build_status_bar()

        main = ttk.Frame(self.root, padding=(22, 16, 22, 12))
        main.pack(fill="both", expand=True)
        self._build_status_card(main)
        self._build_branch_card(main)
        self._build_actions(main)

        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 3)
        self.root.geometry(f"+{x}+{y}")

        self.root.bind("<FocusIn>", self._on_focus, add="+")
        self.root.bind_all("<F5>", lambda _event: self.refresh_status())
        self.root.bind_all("<Control-t>", lambda _event: self.test_connection())
        self.root.bind_all("<Control-r>", lambda _event: self._reload_catalog())
        self.root.bind_all("<Control-e>", lambda _event: self.edit_branches())
        self.root.bind_all("<Control-d>", lambda _event: self.copy_diagnostics())

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=theme.NAVY)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=theme.NAVY, padx=24, pady=18)
        inner.pack(fill="x")

        left = tk.Frame(inner, bg=theme.NAVY)
        left.pack(side="left", anchor="w")
        tk.Label(
            left,
            text="Branch Selector",
            bg=theme.NAVY,
            fg="#ffffff",
            font=theme.FONT_TITLE,
        ).pack(anchor="w")
        tk.Label(
            left,
            text="Point this workstation at another branch's server. Sign in to Twingate first.",
            bg=theme.NAVY,
            fg="#b9c6dd",
            font=theme.FONT,
        ).pack(anchor="w", pady=(3, 0))

        badge = tk.Frame(inner, bg=theme.NAVY)
        badge.pack(side="right", anchor="e")
        tk.Label(
            badge,
            text="BRICKVPN",
            bg=theme.NAVY_SOFT,
            fg="#e2ebff",
            font=theme.FONT_SECTION,
            padx=12,
            pady=5,
        ).pack(anchor="e")
        tk.Label(
            badge,
            text=f"version {__version__}",
            bg=theme.NAVY,
            fg="#8fa3c4",
            font=theme.FONT_SMALL,
        ).pack(anchor="e", pady=(4, 0))

        tk.Frame(self.root, bg=theme.ACCENT, height=3).pack(fill="x")

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self.root, bg=theme.CARD)
        bar.pack(fill="x", side="bottom")
        tk.Frame(bar, bg=theme.BORDER, height=1).pack(fill="x")
        inner = tk.Frame(bar, bg=theme.CARD, padx=16, pady=7)
        inner.pack(fill="x")

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            inner,
            textvariable=self.status_var,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self.progress = ttk.Progressbar(
            inner, mode="determinate", maximum=100, length=160
        )
        self.progress_var = tk.StringVar(value="")
        self.progress_label = tk.Label(
            inner,
            textvariable=self.progress_var,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            width=5,
            anchor="e",
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="Switch to selected branch", command=self.switch_branch, accelerator="Enter"
        )
        file_menu.add_command(
            label="Test connection", command=self.test_connection, accelerator="Ctrl+T"
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Edit branches...", command=self.edit_branches, accelerator="Ctrl+E"
        )
        file_menu.add_command(
            label="Reload branches", command=self._reload_catalog, accelerator="Ctrl+R"
        )
        file_menu.add_command(
            label="Open branches.json (advanced)", command=self.open_branches
        )
        file_menu.add_separator()
        file_menu.add_command(label="Open settings.ini", command=self.open_settings)
        file_menu.add_command(label="Locate settings.ini...", command=self.locate_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Create desktop shortcut", command=self.create_shortcut)
        if not is_admin():
            file_menu.add_command(
                label="Restart as administrator", command=self.restart_as_admin
            )
        file_menu.add_command(label="Open log folder", command=self.open_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(
            label="Copy diagnostics", command=self.copy_diagnostics, accelerator="Ctrl+D"
        )
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.configure(menu=menubar)

    def _build_status_card(self, parent: ttk.Frame) -> None:
        card = theme.card(parent)
        card.pack(fill="x", pady=(16, 0))
        inner = tk.Frame(card, bg=theme.CARD, padx=18, pady=14)
        inner.pack(fill="both", expand=True)
        inner.columnconfigure(1, weight=1)

        tk.Label(
            inner,
            text="WORKSTATION",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.current_label = self._status_row(inner, 1, "Current server")
        self.twingate_label = self._status_row(inner, 2, "Twingate")
        self.connection_label = self._status_row(inner, 3, "Connection")

        tk.Label(
            inner,
            text="Settings file",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).grid(row=4, column=0, sticky="w", pady=(9, 0), padx=(0, 14))
        self.settings_label = tk.Label(
            inner,
            text="Not located",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
        )
        self.settings_label.grid(row=4, column=1, sticky="w", pady=(9, 0))

        actions = tk.Frame(inner, bg=theme.CARD)
        actions.grid(row=4, column=2, sticky="e", pady=(9, 0))
        ttk.Button(
            actions, text="Open", style="Link.TButton", command=self.open_settings
        ).pack(side="left")
        ttk.Button(
            actions, text="Change...", style="Link.TButton", command=self.locate_settings
        ).pack(side="left", padx=(4, 0))

    def _status_row(self, parent: tk.Frame, row: int, title: str) -> ttk.Label:
        tk.Label(
            parent,
            text=title,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=3)
        value = ttk.Label(
            parent, text="-", style="Value.TLabel", wraplength=520, justify="left"
        )
        value.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        return value

    def _build_branch_card(self, parent: ttk.Frame) -> None:
        card = theme.card(parent)
        card.pack(fill="both", expand=True, pady=(16, 0))
        inner = tk.Frame(card, bg=theme.CARD, padx=18, pady=14)
        inner.pack(fill="both", expand=True)

        head = tk.Frame(inner, bg=theme.CARD)
        head.pack(fill="x")
        tk.Label(
            head,
            text="BRANCHES",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).pack(side="left")
        ttk.Button(
            head, text="Edit branches", style="Link.TButton", command=self.edit_branches
        ).pack(side="right")
        ttk.Button(
            head, text="Reload", style="Link.TButton", command=self._reload_catalog
        ).pack(side="right", padx=(0, 8))

        self.catalog_message = tk.Label(
            inner,
            text="",
            bg=theme.CARD,
            fg=theme.ERROR,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=700,
        )
        self.catalog_message.pack(anchor="w", pady=(4, 0))

        table = tk.Frame(inner, bg=theme.CARD)
        table.pack(fill="both", expand=True, pady=(8, 0))

        columns = ("branch", "server", "status")
        self.tree = ttk.Treeview(
            table, columns=columns, show="headings", selectmode="browse", height=7
        )
        self.tree.heading("branch", text="Branch")
        self.tree.heading("server", text="Server")
        self.tree.heading("status", text="Status")
        self.tree.column("branch", width=360, anchor="w", stretch=True)
        self.tree.column("server", width=190, anchor="w", stretch=False)
        self.tree.column("status", width=100, anchor="center", stretch=False)
        self.tree.tag_configure(
            "current", font=theme.FONT_BOLD, foreground=theme.OK
        )

        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda _event: self.switch_branch())
        self.tree.bind("<Return>", lambda _event: self.switch_branch())

        tk.Label(
            inner,
            text="The server listed here is written to settings.ini. Restart the hotel software after switching.",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=700,
        ).pack(anchor="w", pady=(10, 0))

    def _build_actions(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(16, 0))

        self.check_btn = ttk.Button(
            bar, text="Test connection", command=self.test_connection
        )
        self.check_btn.pack(side="left")
        self.refresh_btn = ttk.Button(
            bar, text="Refresh status", command=self.refresh_status
        )
        self.refresh_btn.pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Edit branches...", command=self.edit_branches).pack(
            side="left", padx=(8, 0)
        )
        self.switch_btn = ttk.Button(
            bar, text="Switch branch", command=self.switch_branch, style="Accent.TButton"
        )
        self.switch_btn.pack(side="right")

    # ------------------------------------------------------------------
    # Catalogue and selection
    # ------------------------------------------------------------------

    def _load_catalog(self, *, initial: bool = False) -> None:
        try:
            self.catalog = load_or_create(self.branches_path)
            self.catalog_error = None
            self._branches_mtime = self._mtime()
        except BranchesError as exc:
            self.catalog = None
            self.catalog_error = str(exc)
            _LOGGER.error("Branch catalogue problem: %s", exc)
            if initial:
                self.root.after(
                    400,
                    lambda: messagebox.showerror(
                        "Branch list problem",
                        f"{exc}\n\nFix {self.branches_path} and use File > Reload branches.",
                    ),
                )

    def _mtime(self) -> float | None:
        try:
            return self.branches_path.stat().st_mtime
        except OSError:
            return None

    def _reload_catalog(self) -> None:
        selected = self._selected_branch_id()
        self._load_catalog()
        self._populate_tree(selected)
        self._refresh_current()
        if self.catalog_error:
            self.status_var.set("Branch list could not be loaded.")
        elif self.catalog is not None:
            self.status_var.set(f"Loaded {len(self.catalog.branches)} branches.")

    def _populate_tree(self, select_id: str | None = None) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.catalog is None:
            if self.catalog_error:
                self.catalog_message.configure(text=self.catalog_error)
            return

        self.catalog_message.configure(text="")
        for branch in self.catalog.branches:
            self.tree.insert(
                "",
                "end",
                iid=branch.id,
                values=(branch.display_name, branch.server, ""),
            )
        if select_id and self.tree.exists(select_id):
            self.tree.selection_set(select_id)
            self.tree.focus(select_id)
            self.tree.see(select_id)
        elif self.catalog.branches and not self.tree.selection():
            first = self.catalog.branches[0].id
            self.tree.selection_set(first)
            self.tree.focus(first)
        self._mark_current()

    def _restore_selection(self) -> None:
        self._populate_tree()
        if not self.catalog:
            self._refresh_current()
            self._show_last_switch()
            return

        last = self.state.get("last_branch")
        if not isinstance(last, str) or self.catalog.get(last) is None:
            last = None
        if last is None:
            current = self._read_current_server()
            matched = self.catalog.find_by_server(current)
            last = matched.id if matched else self.catalog.branches[0].id

        if self.tree.exists(last):
            self.tree.selection_set(last)
            self.tree.focus(last)
            self.tree.see(last)
        self._refresh_current()
        self._show_last_switch()

    def _show_last_switch(self) -> None:
        stamp = self.state.get("last_switched_at")
        if not isinstance(stamp, str):
            return
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            return
        last = self.state.get("last_branch")
        branch = self.catalog.get(last) if isinstance(last, str) and self.catalog else None
        suffix = f" ({branch.display_name})" if branch else ""
        self.status_var.set(f"Last switch: {when.strftime('%d %b %Y %H:%M')}{suffix}")

    def _selected_branch_id(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _selected_branch(self) -> Branch | None:
        if not self.catalog:
            return None
        branch_id = self._selected_branch_id()
        if branch_id is None:
            return None
        return self.catalog.get(branch_id)

    def _on_focus(self, event: tk.Event) -> None:
        if self.busy or self.catalog is None:
            return
        mtime = self._mtime()
        if mtime is not None and mtime != self._branches_mtime:
            _LOGGER.info("branches.json changed on disk; reloading")
            self._reload_catalog()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _read_current_server(self) -> str | None:
        if not self.settings_path:
            return None
        try:
            return SettingsDocument.read(self.settings_path).current_server()
        except (OSError, SettingsError):
            _LOGGER.warning("Could not read current server", exc_info=True)
            return None

    def refresh_status(self) -> None:
        if self.busy:
            return
        self._refresh_current()
        self._set_label(self.twingate_label, "Checking...", COLOR_MUTED)
        self._submit(detect_twingate, self._on_twingate)

    def _refresh_current(self) -> None:
        if not self.settings_path:
            self._set_label(self.current_label, "settings.ini not found", COLOR_ERROR)
            self.settings_label.configure(text=f"Expected at {_shorten(str(paths.default_settings_path()))}")
            self._set_label(self.connection_label, "Not checked", COLOR_MUTED)
            self._mark_current()
            self._update_actions()
            return

        self.settings_label.configure(text=_shorten(str(self.settings_path)))
        try:
            server = SettingsDocument.read(self.settings_path).current_server()
        except (OSError, SettingsError) as exc:
            self._set_label(self.current_label, "Could not read settings.ini", COLOR_ERROR)
            self._set_label(self.connection_label, str(exc), COLOR_ERROR)
            self._mark_current()
            self._update_actions()
            return

        if server:
            branch = self.catalog.find_by_server(server) if self.catalog else None
            suffix = f"  ({branch.display_name})" if branch else ""
            self._set_label(self.current_label, f"{server}{suffix}", COLOR_OK)
        else:
            self._set_label(
                self.current_label,
                "No server value found in [Connection_Info]",
                COLOR_WARN,
            )
        self._mark_current()
        self._update_actions()

    def _mark_current(self) -> None:
        if self.catalog is None:
            return
        current = self._read_current_server()
        for branch in self.catalog.branches:
            is_current = bool(
                current and branch.server.lower() == current.strip().lower()
            )
            tags: tuple[str, ...] = ("current",) if is_current else ()
            try:
                self.tree.item(
                    branch.id,
                    values=(
                        branch.display_name,
                        branch.server,
                        "Current" if is_current else "",
                    ),
                    tags=tags,
                )
            except tk.TclError:
                continue

    def _set_label(self, label: ttk.Label, text: str, color: str = COLOR_MUTED) -> None:
        label.configure(text=text, foreground=color)

    def _on_twingate(self, result: TwingateStatus | Exception) -> None:
        if isinstance(result, Exception):
            self._set_label(self.twingate_label, "Status could not be checked.", COLOR_WARN)
            _LOGGER.warning("Twingate probe failed: %s", result)
            return
        color = COLOR_OK if result.running else COLOR_WARN
        self._set_label(self.twingate_label, result.detail, color)

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_branch(self) -> None:
        if self.busy:
            return
        branch = self._selected_branch()
        if branch is None:
            if not self.catalog:
                messagebox.showerror(
                    "Branch list problem",
                    self.catalog_error or "No branches are configured.",
                )
            else:
                messagebox.showinfo("Select a branch", "Choose a branch from the list first.")
            self.tree.focus_set()
            return

        if not self.settings_path:
            messagebox.showwarning(
                "settings.ini not found",
                "Locate the settings.ini used by the hotel software first.",
            )
            self.locate_settings()
            return

        assert self.catalog is not None
        ports = self.catalog.ports_for(branch)
        probe_timeout = self.catalog.probe_timeout
        settings_path = self.settings_path

        self._set_busy(
            True, f"Switching to {branch.display_name}...", determinate=True
        )
        self._set_label(self.connection_label, "Waiting for switch...", COLOR_MUTED)

        def work() -> tuple[str | None, bool, CheckOutcome | None]:
            self._post_progress(0.02, "Reading settings.ini...")
            document = SettingsDocument.read(settings_path)

            self._post_progress(0.06, "Preparing the new server address...")
            previous, changed = document.set_server(branch.server)

            if changed:
                self._post_progress(0.10, "Backing up and writing settings.ini...")
                document.save()
                self._post_progress(0.18, "settings.ini updated.")
            else:
                self._post_progress(0.18, "settings.ini already uses this server.")

            self._post_progress(0.20, "Checking the branch connection...")
            outcome = probe(
                branch.probe_host,
                ports,
                timeout=probe_timeout,
                on_progress=lambda fraction, message: self._post_progress(
                    0.20 + 0.78 * fraction, message
                ),
            )
            self._post_progress(1.0, "Finishing...")
            return previous, changed, outcome

        self._submit(work, lambda result: self._after_switch(branch, result))

    def _after_switch(
        self,
        branch: Branch,
        result: tuple[str | None, bool, CheckOutcome | None] | Exception,
    ) -> None:
        self._set_busy(False)
        if isinstance(result, Exception):
            detail = self._describe_error(result)
            self._set_label(self.connection_label, "Switch failed", COLOR_ERROR)
            self.status_var.set(f"Switch failed: {detail}")
            _LOGGER.error("Switch failed: %s", result)
            if isinstance(result, SettingsAccessError):
                if messagebox.askyesno(
                    "Could not switch branch",
                    f"{detail}\n\nRestart BrickVPN Branch Selector as administrator now?",
                ):
                    self.restart_as_admin()
                return
            messagebox.showerror("Could not switch branch", detail)
            return

        previous, changed, outcome = result
        self.state["last_branch"] = branch.id
        self.state["last_switched_at"] = datetime.now().isoformat(timespec="seconds")
        paths.save_state(self.state)
        self._refresh_current()

        if changed:
            self.status_var.set(
                f"Switched to {branch.display_name}. Restart the hotel software to apply the change."
            )
        else:
            self.status_var.set(f"{branch.display_name} was already selected.")

        if outcome is not None:
            self._apply_probe(outcome)

        address = f"{branch.server}"
        if changed:
            summary = (
                f"You are now connected to the {branch.success_alias} branch.\n\n"
                f"Server: {address}\n"
            )
        else:
            summary = (
                f"This workstation is already set to the {branch.success_alias} branch.\n\n"
                f"Server: {address}\n"
            )
        if previous and changed:
            summary += f"Previous server: {previous}\n"
        if outcome is None:
            summary += "\nConnection was not checked."
        else:
            summary += f"\n{outcome.detail}"

        if outcome is not None and not outcome.ok:
            messagebox.showwarning("Branch set, connection not verified", summary)
        else:
            title = "Branch switched" if changed else "Branch already selected"
            messagebox.showinfo(title, summary)

    def test_connection(self) -> None:
        if self.busy:
            return

        branch = self._selected_branch()
        if branch is not None:
            assert self.catalog is not None
            host = branch.probe_host
            ports = self.catalog.ports_for(branch)
            timeout = self.catalog.probe_timeout
        else:
            server = self._read_current_server()
            if not server:
                messagebox.showinfo(
                    "Nothing to test",
                    "Select a branch, or make sure settings.ini contains a server address.",
                )
                return
            host = server
            ports = self.catalog.default_check_ports if self.catalog else DEFAULT_CHECK_PORTS
            timeout = self.catalog.probe_timeout if self.catalog else DEFAULT_PROBE_TIMEOUT

        self._set_busy(True, f"Testing {host}...", determinate=True)
        self._set_label(self.connection_label, f"Testing {host}...", COLOR_MUTED)
        self._submit(
            lambda: probe(
                host,
                ports,
                timeout=timeout,
                on_progress=self._post_progress,
            ),
            self._on_probe,
        )

    def _on_probe(self, result: CheckOutcome | Exception) -> None:
        self._set_busy(False)
        if isinstance(result, Exception):
            self._set_label(self.connection_label, "Connection check failed.", COLOR_ERROR)
            self.status_var.set(f"Connection check failed: {result}")
            _LOGGER.warning("Connection check failed: %s", result)
            return
        self._apply_probe(result)

    def _apply_probe(self, outcome: CheckOutcome) -> None:
        color = COLOR_OK if outcome.ok else COLOR_WARN
        self._set_label(self.connection_label, outcome.detail, color)
        self.status_var.set(outcome.detail)

    # ------------------------------------------------------------------
    # Files, shortcuts, help
    # ------------------------------------------------------------------

    def open_settings(self) -> None:
        if not self.settings_path:
            self.locate_settings()
            return
        self._open_path(self.settings_path, "settings.ini")

    def open_branches(self) -> None:
        if not self.branches_path.exists():
            self._load_catalog(initial=True)
        self._open_path(self.branches_path, "branches.json")

    def edit_branches(self) -> None:
        """Open the in-app editor for the branch catalogue."""
        if self.busy:
            return
        if not self.branches_path.exists():
            self._load_catalog(initial=True)
        if not self.branches_path.exists():
            messagebox.showerror(
                "Could not open the branch editor",
                self.catalog_error
                or f"{self.branches_path} could not be created.",
            )
            return
        try:
            dialog = BranchEditorDialog(
                self.root, self.branches_path, on_saved=self._branches_saved
            )
        except BranchesError as exc:
            messagebox.showerror(
                "Could not open the branch editor",
                f"{exc}\n\nFix {self.branches_path} and try again.",
            )
            return
        dialog.focus_set()

    def _branches_saved(self) -> None:
        """Reload the catalogue after the editor wrote branches.json."""
        selected = self._selected_branch_id()
        self._load_catalog()
        self._populate_tree(selected)
        self._refresh_current()
        self.root.lift()
        if self.catalog_error:
            self.status_var.set("Branch list could not be loaded after saving.")
            messagebox.showerror(
                "Branch list problem",
                f"{self.catalog_error}\n\nUse File > Edit branches to correct the list.",
            )
            return
        count = len(self.catalog.branches) if self.catalog else 0
        self.status_var.set(f"Branch list updated: {count} branches available.")

    def open_logs(self) -> None:
        folder = paths.log_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Log folder", str(exc))
            return
        self._open_path(folder, "log folder")

    def _open_path(self, path: Path, description: str) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror(f"Could not open {description}", f"{path}\n\n{exc}")

    def _prompt_for_settings(self) -> None:
        if self.settings_path is not None:
            return
        expected = paths.default_settings_path()
        if messagebox.askyesno(
            "settings.ini not found",
            "settings.ini was not found next to the app or in the current folder.\n\n"
            f"Expected: {expected}\n\n"
            "Locate the hotel software's settings.ini now?",
        ):
            self.locate_settings()

    def locate_settings(self) -> None:
        initial = (            str(self.settings_path.parent)
            if self.settings_path
            else str(paths.default_settings_path().parent)
        )
        selected = filedialog.askopenfilename(
            title="Locate the hotel software's settings.ini",
            initialdir=initial,
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
        )
        if not selected:
            return
        candidate = Path(selected)
        try:
            document = SettingsDocument.read(candidate)
        except SettingsError as exc:
            messagebox.showerror("Invalid settings file", str(exc))
            return
        if not document.section_present():
            messagebox.showerror(
                "Invalid settings file",
                f"{candidate.name} does not contain a [Connection_Info] section.",
            )
            return

        self.settings_path = candidate
        self.state["settings_path"] = str(candidate)
        paths.save_state(self.state)
        self.refresh_status()
        self.status_var.set(f"Using {candidate}.")

    def create_shortcut(self) -> None:
        self.status_var.set("Creating desktop shortcut...")
        self._submit(
            lambda: ensure_desktop_shortcut(force=True),
            self._on_shortcut_created,
        )

    def restart_as_admin(self) -> None:
        """Relaunch the app with a UAC prompt and close this window."""
        extra: list[str] = []
        if self.settings_path:
            extra += ["--settings", str(self.settings_path)]
        try:
            launched = relaunch_as_admin(extra)
        except OSError as exc:
            messagebox.showerror("Restart as administrator", str(exc))
            return
        if launched:
            self.root.destroy()
            return
        messagebox.showinfo(
            "Restart as administrator",
            "Windows did not start an elevated copy.\n\n"
            'Close the app, right-click it, then choose "Run as administrator".',
        )

    def _on_shortcut_created(self, result: Path | Exception) -> None:
        if isinstance(result, Exception):
            _LOGGER.error("Shortcut creation failed: %s", result)
            self.status_var.set("Could not create desktop shortcut.")
            messagebox.showerror("Desktop shortcut", str(result))
            return
        self.state["shortcut_path"] = str(result)
        self.state["shortcut_exe"] = str(launch_command()[0])
        paths.save_state(self.state)
        self.status_var.set(f"Shortcut ready: {result}")
        messagebox.showinfo("Desktop shortcut", f"Shortcut created:\n{result}")

    def _auto_shortcut(self) -> None:
        if not paths.is_frozen() and os.environ.get("BRICKVPN_FORCE_SHORTCUT") != "1":
            return
        stored = self.state.get("shortcut_path")
        stored_exe = self.state.get("shortcut_exe")
        expected_exe = str(launch_command()[0])
        if (
            isinstance(stored, str)
            and stored
            and Path(stored).exists()
            and stored_exe == expected_exe
        ):
            return
        self._submit(lambda: ensure_desktop_shortcut(force=True), self._on_auto_shortcut)

    def _on_auto_shortcut(self, result: Path | Exception) -> None:
        if isinstance(result, Exception):
            _LOGGER.warning("Automatic shortcut creation failed: %s", result)
            return
        self.state["shortcut_path"] = str(result)
        self.state["shortcut_exe"] = str(launch_command()[0])
        paths.save_state(self.state)

    def copy_diagnostics(self) -> None:
        """Copy a support-friendly snapshot to the clipboard."""
        lines = [
            f"BrickVPN Branch Selector {__version__}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Windows: {platform.platform()}",
            f"Application folder: {paths.app_dir()}",
            f"Branches file: {self.branches_path}",
            f"Settings file: {self.settings_path or 'not located'}",
            f"Current server: {self._read_current_server() or 'not set'}",
            f"Twingate: {self.twingate_label.cget('text')}",
            f"Connection: {self.connection_label.cget('text')}",
        ]
        if self.catalog is not None:
            lines.append(f"Branches loaded: {len(self.catalog.branches)}")
        if self.catalog_error:
            lines.append(f"Branch list error: {self.catalog_error}")

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            self.root.update_idletasks()
        except tk.TclError:
            messagebox.showerror("Copy diagnostics", "The clipboard is not available.")
            return
        self.status_var.set("Diagnostics copied to the clipboard.")

    def show_about(self) -> None:
        messagebox.showinfo(
            "About BrickVPN Branch Selector",
            "BrickVPN Branch Selector {version}\n\n"
            "Branches: {branches}\n"
            "Settings file: {settings}\n"
            "Log folder: {logs}\n\n"
            "Twingate must be signed in before a branch server becomes reachable.".format(
                version=__version__,
                branches=self.branches_path,
                settings=self.settings_path or "not located",
                logs=paths.log_dir(),
            ),
        )

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------

    def _submit(self, work: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        def runner() -> None:
            try:
                result: Any = work()
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI thread
                result = exc
            self._tasks.put((callback, result))

        threading.Thread(target=runner, name="brickvpn-task", daemon=True).start()

    def _post_progress(self, fraction: float, message: str) -> None:
        """Queue a progress update from a worker thread (safe to call anywhere)."""
        self._tasks.put((None, (fraction, message)))

    def _apply_progress(self, fraction: float, message: str) -> None:
        percent = int(round(max(0.0, min(1.0, fraction)) * 100))
        try:
            self.progress.configure(value=percent)
            self.progress_var.set(f"{percent}%")
        except tk.TclError:
            return
        if message:
            self.status_var.set(f"{message} ({percent}%)")

    def _poll_tasks(self) -> None:
        try:
            while True:
                callback, result = self._tasks.get_nowait()
                try:
                    if callback is None:
                        self._apply_progress(*result)
                    else:
                        callback(result)
                except Exception:  # noqa: BLE001 - keep the UI alive
                    _LOGGER.exception("UI callback failed")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_tasks)

    def _set_busy(
        self, busy: bool, message: str | None = None, *, determinate: bool = False
    ) -> None:
        self.busy = busy
        if message:
            self.status_var.set(message)
        if busy:
            self.progress.pack(side="right", padx=(8, 0))
            self.progress_label.pack(side="right")
            if determinate:
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
                self.progress_var.set("0%")
            else:
                self.progress.configure(mode="indeterminate")
                self.progress_var.set("")
                self.progress.start(12)
            self.root.configure(cursor="watch")
        else:
            self.progress.stop()
            self.progress.configure(value=0)
            self.progress.pack_forget()
            self.progress_label.pack_forget()
            self.progress_var.set("")
            self.root.configure(cursor="")
        self._update_actions()

    def _update_actions(self) -> None:
        has_catalog = bool(self.catalog and self.catalog.branches)
        can_switch = has_catalog and self.settings_path is not None and not self.busy
        can_check = (has_catalog or self.settings_path is not None) and not self.busy

        self.switch_btn.configure(state="normal" if can_switch else "disabled")
        self.check_btn.configure(state="normal" if can_check else "disabled")
        self.refresh_btn.configure(state="disabled" if self.busy else "normal")

    @staticmethod
    def _describe_error(exc: Exception) -> str:
        if isinstance(exc, PermissionError):
            return (
                f"Windows refused access to settings.ini ({exc}).\n\n"
                "Close the hotel software and try again, or run the selector "
                "with an account that can write to that folder."
            )
        if isinstance(exc, (SettingsError, ShortcutError)):
            return str(exc)
        return f"{type(exc).__name__}: {exc}"
