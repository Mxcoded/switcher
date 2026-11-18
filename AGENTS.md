# AGENTS.md

## Project

**Switcher** — a Windows desktop utility owned by **Afriwave Technology** and
developed by **Mxcoded**, for Brickspoint Technologies hotel/POS deployments.
Staff pick a branch; the app writes that branch's server address into the hotel
software's `settings.ini`, so the hotel software can log in over the branch's
Twingate tunnel. The app does **not** manage Twingate (no launch, login, or
configuration): users sign in to Twingate separately, and the app only detects
whether the client looks running and probes the server over TCP.

The product name lives in `brickvpn/branding.py`; the Python package keeps its
original `brickvpn/` name so imports and the folder layout stay stable.

The current app is the `switcher.py` + `brickvpn/` package. The legacy
`main*.py` prototypes and their PyInstaller artefacts have been removed; use git
history (commit "first commit") if you need to inspect them.

## Layout

| Path | Purpose |
| --- | --- |
| `switcher.py` | Entry point: args (`--settings`, `--branches`, `--license`, `--no-shortcut`), logging, DPI awareness, Tk start. |
| `brickvpn/branding.py` | `APP_NAME`, `BRAND_MARK`, `COMPANY`, `DEVELOPER`, copyright, state vendor. |
| `brickvpn/licensing.py` | Signed `license.json` parsing, RSA verification, expiry/grace/clock policy, `countdown_text`. |
| `brickvpn/ui.py` | Main window, worker-thread plumbing, file/menu dialogs. |
| `brickvpn/branch_editor.py` | Modal in-app editor for `branches.json` (list + validated form). |
| `brickvpn/theme.py` | Palette, fonts and ttk styles (`install()`, `card()`). |
| `brickvpn/settings_file.py` | Conservative `settings.ini` editor (line-based, atomic, backups). |
| `brickvpn/branches.py` | `branches.json` dataclasses, validation, document load/save, host/port helpers. |
| `brickvpn/netcheck.py` | TCP probe (`probe`) and Twingate process/service detection. |
| `brickvpn/shortcut.py` | Shortcuts via PowerShell + `WScript.Shell`, icon lookup (`asset_icon`), elevation helpers. |
| `brickvpn/paths.py` | `C:\hotel` deployment folder, app/asset dir, `%LOCALAPPDATA%\Afriwave\Switcher` state/log paths, settings resolution. |
| `installer/core.py` | Install plan/apply, backups, all-users shortcuts, HKLM uninstall entry, uninstall. |
| `installer/setup.py` | Tk setup window, `--silent` / `--uninstall`, admin relaunch, frozen guard. |
| `switcher_setup.py` | Entry point of `SwitcherSetup.exe`. |
| `assets/brand_board.png` | Afriwave brand board; the source artwork for the icon and header mark. |
| `assets/switcher.ico` | Generated multi-size icon (16–256 px); exe, shortcut, installer, window. |
| `assets/logo_mark.png` | Generated 48 px transparent mark for the window header. |
| `tools/make_assets.py` | Regenerates the icon and header mark from the brand board (Pillow, build-time only). |
| `branches.json` | Editable branch catalogue shipped next to the exe. |
| `license.json` | Signed site licence (six-month term) shipped next to the exe. |
| `Switcher.spec` | PyInstaller one-file/windowed build (name: `Switcher`); bundles `assets/`. |
| `SwitcherSetup.spec` | PyInstaller build of `SwitcherSetup.exe`; bundles `payload/` + `assets/`. |
| `version_info.txt` | Company/product/copyright metadata embedded in `Switcher.exe`. |
| `version_info_setup.txt` | Same metadata for `SwitcherSetup.exe`. |
| `tools/` | Vendor-only key generation, licence issuing and asset generation; never bundled except the generated images. |
| `tests/` | `unittest` suite. |
| `build/`, `dist/` | Generated PyInstaller output; ignored by git. |

Runtime state lives in `%LOCALAPPDATA%\Afriwave\Switcher\state.json` (last
branch, custom settings path, shortcut path, `last_seen_date` for the licence
clock). Logs: `%LOCALAPPDATA%\Afriwave\Switcher\logs\switcher.log` (the installer
writes `installer.log` beside it). Backups of the user's `settings.ini` go to
`<settings folder>\backups\`; files replaced by an installer upgrade go to
`<install folder>\installer-backups\`.

`C:\hotel` is the deployment folder: `Switcher.exe`, `SwitcherSetup.exe`,
`branches.json`, `license.json` and the hotel software's `settings.ini` live
there.

## Commands

Venv is Python 3.12.4; runtime code uses only the standard library (tkinter).
Pillow is a build-time dependency of `tools/make_assets.py` only.

```powershell
.\.venv\Scripts\python.exe switcher.py                 # run from source
.\.venv\Scripts\python.exe switcher_setup.py --version # installer from source (cannot install)
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m compileall -q brickvpn installer switcher.py switcher_setup.py tools tests

# Packaging (PyInstaller is installed in .venv; reinstall with requirements.txt if needed):
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\make_assets.py        # regenerate icon + header mark
.\.venv\Scripts\pyinstaller.exe --noconfirm Switcher.spec       # -> dist\Switcher.exe
.\.venv\Scripts\pyinstaller.exe --noconfirm SwitcherSetup.spec  # -> dist\SwitcherSetup.exe

# Vendor licence tooling (private key stays out of git; see keys/):
.\.venv\Scripts\python.exe tools\generate_keys.py --out keys\private_key.json
.\.venv\Scripts\python.exe tools\issue_license.py --key keys\private_key.json `
    --id AFR-2026-001 --customer "Brickspoint Technologies" --months 6 --out license.json
```

Build `Switcher.spec` before `SwitcherSetup.spec`: the setup profile refuses to
run when `dist\Switcher.exe` is missing. Refresh `dist\branches.json` and
`dist\license.json` before packaging the installer so it carries current files.

`branches.json`, `license.json` and `settings.ini` must sit next to the exe; they
are deliberately not bundled into `Switcher.exe`. The installer carries its own
copy of `branches.json` and `license.json` inside `SwitcherSetup.exe`.

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
  or when `SWITCHER_FORCE_SHORTCUT=1`; otherwise use **File > Create desktop
  shortcut**. `SWITCHER_NO_SHORTCUT=1` disables the automatic attempt (the old
  `BRICKVPN_*` names are still accepted). The spec sets `uac_admin=True`, so
  packaged builds request elevation; source runs do not, and use
  `shortcut.relaunch_as_admin` instead.
- Shortcut creation targets the exe (frozen) or `pythonw.exe switcher.py`
  (source) and sets the working directory to the app folder, so relative
  `settings.ini`/`branches.json` lookups keep working.
- All user-facing product names come from `brickvpn/branding.py`
  (`APP_NAME = "Switcher"`, owner `Afriwave Technology`, developer `Mxcoded`).
  Do not hard-code "BrickVPN" in window titles, dialogs, shortcut names or
  build metadata. `version_info.txt` carries the same values into the exe.
- `branches.json` is reloaded when the window regains focus and its mtime
  changed; invalid JSON must be reported without crashing or losing the current
  window state.
- **File > Edit branches...** (`Ctrl+E`) must stay the primary way staff edit
  branches; raw JSON is the advanced escape hatch. The editor works on
  `branches.load_document` so disabled rows survive, validates the whole
  document through `save_document` before writing, keeps internal ids stable,
  and never touches `settings.ini`. After a successful save, reload the table
  and keep the selected branch when it still exists (otherwise select the first).
- All window styling goes through `theme.install()` / `theme.card()`; do not
  reintroduce ad-hoc fonts or colours in `ui.py`, `branch_editor.py` or
  `installer/setup.py`.
- The table's `Status` column marks the branch matching `settings.ini`; the
  status bar initially shows the last switch time from state.
- `Help > Copy diagnostics` (`Ctrl+D`) must keep working with the clipboard
  unavailable: report an error instead of raising.
- Settings resolution checks `C:\hotel\settings.ini` **first**, then the folder
  next to the app, a stored path, and the current folder (see
  `paths.resolve_settings_path` / `paths.preferred_settings_path`). `C:\hotel`
  is the live deployment; the later candidates exist so a development copy still
  works. `--settings` always wins, and the UI must name `C:\hotel` in its
  "not found" message and locate dialog.
- The status card always shows a licence countdown (`licensing.countdown_text`):
  days left, "Expires today", remaining grace, or "renew to switch". Keep the
  banner and the row in step (`_refresh_license_banner` refreshes both) and keep
  the countdown in diagnostics and **Help > Licence** (`Ctrl+L`). Colours come
  from the status level, never from ad-hoc values.

## Installer and assets

- `SwitcherSetup.exe` installs **into `C:\hotel` only** and must never read,
  write or replace `settings.ini`. `installer/core.build_plan` copies only
  `Switcher.exe`, `branches.json` and `license.json`; keep it that way.
- Existing `license.json` and `branches.json` are kept unless the operator ticks
  the replace option, and every replaced file is copied to
  `installer-backups\` first. A reinstall must never roll back a licence renewal
  or a branch edit.
- The installer registers the machine-wide uninstall entry and all-users
  shortcuts, and copies itself to `C:\hotel\SwitcherSetup.exe` so
  `--uninstall` keeps working. Uninstall removes the exe, shortcuts and
  registry entry, then self-deletes; it keeps `settings.ini`, site data and
  backups.
- Never let a source checkout run the install path: `installer.setup._require_frozen`
  refuses to copy `sys.executable` (that would install `python.exe` as the
  uninstaller). `SwitcherSetup.spec` sets `uac_admin=True`; the code also
  relaunches through `ShellExecuteW("runas")` when not elevated.
- The icon and header mark are generated: edit `assets/brand_board.png` and run
  `tools/make_assets.py`; never hand-edit `switcher.ico` or `logo_mark.png`.
  Small icon sizes are redrawn from the brand geometry, larger ones come from the
  artwork. `paths.asset_dir()` prefers the PyInstaller bundle, then
  `assets/`; both specs must keep shipping `assets/switcher.ico` and
  `assets/logo_mark.png`.
- Keep `__version__`, `version_info.txt` and `version_info_setup.txt` in step;
  the setup profile packages the `dist\Switcher.exe` produced by the app build.

## Licensing

- Verification is **offline** and public-key only: `licensing.load_license`
  checks an RSA-2048 PKCS#1 v1.5 / SHA-256 signature with `hashlib` and `pow`.
  Never add a network activation call or an embedded private key.
- `keys/` holds the vendor's private key and is gitignored. Never commit it, and
  never bundle it into the exe. Losing it means re-issuing every licence.
- `licensing.canonical_payload` is the single definition of the signed bytes;
  `tools/issue_license.py` imports it. Do not duplicate the JSON formatting.
- Policy: a 30-day info reminder, a 14-day amber warning (covering the final
  week), a 14-day grace period, then `can_switch=False`. Viewing the branch
  list and connection tests must keep working after expiry. Do not turn a
  lapsed licence into an app that will not open.
- A backwards system clock is detected with `resolve_today` and `last_seen_date`
  in state; judge the licence by the later date and warn, never crash.
- Switching must be blocked in both places: `switch_branch` (with an
  explanatory dialog) and `_update_actions` (button state). `switch_branch` is
  also reachable from the menu and a double-click, so the guard cannot live
  only in the button.
- Tests use a separate test key in `tests/test_licensing.py`; the production
  public key is the only key the app accepts.

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
