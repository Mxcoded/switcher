"""Issue a signed Switcher licence file (vendor only).

The private key is the JSON file produced by ``tools/generate_keys.py``. The
resulting ``license.json`` is copied next to ``Switcher.exe`` (or into
``%PROGRAMDATA%\\Afriwave\\Switcher``). It is signed, not encrypted: a site can
read it, but cannot change the customer, dates or seats.

    python tools/issue_license.py --key keys/private_key.json \
        --id AFR-2026-001 --customer "Brickspoint Technologies" \
        --months 6 --seats 50 --out license.json
"""

from __future__ import annotations

import argparse
import base64
import calendar
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brickvpn.licensing import canonical_payload  # noqa: E402

_DIGEST_INFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")


def add_months(start: date, months: int) -> date:
    """Return *start* shifted by whole months, clamping the day."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def load_private_key(path: Path) -> tuple[int, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return int(data["n"], 16), int(data["e"]), int(data["d"], 16)


def sign_payload(payload: dict, key: tuple[int, int, int]) -> str:
    """Sign the canonical payload with RSA PKCS#1 v1.5 and SHA-256."""
    modulus, _exponent, private_exponent = key
    size = (modulus.bit_length() + 7) // 8
    digest = hashlib.sha256(canonical_payload(payload)).digest()
    padding = size - 3 - len(_DIGEST_INFO_SHA256) - len(digest)
    if padding < 8:
        raise ValueError("The RSA key is too small to sign this payload.")
    encoded = (
        b"\x00\x01" + b"\xff" * padding + b"\x00" + _DIGEST_INFO_SHA256 + digest
    )
    signature = pow(int.from_bytes(encoded, "big"), private_exponent, modulus)
    return base64.b64encode(signature.to_bytes(size, "big")).decode("ascii")


def build_payload(args: argparse.Namespace) -> dict:
    issued = date.fromisoformat(args.issued) if args.issued else date.today()
    expires = (
        date.fromisoformat(args.expires)
        if args.expires
        else add_months(issued, args.months)
    )
    if expires <= issued:
        raise SystemExit("The expiry date must be after the issue date.")
    return {
        "format": 1,
        "license_id": args.id,
        "customer": args.customer,
        "site": args.site,
        "issued": issued.isoformat(),
        "expires": expires.isoformat(),
        "features": [item.strip() for item in args.features.split(",") if item.strip()],
        "seats": args.seats,
        "grace_days": args.grace_days,
        "product": args.product,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue a signed Switcher licence.")
    parser.add_argument("--key", required=True, help="Private key JSON from generate_keys.py.")
    parser.add_argument("--id", required=True, help="Licence identifier, e.g. AFR-2026-001.")
    parser.add_argument("--customer", required=True, help="Licensed organisation.")
    parser.add_argument("--site", default="All sites", help="Site or estate description.")
    parser.add_argument("--issued", help="Issue date (YYYY-MM-DD, default: today).")
    parser.add_argument(
        "--expires", help="Expiry date (YYYY-MM-DD, default: issue date + --months)."
    )
    parser.add_argument("--months", type=int, default=6, help="Term in months (default: 6).")
    parser.add_argument("--seats", type=int, default=0, help="Workstation allowance (0 = site-wide).")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=14,
        help="Days of grace after expiry (default: 14).",
    )
    parser.add_argument(
        "--features",
        default="branch-switching",
        help="Comma-separated feature names (default: branch-switching).",
    )
    parser.add_argument(
        "--product", default="Switcher", help="Product name recorded in the licence."
    )
    parser.add_argument("--out", default="license.json", help="Output file.")
    args = parser.parse_args(argv)

    key = load_private_key(Path(args.key).expanduser())
    payload = build_payload(args)
    document = {
        "format": "switcher-licence/1",
        "payload": payload,
        "signature": sign_payload(payload, key),
    }

    target = Path(args.out).expanduser()
    target.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Licence written to {target}")
    print(f"  Customer: {payload['customer']} ({payload['site']})")
    print(f"  Valid:    {payload['issued']} to {payload['expires']} ({args.months} months)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
