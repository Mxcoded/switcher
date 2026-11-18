"""Reachability checks for branch servers and a light Twingate probe.

Nothing here authenticates to Twingate: the client's sign-in state is not
exposed locally, so the app reports whether the client is running and lets the
TCP probe tell the real story.
"""

from __future__ import annotations

import csv
import logging
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from io import StringIO
from typing import Callable

_LOGGER = logging.getLogger(__name__)

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class CheckOutcome:
    ok: bool
    host: str
    port: int | None = None
    latency_ms: int | None = None
    detail: str = ""

    @property
    def summary(self) -> str:
        if self.ok and self.port is not None:
            suffix = f" ({self.latency_ms} ms)" if self.latency_ms is not None else ""
            return f"Reachable at {self.host}:{self.port}{suffix}"
        return f"Unreachable at {self.host}"


@dataclass(frozen=True)
class TwingateStatus:
    running: bool
    detail: str


def probe(
    host: str,
    ports: tuple[int, ...] | list[int],
    timeout: float = 2.0,
    on_progress: ProgressCallback | None = None,
) -> CheckOutcome:
    """Try each TCP port until one accepts a connection.

    ``on_progress`` receives a fraction (0-1) and a human-readable message.
    During a port attempt it is called about ten times per second so the UI can
    show real movement instead of an indeterminate spinner.
    """
    host = host.strip()
    port_list = tuple(dict.fromkeys(int(port) for port in ports))
    if not host or not port_list:
        return CheckOutcome(False, host, detail="No server address or port configured.")

    timeout = max(0.1, float(timeout))
    last_error = "no response"
    total = len(port_list)

    for index, port in enumerate(port_list):
        base = index / total
        span = 1.0 / total
        _emit(
            on_progress,
            base,
            f"Contacting {host} on port {port} ({index + 1}/{total})...",
        )

        stop = threading.Event()
        started = time.perf_counter()
        ticker: threading.Thread | None = None
        if on_progress is not None:
            ticker = threading.Thread(
                target=_heartbeat,
                args=(on_progress, host, port, timeout, started, stop, base, span),
                name="switcher-probe",
                daemon=True,
            )
            ticker.start()

        try:
            with socket.create_connection((host, port), timeout=timeout):
                elapsed = max(0, round((time.perf_counter() - started) * 1000))
                detail = f"Reachable at {host}:{port} ({elapsed} ms)."
                _emit(on_progress, 1.0, detail)
                return CheckOutcome(True, host, port, elapsed, detail)
        except OSError as exc:
            last_error = exc.strerror or str(exc)
            _LOGGER.info("Probe %s:%s failed: %s", host, port, last_error)
        finally:
            stop.set()
            if ticker is not None:
                ticker.join(timeout=0.2)

    listed = ", ".join(str(port) for port in port_list)
    return CheckOutcome(
        False,
        host,
        detail=(
            f"No response from {host} on port {listed}. "
            "Check that Twingate is signed in and the branch server is online."
        ),
    )


def _emit(callback: ProgressCallback | None, fraction: float, message: str) -> None:
    if callback is None:
        return
    try:
        callback(max(0.0, min(1.0, fraction)), message)
    except Exception:  # noqa: BLE001 - progress must never break a probe
        _LOGGER.debug("Progress callback failed", exc_info=True)


def _heartbeat(
    callback: ProgressCallback,
    host: str,
    port: int,
    timeout: float,
    started: float,
    stop: threading.Event,
    base: float,
    span: float,
) -> None:
    """Report elapsed time while a blocking ``connect`` is in progress."""
    while not stop.wait(0.1):
        elapsed = time.perf_counter() - started
        fraction = base + span * min(elapsed / timeout, 0.95)
        _emit(
            callback,
            fraction,
            f"Waiting for {host}:{port} - {elapsed:0.1f}s of {timeout:0.1f}s",
        )


def _process_running() -> tuple[bool, bool]:
    """Return ``(running, check_succeeded)`` for a Twingate client process."""
    if sys.platform != "win32" or shutil.which("tasklist") is None:
        return False, False
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            timeout=6,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False, False
    if completed.returncode != 0:
        return False, False

    text = completed.stdout.decode("utf-8", "replace")
    for row in csv.reader(StringIO(text)):
        if row and row[0].strip().lower().startswith("twingate"):
            return True, True
    return False, True


def _service_running() -> tuple[bool, bool]:
    """Return ``(running, check_succeeded)`` for the Twingate Windows service."""
    sc = shutil.which("sc") or shutil.which("sc.exe")
    if sys.platform != "win32" or sc is None:
        return False, False

    found = False
    for name in ("Twingate", "Twingated"):
        try:
            completed = subprocess.run(
                [sc, "query", name],
                capture_output=True,
                timeout=6,
                creationflags=_CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return found, False
        output = (completed.stdout + completed.stderr).decode("utf-8", "replace")
        if "RUNNING" in output.upper():
            return True, True
        if completed.returncode == 0:
            found = True
    return False, True


def detect_twingate() -> TwingateStatus:
    """Report whether the Twingate client looks alive on this machine."""
    process, process_ok = _process_running()
    service, service_ok = _service_running()

    if process or service:
        parts = []
        if process:
            parts.append("client process running")
        if service:
            parts.append("background service running")
        return TwingateStatus(True, "Detected (" + ", ".join(parts) + ").")

    if not process_ok and not service_ok:
        return TwingateStatus(False, "Status could not be checked on this system.")

    return TwingateStatus(
        False,
        "Not detected — open Twingate and sign in before switching branches.",
    )
