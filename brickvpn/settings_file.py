"""Read and update ``settings.ini`` without disturbing the rest of the file.

The hotel software owns this file, so the editor is deliberately conservative:

* only the ``server`` key inside ``[Connection_Info]`` is replaced;
* comments, key casing, spacing, line endings and a UTF-8 BOM are preserved;
* the previous version is copied into ``backups/`` before every change;
* the new content is written atomically (temp file + ``os.replace``).
"""

from __future__ import annotations

import codecs
import logging
import os
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

SECTION = "Connection_Info"
KEY = "server"
BACKUP_DIR = "backups"
BACKUP_KEEP = 10

_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
_ENTRY_RE = re.compile(
    r"^(?P<prefix>\s*" + re.escape(KEY) + r"\s*[=:]\s*)(?P<value>.*?)(?P<trailing>[ \t]*)$",
    re.IGNORECASE,
)


class SettingsError(RuntimeError):
    """Raised when settings.ini cannot be parsed or updated."""


class SettingsAccessError(SettingsError):
    """Raised when Windows refuses read or write access to settings.ini."""


@dataclass
class SettingsDocument:
    path: Path
    text: str
    encoding: str = "utf-8"
    bom: bool = False

    @classmethod
    def read(cls, path: Path) -> "SettingsDocument":
        path = Path(path)
        try:
            raw = path.read_bytes()
        except PermissionError as exc:
            raise SettingsAccessError(
                f"Windows refused read access to {path}. "
                "Run the selector as administrator, or use an account that can read that folder."
            ) from exc
        except OSError as exc:
            raise SettingsError(f"Could not read {path}: {exc}") from exc

        bom = raw.startswith(codecs.BOM_UTF8)
        try:
            text = raw.decode("utf-8-sig")
            encoding = "utf-8"
        except UnicodeDecodeError:
            # Old Windows deployments sometimes store ANSI text.
            try:
                text = raw.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise SettingsError(f"{path} is not readable as UTF-8 or ANSI text.") from exc
            encoding = "cp1252"

        return cls(path=path, text=text, encoding=encoding, bom=bom)

    # -- inspection ---------------------------------------------------

    def _lines(self) -> list[str]:
        return self.text.splitlines(keepends=True)

    def _newline(self) -> str:
        return "\r\n" if "\r\n" in self.text else "\n"

    def _locate(self) -> tuple[int | None, int | None]:
        """Return ``(header_index, key_index)`` for [Connection_Info]."""
        in_section = False
        header: int | None = None
        for index, line in enumerate(self._lines()):
            body = line.rstrip("\r\n")
            match = _SECTION_RE.match(body)
            if match:
                in_section = match.group("name").strip().lower() == SECTION.lower()
                if in_section:
                    header = index
                continue
            if in_section and _ENTRY_RE.match(body):
                return header, index
        return header, None

    def section_present(self) -> bool:
        return self._locate()[0] is not None

    def current_server(self) -> str | None:
        _, key_index = self._locate()
        if key_index is None:
            return None
        entry = _ENTRY_RE.match(self._lines()[key_index].rstrip("\r\n"))
        if entry is None:
            return None
        value = entry.group("value").strip()
        return value or None

    # -- editing ------------------------------------------------------

    def set_server(self, server: str) -> tuple[str | None, bool]:
        """Set the server value.

        Returns ``(previous_value, changed)``. The document is only rewritten
        in memory; call :meth:`save` to persist it.
        """
        server = str(server).strip()
        if not server:
            raise SettingsError("Refusing to write an empty server address.")

        lines = self._lines()
        newline = self._newline()
        header_index, key_index = self._locate()

        if header_index is None:
            raise SettingsError(
                f'Section [{SECTION}] was not found in {self.path.name}. '
                "The hotel software may not be installed in this folder."
            )

        if key_index is not None:
            line = lines[key_index]
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            entry = _ENTRY_RE.match(body)
            if entry is None:  # pragma: no cover - _locate already matched
                raise SettingsError(f"Could not parse the {KEY} line in {self.path.name}.")
            previous = entry.group("value").strip() or None
            if previous == server:
                return previous, False
            lines[key_index] = f"{entry.group('prefix')}{server}{entry.group('trailing')}{ending}"
        else:
            previous = None
            if not lines[header_index].endswith(("\n", "\r")):
                lines[header_index] += newline
            lines.insert(header_index + 1, f"{KEY} = {server}{newline}")

        self.text = "".join(lines)
        return previous, True

    # -- persistence --------------------------------------------------

    def save(self) -> Path | None:
        """Write the document atomically, returning the backup path if any.

        A backup is mandatory: if it cannot be created, the original file is
        left untouched. Access-denied folders fail immediately rather than
        retrying, so an administrator-protected hotel folder cannot freeze the
        window.
        """
        data = self.text.encode(self.encoding)
        if self.bom:
            data = codecs.BOM_UTF8 + data

        tmp_path: Path | None = None
        backup: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = _create_temp(self.path)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)

            try:
                if self.path.exists():
                    backup = _backup(self.path)
            except OSError as exc:
                raise SettingsError(
                    f"Could not create a backup of {self.path.name} in "
                    f"{self.path.parent / BACKUP_DIR}. The file was not changed. ({exc})"
                ) from exc

            os.replace(tmp_path, self.path)
            tmp_path = None
        except PermissionError as exc:
            _LOGGER.error("Access denied while writing %s", self.path)
            raise SettingsAccessError(
                f"Windows refused write access to {self.path}.\n\n"
                "Run BrickVPN Branch Selector as administrator (right-click the app, "
                'then choose "Run as administrator"), or ask IT to grant your account '
                f"write access to {self.path.parent}."
            ) from exc
        except SettingsError:
            raise
        except OSError as exc:
            _LOGGER.error("Could not write %s: %s", self.path, exc)
            raise SettingsError(f"Could not write {self.path}: {exc}") from exc
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        _LOGGER.info("Updated server in %s", self.path)
        return backup


def _create_temp(path: Path) -> tuple[int, Path]:
    """Create a uniquely named temporary file beside *path*.

    ``tempfile.mkstemp`` is deliberately avoided: on Windows it retries a
    refused create up to 10,000 times because ``os.access`` ignores ACLs, which
    turns an access-denied folder into a multi-minute freeze. Only name
    collisions are retried here.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(50):
        candidate = path.parent / (
            f".{path.stem}-{os.getpid()}-{secrets.token_hex(4)}.tmp"
        )
        try:
            return os.open(candidate, flags, 0o600), candidate
        except FileExistsError:
            continue
    raise SettingsError(
        f"Could not create a temporary file in {path.parent}. "
        "Remove stale .tmp files and try again."
    )


def _backup(path: Path) -> Path:
    folder = path.parent / BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / f"{path.stem}-{stamp}{path.suffix}"
    counter = 1
    while target.exists():
        target = folder / f"{path.stem}-{stamp}-{counter}{path.suffix}"
        counter += 1
    shutil.copy2(path, target)

    backups = sorted(folder.glob(f"{path.stem}-*{path.suffix}"), key=lambda item: item.stat().st_mtime)
    for stale in backups[:-BACKUP_KEEP]:
        try:
            stale.unlink()
        except OSError:
            _LOGGER.warning("Could not remove old backup %s", stale, exc_info=True)
    return target


def read_settings(path: Path) -> SettingsDocument:
    return SettingsDocument.read(path)
