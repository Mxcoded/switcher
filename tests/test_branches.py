"""Tests for branch catalogue validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brickvpn.branches import (
    DEFAULT_CHECK_PORTS,
    DEFAULT_DOCUMENT,
    DEFAULT_PROBE_TIMEOUT,
    BranchesError,
    load_branches,
    load_document,
    load_or_create,
    parse_catalog,
    parse_ports_text,
    save_document,
    slugify,
    valid_host,
)


class BranchCatalogueTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)

    def _write(self, document: object) -> Path:
        path = self.folder / "branches.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_default_document_is_valid(self) -> None:
        path = self._write(DEFAULT_DOCUMENT)
        catalog = load_branches(path)
        self.assertEqual(
            [branch.id for branch in catalog.branches], ["wuse", "asokoro", "maitama"]
        )
        self.assertEqual(catalog.default_check_ports, DEFAULT_CHECK_PORTS)
        self.assertEqual(catalog.probe_timeout, DEFAULT_PROBE_TIMEOUT)
        self.assertEqual(catalog.get("asokoro").server, "192.168.2.16")

    def test_disabled_branches_are_skipped(self) -> None:
        document = {
            "branches": [
                {"id": "a", "name": "A", "server": "10.0.0.1"},
                {"id": "b", "name": "B", "server": "10.0.0.2", "enabled": False},
            ]
        }
        catalog = parse_catalog(document, Path("branches.json"))
        self.assertEqual([branch.id for branch in catalog.branches], ["a"])

    def test_duplicate_ids_are_rejected(self) -> None:
        document = {
            "branches": [
                {"id": "a", "name": "A", "server": "10.0.0.1"},
                {"id": "a", "name": "B", "server": "10.0.0.2"},
            ]
        }
        with self.assertRaises(BranchesError):
            parse_catalog(document, Path("branches.json"))

    def test_invalid_server_is_rejected(self) -> None:
        document = {"branches": [{"id": "a", "name": "A", "server": "not a host"}]}
        with self.assertRaises(BranchesError):
            parse_catalog(document, Path("branches.json"))

    def test_hostname_servers_are_allowed(self) -> None:
        document = {"branches": [{"id": "a", "name": "A", "server": "tvm-asokoro.local"}]}
        catalog = parse_catalog(document, Path("branches.json"))
        self.assertEqual(catalog.branches[0].server, "tvm-asokoro.local")

    def test_invalid_ports_are_rejected(self) -> None:
        document = {
            "branches": [{"id": "a", "name": "A", "server": "10.0.0.1", "check_ports": [70000]}]
        }
        with self.assertRaises(BranchesError):
            parse_catalog(document, Path("branches.json"))

    def test_empty_branch_list_is_rejected(self) -> None:
        with self.assertRaises(BranchesError):
            parse_catalog({"branches": []}, Path("branches.json"))

    def test_invalid_json_reports_the_file(self) -> None:
        path = self.folder / "branches.json"
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(BranchesError) as caught:
            load_branches(path)
        self.assertIn("branches.json", str(caught.exception))

    def test_load_or_create_writes_the_default_file(self) -> None:
        path = self.folder / "branches.json"
        catalog = load_or_create(path)
        self.assertTrue(path.is_file())
        self.assertEqual(len(catalog.branches), 3)

    def test_probe_timeout_is_configurable(self) -> None:
        document = {
            "probe_timeout_seconds": 5,
            "branches": [{"id": "a", "name": "A", "server": "10.0.0.1"}],
        }
        catalog = parse_catalog(document, Path("branches.json"))
        self.assertEqual(catalog.probe_timeout, 5.0)

    def test_probe_timeout_is_optional(self) -> None:
        document = {"branches": [{"id": "a", "name": "A", "server": "10.0.0.1"}]}
        catalog = parse_catalog(document, Path("branches.json"))
        self.assertEqual(catalog.probe_timeout, DEFAULT_PROBE_TIMEOUT)

    def test_invalid_probe_timeouts_are_rejected(self) -> None:
        for value in (0.1, 31, 0, -5, True, "2"):
            with self.subTest(value=value):
                document = {
                    "probe_timeout_seconds": value,
                    "branches": [{"id": "a", "name": "A", "server": "10.0.0.1"}],
                }
                with self.assertRaises(BranchesError):
                    parse_catalog(document, Path("branches.json"))

    def test_alias_and_check_host_defaults(self) -> None:
        document = {
            "default_check_ports": [1433],
            "branches": [
                {"id": "a", "name": "Alpha", "server": "10.0.0.1", "alias": "A1"},
            ],
        }
        catalog = parse_catalog(document, Path("branches.json"))
        branch = catalog.branches[0]
        self.assertEqual(branch.success_alias, "A1")
        self.assertEqual(catalog.ports_for(branch), (1433,))
        self.assertEqual(branch.probe_host, "10.0.0.1")


class BranchDocumentTests(unittest.TestCase):
    """The in-app editor reads and rewrites the JSON document."""

    def setUp(self) -> None:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        self.folder = Path(handle.name)

    def _write(self, document: object) -> Path:
        path = self.folder / "branches.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_ports_text_accepts_commas_spaces_and_semicolons(self) -> None:
        self.assertEqual(parse_ports_text("445, 1433"), (445, 1433))
        self.assertEqual(parse_ports_text("445 1433"), (445, 1433))
        self.assertEqual(parse_ports_text("445;1433;445"), (445, 1433))
        self.assertEqual(parse_ports_text(""), ())

    def test_ports_text_rejects_bad_values(self) -> None:
        for text in ("445, abc", "0", "70000", "-1"):
            with self.subTest(text=text):
                with self.assertRaises(BranchesError):
                    parse_ports_text(text)

    def test_slugify_builds_unique_ids(self) -> None:
        self.assertEqual(slugify("Wuse Branch!", set()), "wuse-branch")
        self.assertEqual(slugify("Wuse Branch!", {"wuse-branch"}), "wuse-branch-2")
        self.assertEqual(slugify("!!!", set()), "branch")

    def test_valid_host_accepts_addresses_and_names(self) -> None:
        self.assertTrue(valid_host("192.168.2.16"))
        self.assertTrue(valid_host("tvm-asokoro.local"))
        self.assertFalse(valid_host("not a host"))
        self.assertFalse(valid_host(""))

    def test_document_round_trip_keeps_disabled_entries(self) -> None:
        path = self._write(
            {
                "schema_version": 1,
                "default_check_ports": [445, 1433],
                "probe_timeout_seconds": 3,
                "branches": [
                    {"id": "a", "name": "Alpha", "server": "10.0.0.1"},
                    {
                        "id": "b",
                        "name": "Beta",
                        "server": "10.0.0.2",
                        "enabled": False,
                        "notes": "closed for now",
                    },
                ],
            }
        )

        document = load_document(path)
        self.assertEqual(len(document["branches"]), 2)
        document["branches"][0]["name"] = "Alpha renamed"
        document["branches"][1]["enabled"] = True
        catalog = save_document(path, document)

        self.assertEqual([branch.id for branch in catalog.branches], ["a", "b"])
        reloaded = load_document(path)
        self.assertEqual(reloaded["probe_timeout_seconds"], 3)
        self.assertEqual(reloaded["branches"][0]["name"], "Alpha renamed")
        # Keys are written in a stable, hand-editable order.
        first = reloaded["branches"][0]
        self.assertEqual(list(first), ["id", "name", "server"])

    def test_save_document_validates_before_writing(self) -> None:
        path = self._write(DEFAULT_DOCUMENT)
        before = path.read_bytes()
        document = load_document(path)
        document["branches"][0]["server"] = "not a host"

        with self.assertRaises(BranchesError):
            save_document(path, document)

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
