"""Tests for path resolution and persisted state."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brickvpn import paths


class StateTests(unittest.TestCase):
    def test_state_round_trip_in_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": folder}):
                paths.save_state({"last_branch": "wuse", "settings_path": "C:/x/settings.ini"})
                state = paths.load_state()
                self.assertEqual(state["last_branch"], "wuse")
                self.assertEqual(state["settings_path"], "C:/x/settings.ini")
                self.assertTrue(paths.state_file().is_file())

    def test_corrupt_state_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": folder}):
                paths.state_file().parent.mkdir(parents=True)
                paths.state_file().write_text("{ broken", encoding="utf-8")
                self.assertEqual(paths.load_state(), {})


class SettingsResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)
        self.app_folder = self.folder / "app"
        self.app_folder.mkdir()
        patcher = mock.patch.object(paths, "app_dir", return_value=self.app_folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_explicit_path_wins(self) -> None:
        cli_file = self.folder / "custom" / "settings.ini"
        cli_file.parent.mkdir()
        cli_file.write_text("[Connection_Info]\n", encoding="utf-8")
        (self.app_folder / "settings.ini").write_text("[Connection_Info]\n", encoding="utf-8")

        resolved = paths.resolve_settings_path(str(cli_file), {})
        self.assertEqual(resolved, cli_file.resolve())

    def test_state_path_is_used_when_no_cli_value(self) -> None:
        stored = self.folder / "stored.ini"
        stored.write_text("[Connection_Info]\n", encoding="utf-8")
        resolved = paths.resolve_settings_path(None, {"settings_path": str(stored)})
        self.assertEqual(resolved, stored.resolve())

    def test_app_folder_is_the_fallback(self) -> None:
        expected = self.app_folder / "settings.ini"
        expected.write_text("[Connection_Info]\n", encoding="utf-8")
        self.assertEqual(paths.resolve_settings_path(None, {}), expected.resolve())

    def test_app_folder_wins_over_a_stale_stored_path(self) -> None:
        expected = self.app_folder / "settings.ini"
        expected.write_text("[Connection_Info]\n", encoding="utf-8")
        stale = self.folder / "old" / "settings.ini"
        stale.parent.mkdir()
        stale.write_text("[Connection_Info]\n", encoding="utf-8")

        resolved = paths.resolve_settings_path(None, {"settings_path": str(stale)})
        self.assertEqual(resolved, expected.resolve())

    def test_missing_settings_returns_none(self) -> None:
        with mock.patch.object(paths.Path, "cwd", return_value=self.folder / "elsewhere"):
            self.assertIsNone(paths.resolve_settings_path(None, {}))


if __name__ == "__main__":
    unittest.main()
