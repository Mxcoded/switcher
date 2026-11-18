"""In-app editor for ``branches.json``.

The dialog hides internal fields (ids) and edits every published attribute:
name, server, label, alias, check host, ports, notes and enabled state.
Changes are only written when **Save branches** is pressed, after the whole
document has been validated.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from . import theme
from .branches import (
    DEFAULT_CHECK_PORTS,
    DEFAULT_PROBE_TIMEOUT,
    BranchesError,
    load_document,
    parse_ports_text,
    save_document,
    slugify,
    valid_host,
)


@dataclass
class EditorBranch:
    """Mutable working copy of one branch entry."""

    id: str
    name: str = ""
    server: str = ""
    label: str = ""
    alias: str = ""
    check_host: str = ""
    check_ports: str = ""
    notes: str = ""
    enabled: bool = True

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> "EditorBranch":
        ports = entry.get("check_ports")
        if isinstance(ports, int) and not isinstance(ports, bool):
            ports_text = str(ports)
        elif isinstance(ports, list):
            ports_text = ", ".join(str(port) for port in ports)
        else:
            ports_text = ""
        return cls(
            id=str(entry.get("id") or ""),
            name=str(entry.get("name") or ""),
            server=str(entry.get("server") or ""),
            label=str(entry.get("label") or ""),
            alias=str(entry.get("alias") or ""),
            check_host=str(entry.get("check_host") or ""),
            check_ports=ports_text,
            notes=str(entry.get("notes") or ""),
            enabled=entry.get("enabled", True) is not False,
        )

    def to_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": self.id,
            "name": self.name.strip(),
            "server": self.server.strip(),
        }
        if self.label.strip():
            entry["label"] = self.label.strip()
        if self.alias.strip():
            entry["alias"] = self.alias.strip()
        if self.check_host.strip():
            entry["check_host"] = self.check_host.strip()
        ports = parse_ports_text(self.check_ports)
        if ports:
            entry["check_ports"] = list(ports)
        if not self.enabled:
            entry["enabled"] = False
        if self.notes.strip():
            entry["notes"] = self.notes.strip()
        return entry

    @property
    def display_name(self) -> str:
        return self.label.strip() or self.name.strip() or "New branch"


class BranchEditorDialog(tk.Toplevel):
    """Modal editor for the branch catalogue."""

    def __init__(
        self,
        parent: tk.Misc,
        branches_path: Path,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.branches_path = branches_path
        self.on_saved = on_saved

        self.document = load_document(branches_path)
        self.branches = [
            EditorBranch.from_entry(entry)
            for entry in self.document.get("branches", [])
            if isinstance(entry, dict)
        ]
        self._assign_missing_ids()
        self.baseline = [replace(branch) for branch in self.branches]
        self.baseline_ports = self._ports_text(
            self.document.get("default_check_ports", list(DEFAULT_CHECK_PORTS))
        )
        timeout_value = self.document.get("probe_timeout_seconds", DEFAULT_PROBE_TIMEOUT)
        self.baseline_timeout = str(timeout_value)

        self._current: EditorBranch | None = None
        self._loading = False

        self.title("Edit branches")
        self.configure(bg=theme.BG)
        self.minsize(880, 700)
        self.geometry("940x740")
        self.transient(parent)
        self.resizable(True, True)

        self._build()
        self._select(0)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _event: self.cancel())
        self.bind("<Control-s>", lambda _event: self.save())
        self.after(60, self._activate)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _assign_missing_ids(self) -> None:
        """Give every row a unique id so the list widget stays consistent."""
        used: set[str] = set()
        for branch in self.branches:
            if not branch.id or branch.id in used:
                branch.id = slugify(branch.name or "branch", used)
            used.add(branch.id)

    def _build(self) -> None:
        header = tk.Frame(self, bg=theme.NAVY)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=theme.NAVY, padx=22, pady=16)
        inner.pack(fill="x")
        tk.Label(
            inner,
            text="Edit branches",
            bg=theme.NAVY,
            fg="#ffffff",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            inner,
            text="Add, rename, disable or re-address branches. settings.ini is not changed here.",
            bg=theme.NAVY,
            fg="#b9c6dd",
            font=theme.FONT,
        ).pack(anchor="w", pady=(2, 0))
        tk.Frame(self, bg=theme.ACCENT, height=3).pack(fill="x")

        body = ttk.Frame(self, padding=(20, 16, 20, 10))
        body.columnconfigure(0, weight=0, minsize=300)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_footer()
        body.pack(fill="both", expand=True)
        self._build_list(body)
        self._build_form(body)

    def _build_list(self, parent: ttk.Frame) -> None:
        card = theme.card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        inner = tk.Frame(card, bg=theme.CARD, padx=12, pady=12)
        inner.pack(fill="both", expand=True)

        tk.Label(
            inner,
            text="BRANCHES",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).pack(anchor="w", pady=(0, 8))

        table = tk.Frame(inner, bg=theme.CARD)
        table.pack(fill="both", expand=True)
        self.list = ttk.Treeview(
            table,
            columns=("branch", "server"),
            show="headings",
            selectmode="browse",
        )
        self.list.heading("branch", text="Branch")
        self.list.heading("server", text="Server")
        self.list.column("branch", width=165, anchor="w", stretch=True)
        self.list.column("server", width=105, anchor="w", stretch=False)
        self.list.tag_configure("disabled", foreground=theme.MUTED)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set)
        self.list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.list.bind("<<TreeviewSelect>>", self._on_select)

        buttons = ttk.Frame(inner)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="+ Add", command=self._add).grid(
            row=0, column=0, sticky="ew", pady=(0, 4), padx=(0, 4)
        )
        ttk.Button(buttons, text="Duplicate", command=self._duplicate).grid(
            row=0, column=1, sticky="ew", pady=(0, 4)
        )
        ttk.Button(buttons, text="Remove", command=self._remove).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(0, 4)
        )
        ttk.Button(buttons, text="Move up", command=lambda: self._move(-1)).grid(
            row=2, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(buttons, text="Move down", command=lambda: self._move(1)).grid(
            row=2, column=1, sticky="ew"
        )
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

    def _build_form(self, parent: ttk.Frame) -> None:
        card = theme.card(parent)
        card.grid(row=0, column=1, sticky="nsew")
        form = tk.Frame(card, bg=theme.CARD, padx=18, pady=14)
        form.pack(fill="both", expand=True)
        form.columnconfigure(0, weight=1, uniform="form")
        form.columnconfigure(1, weight=1, uniform="form")

        self.vars = {
            "name": tk.StringVar(),
            "server": tk.StringVar(),
            "label": tk.StringVar(),
            "alias": tk.StringVar(),
            "check_host": tk.StringVar(),
            "check_ports": tk.StringVar(),
        }
        self.entries: dict[str, ttk.Entry] = {}

        self._section(form, 0, "BRANCH DETAILS", span=2)
        self._field(form, 1, "Branch name", "name", span=2)
        self._field(form, 3, "Server address", "server", span=2)
        self._field(form, 5, "Display label (optional)", "label", column=0)
        self._field(form, 5, "Connection alias (optional)", "alias", column=1)
        self._field(form, 7, "Check host (optional)", "check_host", column=0)
        self._field(form, 7, "Check ports (optional)", "check_ports", column=1)
        tk.Label(
            form,
            text="Ports are separated by commas, for example 445, 1433. Leave blank for the defaults.",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 8))

        tk.Label(
            form,
            text="Notes (optional)",
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).grid(row=10, column=0, columnspan=2, sticky="w")
        self.notes_text = tk.Text(
            form,
            height=3,
            wrap="word",
            font=theme.FONT,
            bg="#ffffff",
            fg=theme.INK,
            relief="solid",
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT,
            padx=6,
            pady=4,
        )
        self.notes_text.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(3, 8))

        self.enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            form,
            text="Offer this branch in the selector",
            variable=self.enabled_var,
            bg=theme.CARD,
            activebackground=theme.CARD,
            fg=theme.INK,
            activeforeground=theme.INK,
            selectcolor="#ffffff",
            font=theme.FONT,
            highlightthickness=0,
            bd=0,
            anchor="w",
        ).grid(row=12, column=0, columnspan=2, sticky="w", pady=(2, 10))

        tk.Frame(form, bg=theme.BORDER, height=1).grid(
            row=13, column=0, columnspan=2, sticky="ew", pady=(2, 10)
        )

        self._section(form, 14, "CONNECTION DEFAULTS", span=2)
        self.default_ports_var = tk.StringVar(value=self.baseline_ports)
        self.timeout_var = tk.StringVar(value=self.baseline_timeout)
        self._field(
            form,
            15,
            "Default check ports (comma separated)",
            "default_ports",
            column=0,
            variable=self.default_ports_var,
            span=1,
        )
        self._field(
            form,
            15,
            "Probe timeout (seconds, 0.5 to 30)",
            "probe_timeout",
            column=1,
            variable=self.timeout_var,
            span=1,
        )

    def _section(self, parent: tk.Frame, row: int, text: str, span: int = 1) -> None:
        tk.Label(
            parent,
            text=text,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SECTION,
        ).grid(row=row, column=0, columnspan=span, sticky="w", pady=(4, 6))

    def _field(
        self,
        parent: tk.Frame,
        row: int,
        label: str,
        key: str,
        *,
        column: int = 0,
        span: int = 1,
        variable: tk.StringVar | None = None,
    ) -> None:
        padx = (0, 8) if column == 0 and span == 1 else (0, 0)
        columnspan = span if span > 1 else 1
        tk.Label(
            parent,
            text=label,
            bg=theme.CARD,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
        ).grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="w",
            padx=padx,
        )
        entry = ttk.Entry(parent, textvariable=variable or self.vars[key])
        entry.grid(
            row=row + 1,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=padx,
            pady=(3, 8),
        )
        self.entries[key] = entry

    def _build_footer(self) -> None:
        footer = ttk.Frame(self, padding=(20, 0, 20, 16))
        footer.pack(fill="x", side="bottom")
        self.error_label = tk.Label(
            footer,
            text="",
            bg=theme.BG,
            fg=theme.ERROR,
            font=theme.FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self.error_label.pack(side="left", fill="x", expand=True)

        ttk.Button(footer, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(
            footer,
            text="Save branches",
            style="Accent.TButton",
            command=self.save,
        ).pack(side="right", padx=(0, 8))

    def _activate(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            return
        self._center()
        self.entries["name"].focus_set()

    def _center(self) -> None:
        parent = self.master
        try:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 3)
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # List and form
    # ------------------------------------------------------------------

    @staticmethod
    def _ports_text(value: Any) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, list):
            return ", ".join(str(port) for port in value)
        return ""

    def _refresh_list(self) -> None:
        for item in self.list.get_children():
            self.list.delete(item)
        for branch in self.branches:
            tags: tuple[str, ...] = () if branch.enabled else ("disabled",)
            self.list.insert(
                "",
                "end",
                iid=branch.id,
                values=(branch.display_name, branch.server.strip() or "-"),
                tags=tags,
            )
        if self._current is not None and self.list.exists(self._current.id):
            self.list.selection_set(self._current.id)
            self.list.see(self._current.id)

    def _select(self, index: int) -> None:
        if not self.branches:
            self._current = None
            return
        index = max(0, min(index, len(self.branches) - 1))
        branch = self.branches[index]
        self._current = branch
        self._loading = True
        for key, var in self.vars.items():
            var.set(str(getattr(branch, key)))
        self.enabled_var.set(branch.enabled)
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", branch.notes)
        self._loading = False
        self._refresh_list()
        self.error_label.configure(text="")

    def _on_select(self, _event: tk.Event) -> None:
        if self._loading or self._current is None:
            return
        selection = self.list.selection()
        if not selection:
            return
        chosen = selection[0]
        if chosen == self._current.id:
            return
        self._commit()
        for index, branch in enumerate(self.branches):
            if branch.id == chosen:
                self._select(index)
                return

    def _refresh_row(self, branch: EditorBranch) -> None:
        """Update one row without touching the current selection."""
        if not self.list.exists(branch.id):
            return
        tags: tuple[str, ...] = () if branch.enabled else ("disabled",)
        self.list.item(
            branch.id,
            values=(branch.display_name, branch.server.strip() or "-"),
            tags=tags,
        )

    def _commit(self) -> EditorBranch | None:
        if self._current is None:
            return None
        for key, var in self.vars.items():
            setattr(self._current, key, var.get().strip())
        self._current.enabled = bool(self.enabled_var.get())
        self._current.notes = self.notes_text.get("1.0", "end").strip()
        self._refresh_row(self._current)
        return self._current

    def _add(self) -> None:
        self._commit()
        used = {branch.id for branch in self.branches}
        branch = EditorBranch(id=slugify("New branch", used))
        self.branches.append(branch)
        self._current = None
        self._refresh_list()
        self._select(len(self.branches) - 1)
        self.entries["name"].focus_set()

    def _duplicate(self) -> None:
        current = self._commit()
        if current is None:
            return
        used = {branch.id for branch in self.branches}
        copy = replace(
            current,
            id=slugify(current.name or "branch", used),
            name=(current.name.strip() or "Branch") + " copy",
            label="",
            alias="",
        )
        index = self.branches.index(current) + 1
        self.branches.insert(index, copy)
        self._current = None
        self._refresh_list()
        self._select(index)

    def _remove(self) -> None:
        current = self._commit()
        if current is None:
            return
        if len(self.branches) == 1:
            self._show_error("Keep at least one branch in the list.")
            return
        if not messagebox.askyesno(
            "Remove branch",
            f"Remove '{current.display_name}' from the list?\n\n"
            "This only changes branches.json; settings.ini is not touched.",
            parent=self,
        ):
            return
        index = self.branches.index(current)
        self.branches.remove(current)
        self._current = None
        self._refresh_list()
        self._select(min(index, len(self.branches) - 1))

    def _move(self, offset: int) -> None:
        current = self._commit()
        if current is None:
            return
        index = self.branches.index(current)
        target = index + offset
        if not 0 <= target < len(self.branches):
            return
        self.branches[index], self.branches[target] = (
            self.branches[target],
            self.branches[index],
        )
        self._refresh_list()
        self.list.selection_set(current.id)
        self.list.see(current.id)

    # ------------------------------------------------------------------
    # Saving and closing
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self.error_label.configure(text=message)
        self.bell()

    def _build_document(self) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for index, branch in enumerate(self.branches, start=1):
            name = branch.name.strip()
            server = branch.server.strip()
            if not name:
                raise BranchesError(f"Branch {index}: enter a branch name.")
            if not server:
                raise BranchesError(f"Branch {index} ({name}): enter a server address.")
            if not valid_host(server):
                raise BranchesError(
                    f'Branch {index} ({name}): "{server}" is not a valid IP address or host name.'
                )
            check_host = branch.check_host.strip()
            if check_host and not valid_host(check_host):
                raise BranchesError(
                    f'Branch {index} ({name}): "{check_host}" is not a valid check host.'
                )
            try:
                entries.append(branch.to_entry())
            except BranchesError as exc:
                raise BranchesError(f"Branch {index} ({name}): {exc}") from None

        ports_text = self.default_ports_var.get().strip()
        default_ports = list(parse_ports_text(ports_text)) if ports_text else list(
            DEFAULT_CHECK_PORTS
        )
        if not default_ports:
            raise BranchesError("Enter at least one default check port.")

        timeout_text = self.timeout_var.get().strip()
        try:
            timeout = float(timeout_text) if timeout_text else DEFAULT_PROBE_TIMEOUT
        except ValueError:
            raise BranchesError(
                "Probe timeout must be a number of seconds, for example 2.0."
            ) from None
        if not 0.5 <= timeout <= 30:
            raise BranchesError("Probe timeout must be between 0.5 and 30 seconds.")

        document: dict[str, Any] = {
            "schema_version": self.document.get("schema_version", 1),
            "default_check_ports": default_ports,
            "probe_timeout_seconds": timeout,
            "branches": entries,
        }
        return document

    def save(self) -> None:
        self._commit()
        try:
            document = self._build_document()
            save_document(self.branches_path, document)
        except BranchesError as exc:
            self._show_error(str(exc))
            messagebox.showerror("Could not save branches", str(exc), parent=self)
            return

        self.grab_release()
        self.destroy()
        self.on_saved()

    def cancel(self) -> None:
        self._commit()
        defaults_changed = (
            self.default_ports_var.get().strip() != self.baseline_ports
            or self.timeout_var.get().strip() != self.baseline_timeout
        )
        if self.branches != self.baseline or defaults_changed:
            if not messagebox.askyesno(
                "Discard changes?",
                "Close the editor and discard the changes you made?",
                parent=self,
            ):
                return
        self.grab_release()
        self.destroy()
