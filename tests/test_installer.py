"""Tests for the installer plan: site data must survive every upgrade."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from installer import core

SETTINGS = b"[Connection_Info]\r\nserver = 192.168.2.16\r\nnetwork_path = \\\\tvmserver\\tvm01\r\n"
BRANCHES = b'{"schema_version": 1, "branches": []}'


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)
        self.source = self.folder / "payload"
        self.target = self.folder / "hotel"
        self.source.mkdir()
        self.target.mkdir()

        (self.source / "Switcher.exe").write_bytes(b"new-exe")
        (self.source / "branches.json").write_bytes(BRANCHES)
        (self.source / "license.json").write_bytes(b"new-licence")
        (self.target / "settings.ini").write_bytes(SETTINGS)

    def test_fresh_installation_copies_the_payload(self) -> None:
        plan = core.build_plan(self.source, self.target)
        self.assertEqual(
            plan.copy, ("Switcher.exe", "branches.json", "license.json")
        )
        self.assertEqual(plan.keep, ())
        copied = core.apply_plan(plan, stamp="20261118-120000")

        self.assertEqual(
            sorted(path.name for path in copied),
            ["Switcher.exe", "branches.json", "license.json"],
        )
        self.assertEqual((self.target / "Switcher.exe").read_bytes(), b"new-exe")
        self.assertFalse((self.target / core.BACKUP_FOLDER).exists())

    def test_existing_site_data_is_kept_by_default(self) -> None:
        (self.target / "branches.json").write_bytes(b"site-branches")
        (self.target / "license.json").write_bytes(b"site-licence")

        plan = core.build_plan(self.source, self.target)
        self.assertEqual(plan.copy, ("Switcher.exe",))
        self.assertEqual(plan.keep, ("branches.json", "license.json"))

        core.apply_plan(plan, stamp="20261118-120000")
        self.assertEqual((self.target / "license.json").read_bytes(), b"site-licence")
        self.assertEqual((self.target / "branches.json").read_bytes(), b"site-branches")

    def test_replacement_options_update_the_copied_files(self) -> None:
        (self.target / "branches.json").write_bytes(b"site-branches")
        (self.target / "license.json").write_bytes(b"site-licence")

        plan = core.build_plan(
            self.source,
            self.target,
            replace_license=True,
            replace_branches=True,
        )
        self.assertEqual(plan.copy, ("Switcher.exe", "branches.json", "license.json"))
        core.apply_plan(plan, stamp="20261118-120000")

        self.assertEqual(
            (self.target / "license.json").read_bytes(), b"new-licence"
        )
        self.assertEqual((self.target / "branches.json").read_bytes(), BRANCHES)
        backups = sorted(p.name for p in (self.target / core.BACKUP_FOLDER).iterdir())
        self.assertIn("license-20261118-120000.json", backups)
        self.assertIn("branches-20261118-120000.json", backups)

    def test_settings_ini_is_never_copied_or_changed(self) -> None:
        (self.source / "settings.ini").write_bytes(b"[Broken]")
        plan = core.build_plan(self.source, self.target)
        self.assertNotIn("settings.ini", plan.copy)
        core.apply_plan(plan, stamp="20261118-120000")
        self.assertEqual((self.target / "settings.ini").read_bytes(), SETTINGS)

    def test_missing_executable_is_rejected(self) -> None:
        (self.source / "Switcher.exe").unlink()
        with self.assertRaises(core.InstallerError):
            core.build_plan(self.source, self.target)

    def test_apply_plan_backs_up_the_replaced_executable(self) -> None:
        (self.target / "Switcher.exe").write_bytes(b"old-exe")
        plan = core.build_plan(self.source, self.target)
        core.apply_plan(plan, stamp="20261118-120000")

        self.assertEqual((self.target / "Switcher.exe").read_bytes(), b"new-exe")
        backup = self.target / core.BACKUP_FOLDER / "Switcher-20261118-120000.exe"
        self.assertEqual(backup.read_bytes(), b"old-exe")

    def test_backup_names_do_not_collide(self) -> None:
        (self.target / "Switcher.exe").write_bytes(b"old-exe")
        plan = core.build_plan(self.source, self.target)
        core.apply_plan(plan, stamp="20261118-120000")
        core.apply_plan(plan, stamp="20261118-120000")

        backups = sorted(
            path.name
            for path in (self.target / core.BACKUP_FOLDER).iterdir()
            if path.name.startswith("Switcher-")
        )
        self.assertEqual(
            backups,
            ["Switcher-20261118-120000-1.exe", "Switcher-20261118-120000.exe"],
        )

    def test_plan_targets_default_to_c_hotel(self) -> None:
        self.assertEqual(core.build_plan(self.source).target_dir, Path("C:/hotel"))


class LicenseSummaryTests(unittest.TestCase):
    def test_missing_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            summary = core.license_summary(Path(folder) / "license.json")
        self.assertIn("No licence file", summary)

    def test_unreadable_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "license.json"
            path.write_text("{}", encoding="utf-8")
            summary = core.license_summary(path)
        self.assertIn("could not be verified", summary)

    def test_signed_site_licence_is_summarised(self) -> None:
        summary = core.license_summary(Path("license.json"))
        self.assertIn("Brickspoint Technologies", summary)
        self.assertIn("valid until", summary)


if __name__ == "__main__":
    unittest.main()
