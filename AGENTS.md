# AGENTS.md

## Project

**BrickVPN Branch Selector** — a Windows desktop utility for Brickspoint
Technologies hotel/POS deployments. Staff pick a branch; the app writes that
branch's server address into the hotel software's `settings.ini`, so the hotel
software can log in over the branch's Twingate tunnel. The app does **not**
manage Twingate (no launch, login, or configuration): users sign in to Twingate
separately, and the app only detects whether the client looks running and probes
the server over TCP.

The current app is the `switcher.py` + `brickvpn/` package. The legacy
`main*.py` prototypes and their PyInstaller artefacts have been removed; use git
history (commit "first commit") if you need to inspect them.

## Layout

| Path | Purpose |
| --- | --- |
| `switcher.py` | Entry point: args (`--settings`, `--branches`, `--no-shortcut`), logging, DPI awareness, Tk start. |
| `brickvpn/ui.py` | Tkinter window, worker-thread plumbing, all dialogs. |
| `brickvpn/settings_file.py` | Conservative `settings.ini` editor (line-based, atomic, backups). |
| `brickvpn/branches.py` | `branches.json` dataclasses, validation, defaults. |
| `brickvpn/netcheck.py` | TCP probe (`probe`) and Twingate process/service detection. |
| `brickvpn/shortcut.py` | Desktop shortcut via PowerShell + `WScript.Shell` (no pywin32). |
| `brickvpn/paths.py` | App dir, `%LOCALAPPDATA%\BrickVPN` state/log paths, settings resolution. |
| `branches.json` | Editable branch catalogue shipped next to the exe. |
| `BrickVPN.spec` | PyInstaller one-file/windowed build (name: `BrickVPN Branch Selector`). |
| `tests/` | `unittest` suite. |
| `build/`, `dist/` | Generated PyInstaller output; ignored by git. |

Runtime state lives in `%LOCALAPPDATA%\BrickVPN\state.json` (last branch,
custom settings path, shortcut path). Logs: `%LOCALAPPDATA%\BrickVPN\logs\switcher.log`.
Backups of the user's `settings.ini` go to `<settings folder>\backups\`.

## Commands

Venv is Python 3.12.4; runtime code uses only the standard library (tkinter).

```powershell
.\.venv\Scripts\python.exe switcher.py                 # run from source
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m compileall -q brickvpn switcher.py

# Packaging (PyInstaller is installed in .venv; reinstall with requirements.txt if needed):
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pyinstaller.exe BrickVPN.spec         # -> dist\BrickVPN Branch Selector.exe
```

`branches.json` and `settings.ini` must sit next to the exe; they are
deliberately not bundled into the executable.

## Behaviour that must not regress

- Only the `server` key inside `[Connection_Info]` is modified. Comments, key
  casing, spacing, CRLF/LF, UTF-8 BOM and the other sections stay byte-identical
  apart from that one line. Edit `settings_file.py` with that in mind.
- Every write is atomic (a uniquely named temp file + `os.replace`) and creates
  a timestamped backup; only the newest 10 backups are kept. If the backup
  cannot be created, `save()` raises and the original file is untouched.
  Do **not** use `tempfile.mkstemp` beside `settings.ini`: on Windows, Python
  3.12 retries access-denied creates thousands of times because `os.access`
  ignores ACLs, freezing the app. `settings_file._create_temp` fails fast.
- Access denial raises `SettingsAccessError` (a `SettingsError` subclass). The
  UI offers **File > Restart as administrator**, which relaunches through
  `shortcut.relaunch_as_admin` (`ShellExecuteW` with `runas`). Never silently
  continue when `settings.ini` is not writable.
- A missing `[Connection_Info]` section raises `SettingsError`; the UI turns
  that into a readable dialog instead of writing a broken file.
- All slow work (Twingate detection, TCP probe, settings write, shortcut
  creation) runs through `BranchSelectorApp._submit` and returns on the Tk
  thread via `_poll_tasks`. Never show a `messagebox` or touch widgets from a
  worker thread.
- Switch/test feedback uses determinate progress: workers call
  `_post_progress(fraction, message)`, which queues `(None, (fraction, message))`
  and is applied by `_poll_tasks` before the final result callback. Keep
  progress events in order and never let a progress callback raise into
  `netcheck.probe`.
- The desktop shortcut is created automatically only when frozen (PyInstaller)
  or when `BRICKVPN_FORCE_SHORTCUT=1`; otherwise use **File > Create desktop
  shortcut**. `BRICKVPN_NO_SHORTCUT=1` disables the automatic attempt. The spec
  sets `uac_admin=True`, so packaged builds request elevation; source runs do
  not, and use `shortcut.relaunch_as_admin` instead.
- Shortcut creation targets the exe (frozen) or `pythonw.exe switcher.py`
  (source) and sets the working directory to the app folder, so relative
  `settings.ini`/`branches.json` lookups keep working.
- `branches.json` is reloaded when the window regains focus and its mtime
  changed; invalid JSON must be reported without crashing or losing the current
  window state.
- The table's `Status` column marks the branch matching `settings.ini`; the
  status bar initially shows the last switch time from state.
- `Help > Copy diagnostics` (`Ctrl+D`) must keep working with the clipboard
  unavailable: report an error instead of raising.
- Settings resolution prefers the app folder before a stored path (see
  `paths.resolve_settings_path`) so a moved deployment never edits a stale copy.

## Editing `branches.json`

Top level: `schema_version`, `default_check_ports` (default `[445, 1433]`),
`probe_timeout_seconds` (default `2.0`, allowed `0.5`–`30`), `branches`
(non-empty). Per branch: `id`, `name`, `server` are required; optional
`label`, `alias`, `check_host`, `check_ports`, `enabled: false`, `notes`.
Servers may be IPv4 or DNS names. Invalid rows raise `BranchesError` with the
row index.

Known data quirk: the legacy GUIs used Asokoro `192.168.0.6`, while the newest
prototype (and the shipped `branches.json`) use `192.168.2.16`, and one
prototype labelled the third branch "YOBE" while writing alias "Maitama". Do not
silently normalise internal IPs or branch names — confirm with the network
administrator.

## Conventions

- No third-party runtime dependencies; keep it that way (stdlib + tkinter).
  Shortcut/process helpers call `powershell.exe`, `tasklist` and `sc.exe`.
- Windows-only app, but keep pure-Python modules importable on other platforms
  (guard `win32` code) so tests run anywhere.
- Use `pathlib.Path`, type hints, `logging` (never `print`) and short
  docstrings. UI copy is plain English, no abbreviations.
- Add/adjust a unit test under `tests/` for changes to the core modules; run the
  suite before committing.
- `build/` and `dist/` are ignored via `.gitignore`; do not commit binaries.
- Keep real `settings.ini` values (server IPs, `network_path`, POS setup) intact
  when testing; use temporary files.
