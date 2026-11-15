"""Tests for TCP probing and Twingate detection."""

from __future__ import annotations

import socket
import unittest

from brickvpn.netcheck import CheckOutcome, TwingateStatus, detect_twingate, probe


def _listening_socket() -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    return server


def _closed_port() -> int:
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe_socket.bind(("127.0.0.1", 0))
    port = probe_socket.getsockname()[1]
    probe_socket.close()
    return port


class ProbeTests(unittest.TestCase):
    def test_open_port_is_reachable(self) -> None:
        server = _listening_socket()
        self.addCleanup(server.close)
        port = server.getsockname()[1]

        outcome = probe("127.0.0.1", (port,), timeout=1)
        self.assertIsInstance(outcome, CheckOutcome)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.port, port)
        self.assertIsNotNone(outcome.latency_ms)

    def test_closed_port_is_unreachable(self) -> None:
        outcome = probe("127.0.0.1", (_closed_port(),), timeout=0.5)
        self.assertFalse(outcome.ok)
        self.assertIn("No response", outcome.detail)

    def test_falls_through_to_a_reachable_port(self) -> None:
        server = _listening_socket()
        self.addCleanup(server.close)
        open_port = server.getsockname()[1]

        outcome = probe("127.0.0.1", (_closed_port(), open_port), timeout=0.5)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.port, open_port)

    def test_empty_configuration_is_reported(self) -> None:
        outcome = probe("127.0.0.1", ())
        self.assertFalse(outcome.ok)
        self.assertIn("No server address", outcome.detail)

    def test_progress_reaches_completion(self) -> None:
        server = _listening_socket()
        self.addCleanup(server.close)
        port = server.getsockname()[1]

        events: list[tuple[float, str]] = []
        outcome = probe(
            "127.0.0.1",
            (port,),
            timeout=1,
            on_progress=lambda fraction, message: events.append((fraction, message)),
        )

        self.assertTrue(outcome.ok)
        self.assertTrue(events)
        fractions = [fraction for fraction, _ in events]
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[-1], 1.0)
        self.assertTrue(all(0.0 <= fraction <= 1.0 for fraction in fractions))
        self.assertTrue(all(message for _, message in events))

    def test_progress_errors_do_not_break_the_probe(self) -> None:
        server = _listening_socket()
        self.addCleanup(server.close)
        port = server.getsockname()[1]

        def broken(_fraction: float, _message: str) -> None:
            raise RuntimeError("progress callback failed")

        outcome = probe("127.0.0.1", (port,), timeout=1, on_progress=broken)
        self.assertTrue(outcome.ok)


class TwingateTests(unittest.TestCase):
    def test_detection_returns_a_status(self) -> None:
        status = detect_twingate()
        self.assertIsInstance(status, TwingateStatus)
        self.assertIsInstance(status.running, bool)
        self.assertTrue(status.detail)


if __name__ == "__main__":
    unittest.main()
