"""Branch catalogue: the editable list of branches and their servers."""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_CHECK_PORTS: tuple[int, ...] = (445, 1433)
DEFAULT_PROBE_TIMEOUT = 2.0

DEFAULT_DOCUMENT: dict[str, Any] = {
    "schema_version": 1,
    "default_check_ports": list(DEFAULT_CHECK_PORTS),
    "probe_timeout_seconds": DEFAULT_PROBE_TIMEOUT,
    "branches": [
        {"id": "wuse", "name": "Wuse", "label": "Wuse (SERVER 1)", "server": "192.168.0.5"},
        {"id": "asokoro", "name": "Asokoro", "label": "Asokoro (SERVER 2)", "server": "192.168.2.16"},
        {"id": "maitama", "name": "Maitama", "label": "Maitama (SERVER 3)", "server": "192.168.0.7"},
    ],
}

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)


class BranchesError(RuntimeError):
    """Raised when branches.json is missing, unreadable or invalid."""


@dataclass(frozen=True)
class Branch:
    """One selectable branch."""

    id: str
    name: str
    server: str
    label: str | None = None
    alias: str | None = None
    check_host: str | None = None
    check_ports: tuple[int, ...] = ()
    notes: str = ""

    @property
    def display_name(self) -> str:
        return self.label or self.name

    @property
    def success_alias(self) -> str:
        """Name used in the "you are now connected" message."""
        return self.alias or self.name

    @property
    def probe_host(self) -> str:
        return self.check_host or self.server


@dataclass(frozen=True)
class BranchCatalog:
    path: Path
    branches: tuple[Branch, ...] = field(default_factory=tuple)
    default_check_ports: tuple[int, ...] = DEFAULT_CHECK_PORTS
    probe_timeout: float = DEFAULT_PROBE_TIMEOUT

    def get(self, branch_id: str) -> Branch | None:
        for branch in self.branches:
            if branch.id == branch_id:
                return branch
        return None

    def find_by_server(self, server: str | None) -> Branch | None:
        if not server:
            return None
        wanted = server.strip().lower()
        for branch in self.branches:
            if branch.server.lower() == wanted:
                return branch
        return None

    def ports_for(self, branch: Branch) -> tuple[int, ...]:
        return branch.check_ports or self.default_check_ports


def valid_host(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(_HOSTNAME_RE.match(value))


def _parse_ports(value: Any, where: str) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, int) and not isinstance(value, bool):
        value = [value]
    if not isinstance(value, list):
        raise BranchesError(f"{where}: check_ports must be a list of TCP ports.")
    ports: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool) or not 1 <= item <= 65535:
            raise BranchesError(f"{where}: invalid TCP port {item!r}.")
        if item not in ports:
            ports.append(item)
    return tuple(ports)


def _parse_timeout(value: Any) -> float:
    """Validate the optional top-level probe timeout in seconds."""
    if value is None:
        return DEFAULT_PROBE_TIMEOUT
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BranchesError(
            '"probe_timeout_seconds" must be a number between 0.5 and 30.'
        )
    timeout = float(value)
    if not 0.5 <= timeout <= 30:
        raise BranchesError(
            f'"probe_timeout_seconds" is {timeout}; use a value between 0.5 and 30.'
        )
    return timeout


def parse_ports_text(text: str) -> tuple[int, ...]:
    """Parse a user-entered list such as ``"445, 1433"`` into TCP ports."""
    cleaned = text.replace(";", ",").replace(" ", ",")
    ports: list[int] = []
    for part in (piece for piece in cleaned.split(",") if piece):
        try:
            port = int(part)
        except ValueError:
            raise BranchesError(f'"{part.strip()}" is not a TCP port number.') from None
        if not 1 <= port <= 65535:
            raise BranchesError(f"{port} is outside the TCP port range 1-65535.")
        if port not in ports:
            ports.append(port)
    return tuple(ports)


def slugify(value: str, existing: set[str]) -> str:
    """Build a stable, unique id from a branch name."""
    base = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "branch"
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _require_str(entry: dict[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BranchesError(f'{where}: "{key}" must be a non-empty string.')
    return value.strip()


def _optional_str(entry: dict[str, Any], key: str, where: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BranchesError(f'{where}: "{key}" must be a string when present.')
    value = value.strip()
    return value or None


def parse_catalog(document: Any, path: Path) -> BranchCatalog:
    """Validate a decoded branches document and build a catalogue."""
    if not isinstance(document, dict):
        raise BranchesError(f"{path.name}: the top level must be a JSON object.")

    default_ports = _parse_ports(document.get("default_check_ports"), "default_check_ports")
    if not default_ports:
        default_ports = DEFAULT_CHECK_PORTS
    probe_timeout = _parse_timeout(document.get("probe_timeout_seconds"))

    raw_branches = document.get("branches")
    if not isinstance(raw_branches, list) or not raw_branches:
        raise BranchesError(f'{path.name}: "branches" must be a non-empty list.')

    branches: list[Branch] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_branches):
        where = f"branches[{index}]"
        if not isinstance(entry, dict):
            raise BranchesError(f"{where}: must be a JSON object.")
        if entry.get("enabled", True) is False:
            continue

        branch_id = _require_str(entry, "id", where)
        if branch_id in seen_ids:
            raise BranchesError(f'{where}: duplicate branch id "{branch_id}".')
        seen_ids.add(branch_id)

        name = _require_str(entry, "name", where)
        server = _require_str(entry, "server", where)
        if not valid_host(server):
            raise BranchesError(f'{where}: "{server}" is not a valid IP address or host name.')

        check_host = _optional_str(entry, "check_host", where)
        if check_host and not valid_host(check_host):
            raise BranchesError(f'{where}: "{check_host}" is not a valid check_host.')

        branches.append(
            Branch(
                id=branch_id,
                name=name,
                server=server,
                label=_optional_str(entry, "label", where),
                alias=_optional_str(entry, "alias", where),
                check_host=check_host,
                check_ports=_parse_ports(entry.get("check_ports"), where),
                notes=_optional_str(entry, "notes", where) or "",
            )
        )

    if not branches:
        raise BranchesError(f"{path.name}: no enabled branches were found.")

    return BranchCatalog(
        path=path,
        branches=tuple(branches),
        default_check_ports=default_ports,
        probe_timeout=probe_timeout,
    )


def _read_document(path: Path) -> dict[str, Any]:
    """Read branches.json and return the decoded top-level object."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise BranchesError(f"{path} was not found.") from exc
    except OSError as exc:
        raise BranchesError(f"Could not read {path}: {exc}") from exc

    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise BranchesError(f"{path.name} is not valid JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise BranchesError(f"{path.name}: the top level must be a JSON object.")
    return document


def load_branches(path: Path) -> BranchCatalog:
    """Read and validate branches.json."""
    return parse_catalog(_read_document(path), path)


def load_document(path: Path) -> dict[str, Any]:
    """Read branches.json without dropping disabled entries.

    The in-app editor works on this document so that branches set to
    ``"enabled": false`` are preserved and can be switched back on.
    """
    document = _read_document(path)
    if not isinstance(document.get("branches"), list):
        raise BranchesError(f'{path.name}: "branches" must be a list.')
    return document


def _ordered_document(document: dict[str, Any]) -> dict[str, Any]:
    """Emit a predictable key order for a hand-editable file."""
    ordered: dict[str, Any] = {"schema_version": document.get("schema_version", 1)}
    if "default_check_ports" in document:
        ordered["default_check_ports"] = document["default_check_ports"]
    if "probe_timeout_seconds" in document:
        ordered["probe_timeout_seconds"] = document["probe_timeout_seconds"]

    entries: list[dict[str, Any]] = []
    for entry in document.get("branches", []):
        if not isinstance(entry, dict):
            entries.append(entry)
            continue
        ordered_entry: dict[str, Any] = {}
        for key in (
            "id",
            "name",
            "label",
            "server",
            "alias",
            "check_host",
            "check_ports",
            "enabled",
            "notes",
        ):
            if key in entry:
                ordered_entry[key] = entry[key]
        entries.append(ordered_entry)
    ordered["branches"] = entries
    return ordered


def save_document(path: Path, document: dict[str, Any]) -> BranchCatalog:
    """Validate a branch document, write it atomically and return the catalogue."""
    catalog = parse_catalog(document, path)
    text = json.dumps(_ordered_document(document), indent=2, ensure_ascii=False) + "\n"
    _atomic_write(path, text)
    _LOGGER.info("Saved branch catalogue at %s", path)
    return catalog


def _atomic_write(path: Path, text: str) -> None:
    """Write text with a uniquely named temp file plus ``os.replace``.

    Only name collisions are retried; access-denied folders fail immediately
    instead of looping like ``tempfile.mkstemp`` can on Windows.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    tmp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(50):
            candidate = path.parent / (
                f".{path.stem}-{os.getpid()}-{secrets.token_hex(4)}.tmp"
            )
            try:
                fd = os.open(candidate, flags, 0o600)
            except FileExistsError:
                continue
            tmp = candidate
            break
        else:
            raise BranchesError(f"Could not create a temporary file in {path.parent}.")

        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
        tmp = None
    except BranchesError:
        raise
    except OSError as exc:
        raise BranchesError(f"Could not write {path}: {exc}") from exc
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


def write_default_branches(path: Path) -> None:
    """Create branches.json with the known branch list (used on first run)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_DOCUMENT, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise BranchesError(f"Could not create {path}: {exc}") from exc
    _LOGGER.info("Created default branch catalogue at %s", path)


def load_or_create(path: Path) -> BranchCatalog:
    """Load branches.json, creating a starter file when it does not exist."""
    if not path.exists():
        write_default_branches(path)
    return load_branches(path)
