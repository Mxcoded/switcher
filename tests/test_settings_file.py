"""Tests for the conservative settings.ini editor."""

from __future__ import annotations

import codecs
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from brickvpn.settings_file import SettingsAccessError, SettingsDocument, SettingsError

SAMPLE = (
    "; managed by the hotel software\r\n"
    "[Connection_Info]\r\n"
    "app_type = workstation\r\n"
    "Server = 192.168.0.5\r\n"
    "network_path = \\\\tvmserver\\tvm01\r\n"
    "\r\n"
    "[POS]\r\n"
    "server = 10.9.9.9\r\n"
)


class SettingsDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)

    def _write(self, text: str = SAMPLE, *, bom: bool = False) -> Path:
        path = self.folder / "settings.ini"
        data = text.encode("utf-8")
        if bom:
            data = codecs.BOM_UTF8 + data
        path.write_bytes(data)
        return path

    def test_reads_server_from_connection_info_only(self) -> None:
        path = self._write()
        document = SettingsDocument.read(path)
        self.assertEqual(document.current_server(), "192.168.0.5")
        self.assertTrue(document.section_present())

    def test_update_preserves_comments_casing_and_line_endings(self) -> None:
        path = self._write(bom=True)
        document = SettingsDocument.read(path)
        previous, changed = document.set_server("192.168.2.16")

        self.assertEqual(previous, "192.168.0.5")
        self.assertTrue(changed)
        document.save()

        raw = path.read_bytes()
        self.assertTrue(raw.startswith(codecs.BOM_UTF8))
        text = raw.decode("utf-8-sig")
        self.assertIn("; managed by the hotel software", text)
        self.assertIn("Server = 192.168.2.16", text)
        self.assertIn("server = 10.9.9.9", text)  # POS section must not change
        self.assertIn("network_path = \\\\tvmserver\\tvm01", text)
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertEqual(SettingsDocument.read(path).current_server(), "192.168.2.16")

    def test_same_value_is_not_rewritten(self) -> None:
        path = self._write()
        document = SettingsDocument.read(path)
        document.set_server("192.168.0.5")
        # Server is upper-case "Server" in the sample: no change is expected.
        previous, changed = document.set_server("192.168.0.5")
        self.assertEqual(previous, "192.168.0.5")
        self.assertFalse(changed)

    def test_adds_missing_key_to_existing_section(self) -> None:
        text = "[Connection_Info]\r\napp_type = workstation\r\n\r\n[POS]\r\nportnumber = 1\r\n"
        path = self._write(text)
        document = SettingsDocument.read(path)
        self.assertIsNone(document.current_server())

        _, changed = document.set_server("192.168.0.7")
        self.assertTrue(changed)
        document.save()

        updated = SettingsDocument.read(path)
        self.assertEqual(updated.current_server(), "192.168.0.7")
        self.assertIn("[POS]", updated.text)
        self.assertIn("portnumber = 1", updated.text)

    def test_missing_section_raises(self) -> None:
        path = self._write("[POS]\r\nportnumber = 1\r\n")
        document = SettingsDocument.read(path)
        with self.assertRaises(SettingsError):
            document.set_server("192.168.0.7")

    def test_empty_value_is_rejected(self) -> None:
        path = self._write()
        with self.assertRaises(SettingsError):
            SettingsDocument.read(path).set_server("   ")

    def test_backups_are_created_and_limited(self) -> None:
        path = self._write()
        for index in range(14):
            document = SettingsDocument.read(path)
            document.set_server(f"192.168.0.{index + 1}")
            document.save()

        backups = list((self.folder / "backups").glob("settings-*.ini"))
        self.assertTrue(backups)
        self.assertLessEqual(len(backups), 10)

    def test_legacy_ansi_file_round_trips(self) -> None:
        text = "[Connection_Info]\r\nserver = 192.168.0.5\r\n; caf\u00e9\r\n"
        path = self.folder / "settings.ini"
        path.write_bytes(text.encode("cp1252"))

        document = SettingsDocument.read(path)
        self.assertEqual(document.encoding, "cp1252")
        document.set_server("192.168.0.6")
        document.save()

        raw = path.read_bytes()
        self.assertEqual(raw.decode("cp1252").splitlines()[2], "; caf\u00e9")

    def test_access_denied_fails_once_without_retry_storm(self) -> None:
        path = self._write()
        document = SettingsDocument.read(path)
        document.set_server("192.168.0.7")

        with mock.patch(
            "brickvpn.settings_file.os.open",
            side_effect=PermissionError(13, "Access is denied"),
        ) as open_mock:
            with self.assertRaises(SettingsAccessError) as caught:
                document.save()

        # The old tempfile.mkstemp path retried thousands of times here.
        self.assertEqual(open_mock.call_count, 1)
        self.assertIn("administrator", str(caught.exception).lower())
        self.assertEqual(SettingsDocument.read(path).current_server(), "192.168.0.5")
        self.assertEqual(list(self.folder.glob(".settings-*.tmp")), [])

    def test_backup_failure_leaves_the_file_unchanged(self) -> None:
        path = self._write()
        (self.folder / "backups").write_text("not a folder", encoding="utf-8")
        document = SettingsDocument.read(path)
        document.set_server("192.168.0.7")

        with self.assertRaises(SettingsError) as caught:
            document.save()

        self.assertIn("backup", str(caught.exception).lower())
        self.assertEqual(SettingsDocument.read(path).current_server(), "192.168.0.5")
        self.assertEqual(list(self.folder.glob(".settings-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
