# BrickVPN Branch Selector

A small Windows desktop tool for Brickspoint Technologies hotel/POS sites. Staff
open one app, choose the branch they are working at, and the tool points the
hotel software's `settings.ini` at that branch's server. With Twingate already
signed in, the hotel software can then reach the branch and the user can log in.

| | |
| --- | --- |
| **What it is** | A safe editor for one value: `server` in `[Connection_Info]`. |
| **What it is not** | A VPN client. It does not start, configure, or log in to Twingate. |
| **Platform** | Windows 10 / 11 (64-bit). |
| **Runtime** | Packaged `.exe` - no Python needed; requests administrator rights on launch. |

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Deployment](#deployment)
5. [First run and the desktop shortcut](#first-run-and-the-desktop-shortcut)
6. [Daily use](#daily-use)
7. [Window guide](#window-guide)
8. [Branch catalogue reference](#branch-catalogue-reference)
9. [How settings.ini is handled](#how-settingsini-is-handled)
10. [Connection checks and Twingate](#connection-checks-and-twingate)
11. [Troubleshooting](#troubleshooting)
12. [Command-line options](#command-line-options)
13. [Development](#development)
14. [Security and privacy](#security-and-privacy)
15. [FAQ](#faq)
16. [Known limitations and roadmap](#known-limitations-and-roadmap)

---

## Features

- **Branch list lives in `branches.json`** - add, rename, disable or re-address
  branches without touching code or rebuilding the app.
- **Conservative `settings.ini` editing** - only the `server` value in
  `[Connection_Info]` changes. Comments, key casing, line endings and all other
  sections are preserved.
- **Backups and atomic writes** - the previous file is copied to `backups\`
  before every change; a failed write cannot leave a half-written config.
- **Current branch detection** - on start-up the table marks the branch that
  matches the server already in `settings.ini`.
- **Reachability check** - after switching, and on demand, the app probes the
  branch server on TCP 445 / 1433 (configurable) and reports the result.
- **Live percentage progress** - switching shows a real progress bar with the
  current stage ("Checking the branch connection... 67%"), a per-port countdown
  while waiting, and a configurable timeout.
- **Twingate awareness** - shows whether the Twingate client/service is running
  and gives guidance when it is not (sign-in state cannot be read locally).
- **Portable deployment** - copy one exe and one JSON file next to the hotel
  software; the app finds its files relative to itself, not the Desktop.
- **Automatic desktop shortcut** - the packaged app creates/repairs its own
  shortcut on first run, with the correct working directory.
- **Support-friendly** - rotating log file, and **Help > Copy diagnostics**
  puts a complete status snapshot on the clipboard.
- **Native, comfortable UI** - Windows theme, DPI awareness, keyboard
  shortcuts, percentage progress and readable error messages.
- **Runs elevated by default** - the packaged exe requests administrator rights
  through UAC, so protected hotel folders such as `C:\hotel` work without extra
  steps. Source runs can use **File > Restart as administrator**.

---

## How it works

1. Twingate is running and the user is signed in.
2. The user opens **BrickVPN Branch Selector** and picks a branch.
3. The app rewrites the `server` value in `settings.ini`.
4. The app probes the branch server and shows reachable / unreachable.
5. The user restarts the hotel software so it reads the new server, then logs in.

```
Hotel software folder
├── settings.ini                       <- read and updated by this app
├── branches.json                      <- branch list, maintained by IT
├── BrickVPN Branch Selector.exe       <- this app
├── backups\                           <- automatic copies of settings.ini
│   └── settings-20261115-120312.ini
└── ... hotel software files
```

Only this one line changes inside `settings.ini`:

```ini
[Connection_Info]
app_type = workstation
database = hotel
server = 192.168.2.16        ; <- replaced with the selected branch's server
network_path = \\tvmserver\tvm01
timeout = 15
numretries = 5
```

Everything else - POS configuration, branch defaults, comments, spacing,
key casing and Windows/Unix line endings - is left exactly as it was.

Per-user data is kept outside the app folder so the deployment can be read-only:

| Item | Location |
| --- | --- |
| Last branch / last switch / custom paths | `%LOCALAPPDATA%\BrickVPN\state.json` |
| Log file | `%LOCALAPPDATA%\BrickVPN\logs\switcher.log` |
| Backups of the real `settings.ini` | `<folder of settings.ini>\backups\` |

---

## Requirements

- Windows 10 or Windows 11, 64-bit.
- The hotel software installed with its `settings.ini`.
- Twingate installed, running and signed in on the workstation.
- The Twingate user must have access to the branch resources; a running client
  with no access will still fail the connection check.
- Write permission to the folder containing `settings.ini`, or run the app as
  administrator for protected folders such as `C:\hotel`.
- For source runs or rebuilds only: Python 3.10+ with tkinter (the bundled
  `.venv` uses Python 3.12).

---

## Deployment

### New workstation

1. Install and sign in to Twingate.
2. Locate the folder that contains the hotel software's `settings.ini`.
3. Copy these two files into that folder:
   - `BrickVPN Branch Selector.exe`
   - `branches.json`
4. Run the exe once. A **BrickVPN Branch Selector** shortcut is placed on the
   current user's Desktop.
5. Test a switch, restart the hotel software, and confirm login.

> Approve the **User Account Control** prompt when the app starts: the packaged
> exe requests administrator rights so it can update `settings.ini` inside
> protected folders such as `C:\hotel`. The desktop shortcut launches the same
> elevated exe. When running from source, use **File > Restart as
> administrator** if Windows reports denied access.

No installer, Windows service or registry changes are required. Each Windows
user who runs the app gets their own state and their own shortcut.

### Upgrading an existing site

1. Close the app.
2. Replace `BrickVPN Branch Selector.exe` with the new build.
3. Keep the site's `branches.json` and `settings.ini` - do not overwrite them
   with the repository defaults.
4. Start the app; the shortcut is repaired automatically if the exe moved.

State and logs in `%LOCALAPPDATA%\BrickVPN` are preserved across upgrades.

### Uninstalling

1. Delete the Desktop shortcut.
2. Delete the exe and `branches.json` from the hotel software folder.
3. Optionally delete `%LOCALAPPDATA%\BrickVPN` and the `backups\` folder if the
   history is no longer needed.

`settings.ini` is left as it is; the hotel software keeps using the last
selected branch.

> The executable is not code-signed. Windows SmartScreen may warn the first
> time it runs on a new machine; use **More info > Run anyway**, or code-sign
> the build before a wider rollout.

---

## First run and the desktop shortcut

When the **packaged** app starts and no valid shortcut is recorded, it creates:

- **Name:** `BrickVPN Branch Selector.lnk`
- **Target:** the exe that is running
- **Working directory:** the exe's folder (so `settings.ini` is found)
- **Icon:** the exe icon, or `assets\brickvpn.ico` if one was built in

The app tracks the shortcut target in its state. If the deployment folder moves,
the stale shortcut is recreated with the new path on the next launch.

If the shortcut is missing or was deleted, use **File > Create desktop shortcut**.
Running from source does not auto-create a shortcut; use the same menu item or
set `BRICKVPN_FORCE_SHORTCUT=1`.

If the app starts without finding `settings.ini` next to itself, it asks once
whether to locate the hotel software's file; the chosen path is remembered in
`state.json`. Running the app from `dist\` without a `settings.ini` is otherwise
a valid way to look at the branch list.

> `settings.ini` next to the app always takes priority over a previously located
> file, so moving the whole folder never edits a stale copy. Use
> `File > Locate settings.ini...` or `--settings <path>` to override.

---

## Daily use

1. Open **Twingate** and make sure it is signed in.
2. Open **BrickVPN Branch Selector** from the Desktop and approve the UAC
   prompt.
3. Check the status card:
   - **Current server** shows what the hotel software is using now.
   - **Twingate** should say *Detected*.
4. Select the branch. The row marked **Current** is the active one.
5. Press **Switch Branch**. The app writes the new server and checks it. The
   status bar shows what it is doing and how far along it is (for example
   `Waiting for 192.168.2.16:1433 - 1.2s of 2.0s (68%)`).
6. Read the result dialog, then **restart the hotel software**.
7. Log in with the account for that branch.

A switch dialog looks like this:

```
Branch switched

You are now connected to the Asokoro branch.

Server: 192.168.2.16
Previous server: 192.168.0.5

Reachable at 192.168.2.16:445 (12 ms)
```

If the server cannot be reached, the dialog is a warning instead, and the
reason is also shown in the **Connection** row.

---

## Window guide

**Status card**

| Row | Meaning |
| --- | --- |
| Current server | Value currently in `settings.ini`, plus the branch it matches. Red if the file is missing or unreadable. |
| Twingate | *Detected (client process running / background service running)* or *Not detected*. This is a liveness check only - sign-in state cannot be read locally. |
| Connection | Result of the last TCP probe: port and latency, or a troubleshooting hint. |
| Settings file | Full path of the file being edited, with **Open** and **Change...** buttons. |

While a switch or connection test runs, a progress bar and percentage appear on
the right of the status bar, the busy cursor is shown, and the action buttons
are disabled. The bar is determinate, not a spinner: it reports each stage and
moves during the network check.

**Branches table**

- `Branch` - display name (`label`, else `name`) from `branches.json`.
- `Server` - address that will be written to `settings.ini`.
- `Status` - **Current** for the branch that matches `settings.ini`.
- Double-click a row, or select it and press **Enter**, to switch.

**Buttons**

| Button | Action |
| --- | --- |
| Test Connection | Probe the selected branch (or the current server if none is selected). |
| Refresh | Re-read `settings.ini` and re-check Twingate. |
| Switch Branch | Write the selected branch and probe it. |

**Menus and keyboard shortcuts**

| Shortcut | Action |
| --- | --- |
| `Enter` (in the table) | Switch to the selected branch |
| `F5` | Refresh status |
| `Ctrl+T` | Test connection |
| `Ctrl+R` | Reload `branches.json` |
| `Ctrl+D` | Copy diagnostics to the clipboard |
| `File > Locate settings.ini...` | Point the app at a different hotel installation |
| `File > Edit branches.json` | Open the catalogue in the default editor |
| `File > Create desktop shortcut` | Create or repair the shortcut |
| `File > Restart as administrator` | Relaunch elevated (shown only when not already elevated) |
| `File > Open log folder` | Open `%LOCALAPPDATA%\BrickVPN\logs` |
| `Help > About` | Version and active paths |

`branches.json` is also watched: after you edit and save it, returning focus to
the window reloads the table automatically. Invalid content produces an inline
error and a dialog, and the previous table stays usable.

---

## Branch catalogue reference

`branches.json` is read every time the app starts and whenever the window
regains focus after the file changed. It is strict JSON: double quotes, no
trailing commas, no comments.

```json
{
  "schema_version": 1,
  "default_check_ports": [445, 1433],
  "probe_timeout_seconds": 2.0,
  "branches": [
    {
      "id": "wuse",
      "name": "Wuse",
      "label": "Wuse (SERVER 1)",
      "server": "192.168.0.5"
    },
    {
      "id": "asokoro",
      "name": "Asokoro",
      "label": "Asokoro (SERVER 2)",
      "server": "192.168.2.16",
      "alias": "Asokoro",
      "check_ports": [1433],
      "notes": "SQL port verified with the branch administrator"
    },
    {
      "id": "maitama",
      "name": "Maitama",
      "label": "Maitama (SERVER 3)",
      "server": "192.168.0.7"
    }
  ]
}
```

### Top-level fields

| Field | Required | Description |
| --- | --- | --- |
| `schema_version` | no | Informational; currently `1`. |
| `default_check_ports` | no | TCP ports probed for branches without their own `check_ports`. Default `[445, 1433]` (SMB / SQL Server). |
| `probe_timeout_seconds` | no | How long each port attempt waits before giving up. Number from `0.5` to `30`; default `2.0`. |
| `branches` | yes | Non-empty list of branch objects. |

### Branch fields

| Field | Required | Description |
| --- | --- | --- |
| `id` | yes | Stable, unique identifier (`wuse`, `asokoro`, ...). Used for selection and state; changing it resets the saved selection. |
| `name` | yes | Short branch name, also used in messages. |
| `server` | yes | IPv4 address or DNS name written to `settings.ini`. |
| `label` | no | Text shown in the table. Defaults to `name`. |
| `alias` | no | Name used in the success dialog. Defaults to `name`. |
| `check_host` | no | Different host to probe if the server address is not the one that answers the check. |
| `check_ports` | no | One port or a list of ports for this branch; overrides `default_check_ports`. |
| `enabled` | no | Set `false` to hide a branch without deleting its entry. |
| `notes` | no | Free text for maintainers; accepted but not displayed. |

Servers are validated as IPv4 addresses or DNS host names. Duplicate ids,
missing required fields, invalid ports and malformed JSON are rejected with the
row number; the app never writes a broken branch file. To start from scratch,
delete `branches.json` and restart the app - it writes the default catalogue.

### Common edits

**Add a branch** - append an object to `branches` with a new `id`, `name` and
`server`, then save and return to the window.

**Stop offering a branch** - set `"enabled": false` instead of deleting it.

**Change a server address** - edit `server`. Nothing else needs to change.

**Probe a different port** - add `"check_ports": [1433]` to that branch.

**Change how long a check waits** - set `probe_timeout_seconds` at the top
level. A smaller value (for example `1.0`) makes a failed check finish sooner;
a larger value tolerates a slow tunnel. The wait applies to each port, so two
ports at `2.0` can take about four seconds when the server is offline.

**Use a DNS name** - `"server": "tvm-asokoro.local"` is valid, provided the
workstation can resolve it through Twingate.

> Historical note: earlier prototypes used `192.168.0.6` for Asokoro, while the
> newest GUI used `192.168.2.16`; one prototype labelled the third branch
> "YOBE" but wrote alias "Maitama". The shipped catalogue uses
> **Asokoro = 192.168.2.16** and **Maitama = 192.168.0.7**. Confirm both with
> the network administrator and correct the JSON if the site differs.

---

## How `settings.ini` is handled

- Only the first `server` key (case-insensitive, `=` or `:`) inside
  `[Connection_Info]` is replaced. The original key spelling and spacing around
  the delimiter are preserved.
- If the key is missing but the section exists, it is added directly below the
  section header.
- If the section is missing, the app refuses to write and shows an error; it
  never creates a partial hotel configuration.
- Encoding is detected: UTF-8 (with or without BOM) or ANSI/cp1252. The file is
  written back in the same encoding, with the same BOM and line endings.
- Each save first copies the old file to `backups\settings-YYYYMMDD-HHMMSS.ini`.
  The newest 10 backups are kept; older ones are pruned. If the backup cannot
  be created, the app refuses to continue and leaves `settings.ini` untouched.
- Writes use a temporary file in the same folder and `os.replace`, so a crash
  cannot leave a truncated `settings.ini`.

**If Windows denies access** (common when the hotel software is installed in an
administrator-protected folder such as `C:\hotel`), the switch stops within
milliseconds, `settings.ini` is not changed, and the app offers to restart as
administrator. Accept the prompt, approve UAC, and switch again. You can also
start the app with right-click **Run as administrator**, or ask IT to grant
your Windows account write access to the folder.

**Restore a previous configuration:** close the app and the hotel software,
open `backups\`, and copy the required `settings-*.ini` over `settings.ini`
(rename it to `settings.ini`). Then restart the hotel software.

**If the file is read-only or locked:** the app reports "Windows refused write
access". Close the hotel software and retry, or run the selector from an
account that can write to the folder.

---

## Connection checks and Twingate

The probe opens a TCP connection to the branch's `check_host` (default: its
`server`) on each configured port until one answers. It is intentionally
generic: it does not log in to SQL, SMB or the hotel application. Each port
attempt is limited by `probe_timeout_seconds` (default 2 seconds).

While the probe runs, the status bar names the port it is trying and counts the
elapsed time, and the percentage next to the bar reflects the whole switch -
reading the file, writing it, then the connection check. The check is allowed
to take its time; the app does not freeze because it runs on a worker thread.

| Twingate | Probe | Interpretation |
| --- | --- | --- |
| Detected | Reachable | Normal state; restart the hotel software and log in. |
| Detected | Unreachable | Client is running but not usable: finish sign-in, check the user's resource access, or the branch server is offline. |
| Not detected | Unreachable | Start Twingate, sign in, then press **Refresh** and test again. |
| Not detected | Reachable | The network path is probably still up; confirm Twingate status before relying on it. |

Twingate detection looks for a `twingate*` process and the `Twingate` /
`Twingated` Windows services. Sign-in state is not exposed locally, so the app
never claims "connected" on Twingate's behalf.

If the probe reports *Unreachable* while the hotel software still works, the
application may use a port that is not in `default_check_ports`. Set
`check_ports` for that branch to the real port, or ignore the probe - the write
has already succeeded either way.

---

## Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| "Twingate: Not detected" | Client not running, or detection blocked | Open Twingate and sign in; press **Refresh**; check Task Manager for a Twingate process. |
| "No response from ... on port 445, 1433" | Not signed in, no resource access, server offline, or wrong ports | Sign in to Twingate, verify the branch server is up, set `check_ports`, or test from another workstation. |
| Dialog says branch was set but connection was not verified | The write succeeded; only the probe failed | Treat as a network/Twingate issue; the hotel software may still work. |
| "Could not write settings.ini" | File locked by the hotel software or the folder is administrator-protected | Close the hotel software; if the message mentions access, accept the offer to restart as administrator (or right-click the app > **Run as administrator**). |
| "settings.ini not found" | App placed elsewhere, or file renamed | **File > Locate settings.ini...**, or pass `--settings`. |
| Branch list problem / empty table | Invalid JSON, duplicate id, missing field | Read the inline error, fix `branches.json`, then **File > Reload branches** (`Ctrl+R`). |
| No branches appear after editing | JSON saved in another folder or malformed | Confirm the path shown under **Settings file** uses the app folder's `branches.json`. |
| Shortcut missing or points to an old folder | Moved exe, or shortcut deleted | **File > Create desktop shortcut**; the target is rewritten. |
| Switched, but hotel software still uses the old server | It read `settings.ini` at start-up | Restart the hotel software. |
| App window does not open | Corrupt deployment or missing files | Check `%LOCALAPPDATA%\BrickVPN\logs\switcher.log`; re-copy the exe. |
| SmartScreen warning on first run | Unsigned executable | **More info > Run anyway**, or sign the build. |

### Collecting diagnostics

1. In the app, press `Ctrl+D` (**Help > Copy diagnostics**). The clipboard now
   contains the version, Windows build, active paths, current server, Twingate
   and connection status, and any branch-list error.
2. Open **File > Open log folder** and attach `switcher.log` if the problem is
   reproducible.
3. Include the selected branch and the exact dialog text in the report.

---

## Command-line options

```powershell
"BrickVPN Branch Selector.exe" [--settings PATH] [--branches PATH] [--no-shortcut]
```

| Option | Description |
| --- | --- |
| `--settings PATH` | Use a specific `settings.ini` instead of the one next to the app. |
| `--branches PATH` | Use a specific `branches.json`. |
| `--no-shortcut` | Do not create the desktop shortcut automatically this run. |
| `--version` | Print the version and exit (source runs). |

Environment variables:

| Variable | Effect |
| --- | --- |
| `BRICKVPN_NO_SHORTCUT=1` | Disable automatic shortcut creation for this user/session. |
| `BRICKVPN_FORCE_SHORTCUT=1` | Allow automatic shortcut creation when running from source. |

Examples:

```powershell
"BrickVPN Branch Selector.exe" --settings "D:\Hotel\settings.ini"
"BrickVPN Branch Selector.exe" --no-shortcut
```

---

## Development

### Project structure

```
BrickVPN/
├── switcher.py              # entry point: args, logging, DPI, Tk start
├── brickvpn/
│   ├── __init__.py          # version
│   ├── ui.py                # window, worker threads, dialogs
│   ├── settings_file.py     # conservative settings.ini editor
│   ├── branches.py          # branches.json model and validation
│   ├── netcheck.py          # TCP probe, Twingate detection
│   ├── shortcut.py          # desktop shortcut via PowerShell/WScript
│   └── paths.py             # app/state paths, settings resolution
├── tests/                   # unittest suite
├── branches.json            # sample/default branch catalogue
├── settings.ini             # target file for this deployment
├── BrickVPN.spec            # PyInstaller build definition
├── requirements.txt         # build-time dependency (PyInstaller)
├── README.md
└── AGENTS.md                # notes for coding agents
```

No third-party packages are needed at runtime: the app uses the standard
library, tkinter, and built-in Windows tools (`powershell.exe`, `tasklist`,
`sc.exe`).

### Set up and run

```powershell
.\.venv\Scripts\python.exe switcher.py
```

### Tests and static checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m compileall -q brickvpn switcher.py tests
```

The tests cover the settings editor (comments, BOM, CRLF, cp1252, backups,
atomic replacement), branch validation, path precedence, TCP probing and
shortcut script generation. They never touch the real `settings.ini` and never
create a desktop shortcut.

### Build the executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pyinstaller.exe --noconfirm BrickVPN.spec
```

Output: `dist\BrickVPN Branch Selector.exe` (one file, no console window,
~12 MB). Delete `build\` safely at any time; it is regenerated.

`branches.json` and `settings.ini` are deliberately **not** bundled. They are
data owned by the site and must sit next to the exe at runtime.

Optional icon: place `assets\brickvpn.ico` before building. It is used for the
executable, the shortcut and the window icon.

### Releasing

1. Update `__version__` in `brickvpn/__init__.py`.
2. Run the test suite.
3. Rebuild with the command above.
4. Smoke-test on a clean workstation: launch, switch branch, restart hotel
   software, log in, check `backups\` and the log.
5. Distribute the exe plus the site's `branches.json`.

### Conventions

- Standard library only at runtime; keep new modules importable on non-Windows
  systems with `sys.platform` guards so tests run anywhere.
- `pathlib.Path`, type hints, `logging` (never `print`), short docstrings.
- All slow work runs in a worker thread and returns to the Tk thread through
  `BranchSelectorApp._poll_tasks`; never show dialogs from a worker.
- Add a unit test for every change to `settings_file.py`, `branches.py`,
  `netcheck.py`, `paths.py` or `shortcut.py`.
- Do not commit `build/`, `dist/`, logs, backups or `.venv`.

---

## Security and privacy

- The app stores **no credentials**. Twingate handles authentication.
- No telemetry, analytics or network calls beyond the configured TCP probes.
- `branches.json` contains internal IP addresses and server names. Treat it as
  internal documentation and do not publish it outside the organisation.
- `settings.ini` and `backups\` contain POS configuration. Keep the hotel
  software folder's existing permissions; backups inherit them.
- Logs contain file paths, branch names and error text - useful for support,
  but review before sending outside the organisation.
- The packaged exe is unsigned; sign it for site-wide distribution and to avoid
  SmartScreen prompts.
- The packaged app requests administrator rights so it can write to protected
  hotel folders; Windows always shows a UAC prompt at launch.
- If Windows still denies access, the switch aborts and a clear message is
  shown; the app never writes a partial `settings.ini`.

---

## FAQ

**Does the app connect the VPN?**
No. Twingate must already be running and signed in. The app only edits the
server address and checks reachability.

**Can I add a branch without rebuilding?**
Yes. Edit `branches.json` next to the exe; the app reloads it.

**Why must the hotel software be restarted?**
It reads `settings.ini` at start-up. The app changes the file on disk; the
running process keeps its old server until restarted.

**What happens if I select the branch already in use?**
The app reports "already set", does not rewrite the file, and still performs a
connection check so you can confirm it is healthy.

**How many backups are kept?**
The newest 10 files in `backups\`; older ones are removed automatically.

**Can several sites share one installation?**
Run one copy per hotel folder. Each exe finds the files next to itself; state
(last branch/selection) is per Windows user, so it follows the user across
folders.

**Does it work without Twingate?**
The switch itself works (it is a file edit). Only the connection check depends
on the network path.

**The connection check fails but the hotel software works - why?**
The probe uses generic TCP ports. The application may use a different port; set
`check_ports` for that branch. The server address has already been written.

**Where can I see what the app did?**
`%LOCALAPPDATA%\BrickVPN\logs\switcher.log`, plus the `backups\` folder next to
`settings.ini`.

---

## Known limitations and roadmap

- Twingate sign-in state is not readable locally; the app can only detect the
  client/service and rely on the TCP probe.
- The app does not launch or restart Twingate (deliberate - avoids interfering
  with an existing session).
- Checks are TCP-level only, not a hotel-application login test.
- Windows-only.
- No auto-update; replace the exe during maintenance.
- The exe is unsigned.
- Possible future work: code signing, branded icon, installer/Intune package,
  optional logging of every switch to a shared audit file, and a per-branch
  application-level health check.
