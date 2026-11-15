"""Headless smoke tests for the main window and the branch editor."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - tkinter is present on Windows
    tk = None  # type: ignore[assignment]

from brickvpn import ui
from brickvpn.branch_editor import BranchEditorDialog

DOCUMENT = {
    "schema_version": 1,
    "default_check_ports": [445, 1433],
    "probe_timeout_seconds": 2,
    "branches": [
        {"id": "wuse", "name": "Wuse", "label": "Wuse (SERVER 1)", "server": "10.0.0.1"},
        {"id": "asokoro", "name": "Asokoro", "server": "10.0.0.2"},
        {"id": "old", "name": "Old site", "server": "10.0.0.3", "enabled": False},
    ],
}

SETTINGS = "[Connection_Info]\r\nserver = 10.0.0.1\r\n"


class UserInterfaceSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        if tk is None:
            self.skipTest("tkinter is not available")
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)
        self.branches = self.folder / "branches.json"
        self.branches.write_text(json.dumps(DOCUMENT, indent=2), encoding="utf-8")
        self.settings = self.folder / "settings.ini"
        self.settings.write_text(SETTINGS, encoding="utf-8")

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - no display
            self.skipTest(f"no Tk display: {exc}")
        self.root.withdraw()

        patcher = mock.patch.multiple(
            ui.messagebox,
            showerror=mock.DEFAULT,
            showinfo=mock.DEFAULT,
            showwarning=mock.DEFAULT,
            askyesno=mock.DEFAULT,
        )
        self.dialogs = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._destroy)

    def _destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    @staticmethod
    def _close_dialog(dialog: BranchEditorDialog) -> None:
        try:
            if dialog.winfo_exists():
                dialog.destroy()
        except tk.TclError:
            pass

    def _app(self) -> ui.BranchSelectorApp:
        return ui.BranchSelectorApp(
            self.root,
            settings_path=self.settings,
            branches_path=self.branches,
            auto_shortcut=False,
        )

    def test_main_window_lists_only_enabled_branches(self) -> None:
        app = self._app()
        rows = app.tree.get_children()
        self.assertEqual(list(rows), ["wuse", "asokoro"])
        self.assertEqual(app.tree.item("wuse")["values"][2], "Current")
        self.assertEqual(app.tree.selection(), ("wuse",))
        self.assertEqual(app.catalog_message.cget("text"), "")

    def test_editor_saves_changes_and_preserves_disabled_rows(self) -> None:
        app = self._app()
        app.tree.selection_set("asokoro")

        dialog = BranchEditorDialog(
            self.root, self.branches, on_saved=app._branches_saved
        )
        self.addCleanup(self._close_dialog, dialog)
        self.assertEqual(len(dialog.list.get_children()), 3)

        dialog.list.selection_set("asokoro")
        dialog._on_select(None)
        dialog.vars["name"].set("Asokoro Main")
        dialog.vars["server"].set("10.0.0.9")
        dialog.save()

        saved = json.loads(self.branches.read_text(encoding="utf-8"))
        self.assertEqual([entry["id"] for entry in saved["branches"]], ["wuse", "asokoro", "old"])
        self.assertEqual(saved["branches"][1]["name"], "Asokoro Main")
        self.assertEqual(saved["branches"][1]["server"], "10.0.0.9")
        self.assertIs(saved["branches"][2]["enabled"], False)

        self.assertEqual(app.tree.selection(), ("asokoro",))
        self.assertEqual(app.tree.item("asokoro")["values"][0], "Asokoro Main")
        self.assertIn("2 branches", app.status_var.get())

    def test_editor_rejects_an_invalid_server(self) -> None:
        app = self._app()
        dialog = BranchEditorDialog(
            self.root, self.branches, on_saved=app._branches_saved
        )
        self.addCleanup(self._close_dialog, dialog)

        dialog.vars["server"].set("not a host")
        dialog.save()

        self.assertIn("not a valid IP address", dialog.error_label.cget("text"))
        self.dialogs["showerror"].assert_called()
        saved = json.loads(self.branches.read_text(encoding="utf-8"))
        self.assertEqual(saved["branches"][0]["server"], "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
