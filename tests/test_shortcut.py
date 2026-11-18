"""Tests for shortcut script generation (no shortcuts are created)."""

from __future__ import annotations

import unittest
from pathlib import Path

from brickvpn import shortcut
from brickvpn.branding import APP_NAME


class ShortcutBuildingTests(unittest.TestCase):
    def test_shortcut_uses_the_product_name(self) -> None:
        self.assertEqual(shortcut.SHORTCUT_NAME, APP_NAME)
        self.assertEqual(APP_NAME, "Switcher")

    def test_single_quotes_are_escaped(self) -> None:
        self.assertEqual(shortcut._quote("C:\\O'Brien\\app.exe"), "'C:\\O''Brien\\app.exe'")

    def test_script_contains_all_fields(self) -> None:
        script = shortcut._build_script(
            link=Path("C:/Users/Test/Desktop/Switcher.lnk"),
            executable=Path("C:/Apps/Switcher/Switcher.exe"),
            arguments="",
            workdir=Path("C:/Apps/Switcher"),
            icon=Path("C:/Apps/Switcher/Switcher.exe"),
            description="Switcher",
        )
        self.assertIn("CreateShortcut", script)
        self.assertIn("Switcher.lnk", script)
        self.assertIn("WorkingDirectory", script)
        self.assertIn("IconLocation", script)
        self.assertIn("$shortcut.Save()", script)

    def test_desktop_dir_is_a_path(self) -> None:
        self.assertIsInstance(shortcut.desktop_dir(), Path)

    def test_admin_check_returns_a_bool(self) -> None:
        self.assertIsInstance(shortcut.is_admin(), bool)

    def test_launch_command_points_at_an_existing_target(self) -> None:
        executable, arguments, workdir = shortcut.launch_command()
        self.assertTrue(executable.is_file())
        self.assertIsInstance(arguments, str)
        self.assertTrue(workdir.is_dir())

    def test_elevation_request_keeps_settings_argument(self) -> None:
        executable, parameters, workdir = shortcut._elevation_request(
            ["--settings", r"C:\hotel\settings.ini"]
        )
        self.assertTrue(executable.is_file())
        self.assertIn("--settings", parameters)
        self.assertIn("settings.ini", parameters)
        self.assertTrue(workdir.is_dir())


if __name__ == "__main__":
    unittest.main()
