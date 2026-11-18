"""Offline licence verification and the 6-month renewal policy.

Licences are issued by the vendor as a small JSON document signed with
RSA-2048 (PKCS#1 v1.5, SHA-256). Only the public key ships with the app, so a
site can read a licence but cannot forge it, move the expiry date or change the
customer. Verification uses only the standard library.

Policy: warnings at 30, 14 and 7 days; a 14-day grace period after expiry;
after grace the app still shows the current server and runs connection tests,
but refuses to write ``settings.ini`` until a renewed licence is installed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

from .branding import APP_NAME, COMPANY, STATE_VENDOR
from .paths import app_dir, state_dir

_LOGGER = logging.getLogger(__name__)

LICENSE_FILENAME = "license.json"
REMINDER_DAYS = 30
GRACE_DAYS = 14

# RSA-2048 public key. Replace both values (and re-issue every licence) when
# rotating the signing key. The private half lives offline, never in the repo.
PUBLIC_KEY_N = int(
    "7c787f8a1d28770b9a27da318ac94821656d64c4f424b4e689828e5d1c6a096a"
    "590a325adfebd6fc5f1fd4369836ba5c7a2e0dfa83f27148138b411d8b4c3df2"
    "4f94eadcee90111aa6bb8651e47edc1d990928ab0f5db0334c0b36a861fe2c5a"
    "5ffec210a87fb8fabeccbdca89e3dfd503802d0f5da00d50d582575cf87aa24"
    "f219f51a5856fda1225a51f730ce9002e034c0a4057f944e09cb2169f1910f2"
    "575d9b5c199a7a58f4b4e7d6a7aa8b0523605b5dc899f94e843bf58d55a3a6"
    "81b0cac72e64b362ccba575164ef6f5d6038771af457aa4acca81ae4ffe71f7"
    "e2104e413a3b2cd7f270f761219d3e548067bb3c3f5be4c7e20394a875cfdbe"
    "95fb3d",
    16,
)
PUBLIC_KEY_E = 65537
SIGNATURE_BYTES = (PUBLIC_KEY_N.bit_length() + 7) // 8

_DIGEST_INFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")


class LicenseError(ValueError):
    """Raised when a licence file is unreadable, malformed or not signed."""


@dataclass(frozen=True)
class License:
    """The verified contents of a licence file."""

    license_id: str
    customer: str
    site: str
    issued: date
    expires: date
    features: tuple[str, ...] = ()
    seats: int = 0
    grace_days: int = GRACE_DAYS

    @property
    def days_left(self) -> int:
        return (self.expires - date.today()).days


@dataclass(frozen=True)
class LicenseStatus:
    """The licence as it applies today, ready for the UI."""

    state: str  # active | expiring | grace | expired | missing | invalid
    license: License | None
    days_left: int | None
    message: str
    can_switch: bool
    level: str  # ok | info | warning | error


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    """Return the exact bytes that are signed and verified."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def verify_signature(
    payload: bytes,
    signature: bytes,
    *,
    modulus: int = PUBLIC_KEY_N,
    exponent: int = PUBLIC_KEY_E,
) -> bool:
    """Check an RSA PKCS#1 v1.5 / SHA-256 signature without third-party code."""
    size = (modulus.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    value = int.from_bytes(signature, "big")
    if value >= modulus:
        return False

    padding = size - 3 - len(_DIGEST_INFO_SHA256) - hashlib.sha256().digest_size
    if padding < 8:
        return False
    expected = (
        b"\x00\x01"
        + b"\xff" * padding
        + b"\x00"
        + _DIGEST_INFO_SHA256
        + hashlib.sha256(payload).digest()
    )
    encoded = pow(value, exponent, modulus).to_bytes(size, "big")
    return hmac.compare_digest(encoded, expected)


def load_license(
    path: Path,
    *,
    modulus: int = PUBLIC_KEY_N,
    exponent: int = PUBLIC_KEY_E,
) -> License:
    """Read, verify and parse ``license.json``; raise ``LicenseError`` on problems."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LicenseError(f"the file could not be read ({exc.strerror or exc}).") from exc
    except ValueError as exc:
        raise LicenseError("the file is not valid JSON.") from exc

    if not isinstance(document, dict):
        raise LicenseError("the file does not contain a licence document.")
    payload = document.get("payload")
    signature_text = document.get("signature")
    if not isinstance(payload, dict):
        raise LicenseError("the signed payload is missing.")
    if not isinstance(signature_text, str):
        raise LicenseError("the signature is missing.")

    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (ValueError, TypeError) as exc:
        raise LicenseError("the signature is not valid base64.") from exc

    if not verify_signature(
        canonical_payload(payload), signature, modulus=modulus, exponent=exponent
    ):
        raise LicenseError("the signature does not match this payload.")
    return _parse_payload(payload)


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LicenseError(f"the '{key}' field is missing.")
    return value.strip()


def _parse_date(payload: Mapping[str, Any], key: str) -> date:
    value = payload.get(key)
    if not isinstance(value, str):
        raise LicenseError(f"the '{key}' date is missing.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise LicenseError(f"the '{key}' date is not YYYY-MM-DD.") from exc


def _parse_payload(payload: Mapping[str, Any]) -> License:
    product = payload.get("product")
    if product is not None and product != APP_NAME:
        raise LicenseError(f"the licence was issued for {product!r}, not {APP_NAME!r}.")

    issued = _parse_date(payload, "issued")
    expires = _parse_date(payload, "expires")
    if expires <= issued:
        raise LicenseError("the expiry date is not after the issue date.")

    features_value = payload.get("features", [])
    if not isinstance(features_value, list) or not all(
        isinstance(item, str) for item in features_value
    ):
        raise LicenseError("the 'features' field must be a list of names.")

    seats = payload.get("seats", 0)
    if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
        raise LicenseError("the 'seats' field must be zero or a positive number.")

    grace_days = payload.get("grace_days", GRACE_DAYS)
    if (
        isinstance(grace_days, bool)
        or not isinstance(grace_days, int)
        or not 0 <= grace_days <= 365
    ):
        raise LicenseError("the 'grace_days' field must be between 0 and 365.")

    site = payload.get("site", "")
    if not isinstance(site, str):
        raise LicenseError("the 'site' field must be text.")

    return License(
        license_id=_required_text(payload, "license_id"),
        customer=_required_text(payload, "customer"),
        site=site.strip(),
        issued=issued,
        expires=expires,
        features=tuple(item.strip() for item in features_value if item.strip()),
        seats=seats,
        grace_days=grace_days,
    )


def candidate_paths(explicit: Path | None = None) -> list[Path]:
    """Likely licence locations, in priority order."""
    if explicit is not None:
        return [Path(explicit).expanduser()]

    candidates: list[Path] = [app_dir() / LICENSE_FILENAME]

    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        candidates.append(
            Path(program_data) / STATE_VENDOR / APP_NAME / LICENSE_FILENAME
        )
    candidates.append(state_dir() / LICENSE_FILENAME)

    seen: set[str] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            ordered.append(candidate)
    return ordered


def discover(
    explicit: Path | None = None,
) -> tuple[License | None, Path | None, str | None]:
    """Find and verify the first licence file.

    Returns ``(license, path, error)``. When a file exists but fails
    verification, ``path`` is set and ``error`` explains why.
    """
    for path in candidate_paths(explicit):
        if not path.is_file():
            continue
        try:
            return load_license(path), path, None
        except LicenseError as exc:
            return None, path, str(exc)
    if explicit is not None:
        return None, None, f"The licence file {Path(explicit).expanduser()} was not found."
    return (
        None,
        None,
        f"No licence file was found (expected {LICENSE_FILENAME} next to {APP_NAME}.exe).",
    )


def _format_date(value: date) -> str:
    return value.strftime("%d %b %Y")


def evaluate(
    license: License | None,
    today: date,
    *,
    reminder_days: int = REMINDER_DAYS,
    grace_days: int | None = None,
) -> LicenseStatus:
    """Turn a verified licence into today's status."""
    if license is None:
        return status_from_error(None, "No licence is installed.")

    grace = license.grace_days if grace_days is None else grace_days
    days_left = (license.expires - today).days

    if today > license.expires:
        grace_ends = license.expires + timedelta(days=grace)
        if today <= grace_ends:
            remaining = (grace_ends - today).days
            message = (
                f"Licence expired on {_format_date(license.expires)}. "
                f"{remaining} day(s) of grace remain; switching stays available "
                f"until {_format_date(grace_ends)}. Contact {COMPANY} to renew."
            )
            return LicenseStatus("grace", license, days_left, message, True, "warning")
        message = (
            f"Licence expired on {_format_date(license.expires)} and the grace "
            f"period has ended. Switching is disabled; viewing and connection "
            f"tests remain available. Contact {COMPANY} to renew."
        )
        return LicenseStatus("expired", license, days_left, message, False, "error")

    if days_left <= reminder_days:
        if days_left == 0:
            message = (
                f"Licence expires today ({_format_date(license.expires)}). "
                f"Contact {COMPANY} to renew."
            )
        else:
            message = (
                f"Licence expires in {days_left} day(s), on "
                f"{_format_date(license.expires)}. Contact {COMPANY} to renew."
            )
        return LicenseStatus(
            "expiring", license, days_left, message, True, reminder_level(days_left)
        )

    return LicenseStatus("active", license, days_left, "", True, "ok")


def status_from_error(path: Path | None, reason: str) -> LicenseStatus:
    """Build the missing/invalid status shown by the UI."""
    state = "missing" if path is None else "invalid"
    prefix = f"{path.name}: " if path is not None else ""
    message = (
        f"{prefix}{reason} Switching is disabled until a valid licence is "
        f"installed. Contact {COMPANY}."
    )
    return LicenseStatus(state, None, None, message, False, "error")


def resolve_today(today: date, last_seen: date | None) -> tuple[date, bool]:
    """Detect a backwards clock and return the date the licence is judged by.

    When the machine clock is more than a day behind the most recent launch,
    the later date is used so rolling the clock back cannot extend a licence.
    """
    if last_seen is None:
        return today, False
    if today < last_seen - timedelta(days=1):
        return last_seen, True
    return max(today, last_seen), False


def countdown_text(status: LicenseStatus) -> str:
    """Short renewal countdown for the status card and licence dialog."""
    license = status.license
    if license is None:
        return "No valid licence"

    days = status.days_left
    if days is None:
        days = (license.expires - date.today()).days
    expiry = _format_date(license.expires)

    if status.state == "grace":
        remaining = max(license.grace_days + days, 0)
        unit = "day" if remaining == 1 else "days"
        return f"Expired {expiry}; {remaining} {unit} of grace left"
    if status.state == "expired":
        return f"Expired {expiry}; renew to switch"
    if days <= 0:
        return f"Expires today ({expiry})"
    unit = "day" if days == 1 else "days"
    return f"{days} {unit} left"


def describe(license: License) -> str:
    """Readable summary for the Help > Licence dialog."""
    features = ", ".join(license.features) if license.features else "Branch switching"
    seats = str(license.seats) if license.seats else "Site-wide"
    return "\n".join(
        [
            f"Licence ID: {license.license_id}",
            f"Customer: {license.customer}",
            f"Site: {license.site or 'All sites'}",
            f"Issued: {_format_date(license.issued)}",
            f"Expires: {_format_date(license.expires)}",
            f"Seats: {seats}",
            f"Features: {features}",
        ]
    )


def reminder_level(days_left: int) -> str:
    """Return the banner level for an upcoming expiry (30/14/7-day cadence)."""
    if days_left <= 14:
        return "warning"
    return "info"
