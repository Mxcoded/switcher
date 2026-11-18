"""Generate an RSA-2048 signing keypair for Switcher licences (vendor only).

Run this once, keep the private key offline, and embed the printed public
modulus in ``brickvpn/licensing.py``. Rotating the key means changing that
constant and re-issuing every licence.

    python tools/generate_keys.py --out keys/private_key.json
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from math import gcd
from pathlib import Path

E = 65537


def _small_primes(limit: int = 2000) -> list[int]:
    sieve = bytearray([1]) * limit
    sieve[0:2] = b"\x00\x00"
    for number in range(2, int(limit**0.5) + 1):
        if sieve[number]:
            sieve[number * number : limit : number] = b"\x00" * len(
                range(number * number, limit, number)
            )
    return [number for number in range(limit) if sieve[number]]


_PRIMES = _small_primes()


def is_probable_prime(number: int, rounds: int = 40) -> bool:
    """Miller-Rabin test with small-prime trial division."""
    if number < 2:
        return False
    for prime in _PRIMES:
        if number % prime == 0:
            return number == prime

    odd = number - 1
    shifts = 0
    while odd % 2 == 0:
        odd //= 2
        shifts += 1

    for _ in range(rounds):
        base = secrets.randbelow(number - 3) + 2
        value = pow(base, odd, number)
        if value in (1, number - 1):
            continue
        for _ in range(shifts - 1):
            value = pow(value, 2, number)
            if value == number - 1:
                break
        else:
            return False
    return True


def generate_prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if is_probable_prime(candidate):
            return candidate


def generate_keypair(bits: int = 2048) -> dict[str, int]:
    while True:
        p = generate_prime(bits // 2)
        q = generate_prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if gcd(E, phi) == 1:
            break
    modulus = p * q
    private_exponent = pow(E, -1, phi)
    return {"n": modulus, "e": E, "d": private_exponent}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Switcher licence keypair.")
    parser.add_argument(
        "--out",
        default="keys/private_key.json",
        help="Where to write the private key (default: keys/private_key.json).",
    )
    parser.add_argument("--bits", type=int, default=2048, help="Modulus size (default: 2048).")
    args = parser.parse_args(argv)

    print(f"Generating a {args.bits}-bit keypair; this can take a moment...", file=sys.stderr)
    key = generate_keypair(args.bits)

    target = Path(args.out).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({name: format(value, "x") for name, value in key.items()}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    print(f"Private key written to {target}")
    print("Keep this file offline and out of version control.")
    print()
    print("Add these values to brickvpn/licensing.py:")
    print(f'PUBLIC_KEY_N = int("{format(key["n"], "x")}", 16)')
    print(f"PUBLIC_KEY_E = {key['e']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
