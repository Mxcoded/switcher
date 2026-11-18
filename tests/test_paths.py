"""Tests for path resolution and persisted state."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brickvpn import paths


class StateTests(unittest.TestCase):
    def test_state_folder_is_namespaced_by_vendor(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": folder}):
                self.assertEqual(
                    paths.state_dir(), Path(folder) / "Afriwave" / "Switcher"
                )
                self.assertEqual(paths.log_dir(), paths.state_dir() / "logs")

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
        self.deployment = self.folder / "hotel"
        patcher = mock.patch.object(paths, "app_dir", return_value=self.app_folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        deployment_patcher = mock.patch.object(paths, "DEPLOYMENT_DIR", self.deployment)
        deployment_patcher.start()
        self.addCleanup(deployment_patcher.stop)

    def test_explicit_path_wins(self) -> None:
        cli_file = self.folder / "custom" / "settings.ini"
        cli_file.parent.mkdir()
        cli_file.write_text("[Connection_Info]\n", encoding="utf-8")
        (self.app_folder / "settings.ini").write_text("[Connection_Info]\n", encoding="utf-8")

        resolved = paths.resolve_settings_path(str(cli_file), {})
        self.assertEqual(resolved, cli_file.resolve())

    def test_deployment_folder_wins_over_the_app_folder(self) -> None:
        deployment_file = self.deployment / "settings.ini"
        deployment_file.parent.mkdir()
        deployment_file.write_text("[Connection_Info]\n", encoding="utf-8")
        (self.app_folder / "settings.ini").write_text("[Connection_Info]\n", encoding="utf-8")
        stored = self.folder / "stored.ini"
        stored.write_text("[Connection_Info]\n", encoding="utf-8")

        resolved = paths.resolve_settings_path(None, {"settings_path": str(stored)})
        self.assertEqual(resolved, deployment_file.resolve())

    def test_deployment_settings_path_is_c_hotel(self) -> None:
        self.assertEqual(
            paths.deployment_settings_path(), self.deployment / "settings.ini"
        )

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


class AssetTests(unittest.TestCase):
    def test_source_runs_use_the_project_assets_folder(self) -> None:
        with mock.patch.object(paths, "app_dir", return_value=Path("C:/project")):
            with mock.patch.object(paths.sys, "_MEIPASS", None, create=True):
                self.assertEqual(
                    paths.asset_dir(), Path("C:/project/assets")
                )

    def test_frozen_runs_prefer_the_bundled_assets(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bundled = Path(folder) / "assets"
            bundled.mkdir()
            with mock.patch.object(paths.sys, "_MEIPASS", folder, create=True):
                self.assertEqual(paths.asset_dir(), bundled)


if __name__ == "__main__":
    unittest.main()
