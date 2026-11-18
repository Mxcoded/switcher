"""Tests for offline licence verification and the expiry policy."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from brickvpn import licensing
from brickvpn.licensing import License, LicenseError, canonical_payload
from tools import issue_license

# Test-only RSA-2048 key. Never used to issue real licences.
TEST_N = int(
    "5e91461bba7fa28a0892e55bd141f246e03a75dc20bf1b4f3c70fc90331cd4cc"
    "07a28a757e90075c446f7e4f6b79fd64bcd36f3ab4d39924eb9e5f77f7a6bd8"
    "5d430aeb5a47f9edebdc9d3d4a482a2808fd25e18eb467325d1d99d7bfeb8f2"
    "293805956310476c9f8e41110233acbfdf905a1163c15d2aec3ed49660f69a8e"
    "116568247e2a2a37ba738c061b2fd930326abb0c55b91c58759981c1a6c0f7a"
    "42c80c0b31f15e10f9584fa4f40e8425222c1bb210c16b3029ae2a4995879c8"
    "c0e7d87ce2c05196bd546485119bcf583005a3d9f4895f8b5bfb651fb1a4dc6"
    "2c6929e1fc2d7f813a81421dbb6b31da0ebedea6626802f655cbdd035cdbbe8"
    "ebda6d",
    16,
)
TEST_E = 65537
TEST_D = int(
    "1fcbb289d22be5e7893872bb6b6143e786aec13ff116b044f4ea7c50b38ec711"
    "8ea39cf0224ca4dce5f9a2bb6b4489e91bffef0f0b0b761b4ec9620a010f63f"
    "ba23b781284ab902c0e1dd5065305c5437a97dda17d41a3a79ca61168465dc2"
    "b60f2af96e6463cf66da3a905070356e11ea040e82bed9e77ba5286f234ce6e"
    "c4b0d806894f1267077b9ab7de97ab54ba344055c9816feab17bc60728be0f6"
    "acf8f4afdf77d53f901632cb927bea13994617f1b3d305dbf231cc501bb07a3"
    "84d9b8121988ffc831de91515f728dccda622c03109cc241297301a88d1799f"
    "f35b308fa20b935e6e928810fb7ed729578f390321fc61aa3dff311900ab0c9"
    "50af755",
    16,
)
SIGNATURE_BYTES = 256
DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def sign(payload: dict, *, n: int = TEST_N, d: int = TEST_D) -> str:
    """Sign a payload exactly as the vendor tool does (test helper)."""
    digest = hashlib.sha256(canonical_payload(payload)).digest()
    padding = SIGNATURE_BYTES - 3 - len(DIGEST_INFO) - len(digest)
    encoded = b"\x00\x01" + b"\xff" * padding + b"\x00" + DIGEST_INFO + digest
    value = pow(int.from_bytes(encoded, "big"), d, n)
    return base64.b64encode(value.to_bytes(SIGNATURE_BYTES, "big")).decode("ascii")


def payload(**overrides) -> dict:
    base = {
        "format": 1,
        "license_id": "TEST-001",
        "customer": "Test Hotels Ltd",
        "site": "Abuja",
        "issued": "2026-01-01",
        "expires": "2026-07-01",
        "features": ["branch-switching"],
        "seats": 10,
        "grace_days": 14,
        "product": "Switcher",
    }
    base.update(overrides)
    return base


def write_license(folder: Path, body: dict, signature: str | None = None) -> Path:
    target = folder / "license.json"
    target.write_text(
        json.dumps(
            {
                "format": "switcher-licence/1",
                "payload": body,
                "signature": sign(body) if signature is None else signature,
            }
        ),
        encoding="utf-8",
    )
    return target


def make_license(**overrides) -> License:
    values = {
        "license_id": "TEST-001",
        "customer": "Test Hotels Ltd",
        "site": "Abuja",
        "issued": date(2026, 1, 1),
        "expires": date(2026, 7, 1),
        "features": ("branch-switching",),
        "seats": 10,
        "grace_days": 14,
    }
    values.update(overrides)
    return License(**values)


class VerificationTests(unittest.TestCase):
    def test_signed_licence_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(Path(folder), payload())
            license = licensing.load_license(
                path, modulus=TEST_N, exponent=TEST_E
            )
        self.assertEqual(license.customer, "Test Hotels Ltd")
        self.assertEqual(license.expires, date(2026, 7, 1))
        self.assertEqual(license.grace_days, 14)

    def test_tampering_with_the_customer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            body = payload()
            path = write_license(Path(folder), body)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["customer"] = "Someone Else"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(LicenseError):
                licensing.load_license(path, modulus=TEST_N, exponent=TEST_E)

    def test_tampering_with_the_expiry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(Path(folder), payload())
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["expires"] = "2036-07-01"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(LicenseError):
                licensing.load_license(path, modulus=TEST_N, exponent=TEST_E)

    def test_signature_from_another_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(Path(folder), payload())
            with self.assertRaises(LicenseError):
                licensing.load_license(path)  # production public key
            with self.assertRaises(LicenseError):
                licensing.load_license(path, modulus=TEST_N + 2, exponent=TEST_E)

    def test_wrong_product_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(Path(folder), payload(product="Other App"))
            with self.assertRaises(LicenseError):
                licensing.load_license(path, modulus=TEST_N, exponent=TEST_E)

    def test_expiry_before_issue_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(
                Path(folder),
                payload(issued="2026-07-01", expires="2026-01-01"),
            )
            with self.assertRaises(LicenseError):
                licensing.load_license(path, modulus=TEST_N, exponent=TEST_E)

    def test_discover_reports_a_missing_explicit_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            license, path, error = licensing.discover(Path(folder) / "license.json")
        self.assertIsNone(license)
        self.assertIsNone(path)
        self.assertIn("not found", error)


class PolicyTests(unittest.TestCase):
    def test_active_licence_has_no_banner(self) -> None:
        license = make_license(expires=date(2026, 12, 31))
        status = licensing.evaluate(license, date(2026, 7, 1))
        self.assertEqual(status.state, "active")
        self.assertTrue(status.can_switch)
        self.assertEqual(status.message, "")

    def test_thirty_day_reminder(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 6, 1))
        self.assertEqual(status.state, "expiring")
        self.assertEqual(status.days_left, 30)
        self.assertTrue(status.can_switch)
        self.assertIn("30 day", status.message)

    def test_last_week_is_a_warning(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 6, 24))
        self.assertEqual(status.state, "expiring")
        self.assertEqual(status.level, "warning")

    def test_expiry_day_still_allows_switching(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 1))
        self.assertEqual(status.state, "expiring")
        self.assertEqual(status.days_left, 0)
        self.assertTrue(status.can_switch)

    def test_grace_keeps_switching_available(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 10))
        self.assertEqual(status.state, "grace")
        self.assertTrue(status.can_switch)
        self.assertIn("grace", status.message)

    def test_last_grace_day_still_allows_switching(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 15))
        self.assertEqual(status.state, "grace")
        self.assertTrue(status.can_switch)
        self.assertIn("0 day", status.message)

    def test_after_grace_switching_is_disabled(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 16))
        self.assertEqual(status.state, "expired")
        self.assertFalse(status.can_switch)
        self.assertEqual(status.level, "error")

    def test_missing_licence_disables_switching(self) -> None:
        status = licensing.status_from_error(None, "No licence file was found.")
        self.assertEqual(status.state, "missing")
        self.assertFalse(status.can_switch)
        self.assertIn("No licence file was found", status.message)
        self.assertIn("Switching is disabled", status.message)

    def test_invalid_licence_names_the_file(self) -> None:
        status = licensing.status_from_error(
            Path("C:/Apps/Switcher/license.json"), "the signature does not match."
        )
        self.assertEqual(status.state, "invalid")
        self.assertFalse(status.can_switch)
        self.assertIn("license.json", status.message)


class CountdownTests(unittest.TestCase):
    def test_active_licence_counts_the_days_left(self) -> None:
        license = make_license(expires=date(2026, 12, 31))
        status = licensing.evaluate(license, date(2026, 7, 1))
        self.assertEqual(licensing.countdown_text(status), "183 days left")

    def test_single_day_is_not_plural(self) -> None:
        license = make_license(expires=date(2026, 7, 2))
        status = licensing.evaluate(license, date(2026, 7, 1))
        self.assertEqual(licensing.countdown_text(status), "1 day left")

    def test_expiry_day_is_named(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 1))
        self.assertEqual(
            licensing.countdown_text(status), "Expires today (01 Jul 2026)"
        )

    def test_grace_shows_the_remaining_days(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 10))
        self.assertEqual(
            licensing.countdown_text(status),
            "Expired 01 Jul 2026; 5 days of grace left",
        )

    def test_expired_asks_for_a_renewal(self) -> None:
        license = make_license(expires=date(2026, 7, 1))
        status = licensing.evaluate(license, date(2026, 7, 16))
        self.assertEqual(
            licensing.countdown_text(status), "Expired 01 Jul 2026; renew to switch"
        )

    def test_missing_licence_has_no_countdown(self) -> None:
        status = licensing.status_from_error(None, "No licence file was found.")
        self.assertEqual(licensing.countdown_text(status), "No valid licence")


class ClockTests(unittest.TestCase):
    def test_normal_clock_is_used(self) -> None:
        today, rollback = licensing.resolve_today(date(2026, 7, 1), date(2026, 6, 30))
        self.assertEqual(today, date(2026, 7, 1))
        self.assertFalse(rollback)

    def test_small_timezone_step_is_tolerated(self) -> None:
        today, rollback = licensing.resolve_today(date(2026, 6, 29), date(2026, 6, 30))
        self.assertFalse(rollback)

    def test_large_rollback_uses_the_last_seen_date(self) -> None:
        today, rollback = licensing.resolve_today(date(2025, 1, 1), date(2026, 6, 30))
        self.assertTrue(rollback)
        self.assertEqual(today, date(2026, 6, 30))


class IssueToolTests(unittest.TestCase):
    def test_six_month_term_is_added(self) -> None:
        self.assertEqual(
            issue_license.add_months(date(2026, 1, 31), 6), date(2026, 7, 31)
        )
        self.assertEqual(
            issue_license.add_months(date(2026, 8, 31), 6), date(2027, 2, 28)
        )

    def test_tool_signature_is_accepted_by_the_app(self) -> None:
        body = payload()
        signature = issue_license.sign_payload(body, (TEST_N, TEST_E, TEST_D))
        with tempfile.TemporaryDirectory() as folder:
            path = write_license(Path(folder), body, signature)
            license = licensing.load_license(path, modulus=TEST_N, exponent=TEST_E)
        self.assertEqual(license.license_id, "TEST-001")


if __name__ == "__main__":
    unittest.main()
