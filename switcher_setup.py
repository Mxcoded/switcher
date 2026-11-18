"""Entry point for the Switcher installer, built as ``SwitcherSetup.exe``."""

from __future__ import annotations

from installer.setup import main

if __name__ == "__main__":
    raise SystemExit(main())
