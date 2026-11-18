# Switcher

**Switcher** is a Windows desktop utility owned by **Afriwave Technology** and
developed by **Mxcoded**. It is deployed at Brickspoint Technologies hotel/POS
sites: staff open the app, choose the branch they are working at, and the tool
points the hotel software's `settings.ini` at that branch's server. With
Twingate already signed in, the hotel software can then reach the branch and the
user can log in.

| | |
| --- | --- |
| **What it is** | A safe editor for one value: `server` in `[Connection_Info]`. |
| **What it is not** | A VPN client. It does not start, configure, or log in to Twingate. |
| **Platform** | Windows 10 / 11 (64-bit). |
| **Licence** | Signed `license.json`; six-month term, checked offline. |
| **Runtime** | Packaged `.exe` - no Python needed; requests administrator rights on launch. |
| **Installer** | `SwitcherSetup.exe` installs into `C:\hotel`, creates shortcuts and keeps site data. |

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Install](#install)
5. [Using Switcher](#using-switcher)
6. [Window guide](#window-guide)
7. [Editing branches in the app](#editing-branches-in-the-app)
8. [Branch catalogue reference](#branch-catalogue-reference)
9. [How settings.ini is handled](#how-settingsini-is-handled)
10. [Connection checks and Twingate](#connection-checks-and-twingate)
11. [Troubleshooting](#troubleshooting)
12. [Command-line options](#command-line-options)
13. [Development](#development)
14. [Licence and renewal](#licence-and-renewal)
15. [Security and privacy](#security-and-privacy)
16. [FAQ](#faq)
17. [Known limitations and roadmap](#known-limitations-and-roadmap)

---

## Features

- **Edit branches in the app** - add, rename, disable, reorder or re-address
  branches in a friendly dialog (**File > Edit branches**, `Ctrl+E`). No JSON
  editing required; the list is still stored in `branches.json` for IT.
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
- **One-folder deployment** - the app lives beside the hotel software in
  `C:\hotel` and finds its files relative to itself, not the Desktop.
- **Automatic desktop shortcut** - the packaged app creates/repairs its own
  shortcut on first run, with the correct working directory; the installer also
  creates all-users Desktop and Start menu shortcuts.
- **Support-friendly** - rotating log file, and **Help > Copy diagnostics**
  puts a complete status snapshot on the clipboard.
- **Bright, uncluttered window** - coloured status cards, clear typography,
  striped branch table and prominent **Switch branch** button, with a matching
  branch editor dialog.
- **Offline licence with renewal reminders** - a signed six-month licence file,
  30/14/7-day warnings and a 14-day grace period, so a hotel is never stranded
  mid-shift; switching stops only after the grace period ends.
- **Licence countdown in the window** - the status card always shows how many
  days remain (or the remaining grace), turns amber near expiry and red when
  switching stops.
- **Branded installer** - `SwitcherSetup.exe` installs into `C:\hotel`, creates
  Desktop and Start menu shortcuts for every user, registers an uninstaller and
  never writes `settings.ini`. Existing branches and licences are kept unless
  the operator explicitly replaces them.
- **Runs elevated by default** - the packaged exe requests administrator rights
  through UAC, so protected hotel folders such as `C:\hotel` work without extra
  steps. Source runs can use **File > Restart as administrator**.

---

## How it works

1. Twingate is running and the user is signed in.
2. The user opens **Switcher** and picks a branch.
3. The app rewrites the `server` value in `settings.ini`.
4. The app probes the branch server and shows reachable / unreachable.
5. The user restarts the hotel software so it reads the new server, then logs in.

```
Hotel software folder (C:\hotel)
├── settings.ini                       <- read and updated by this app
├── branches.json                      <- branch list, maintained by IT
├── license.json                       <- signed site licence (six-month term)
├── Switcher.exe                       <- this app
├── SwitcherSetup.exe                  <- installer / uninstaller copy
├── backups\                           <- automatic copies of settings.ini
│   └── settings-20261115-120312.ini
├── installer-backups\                 <- files replaced by an upgrade
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
| Last branch / last switch / custom paths | `%LOCALAPPDATA%\Afriwave\Switcher\state.json` |
| Log file | `%LOCALAPPDATA%\Afriwave\Switcher\logs\switcher.log` |
| Backups of the real `settings.ini` | `<folder of settings.ini>\backups\` |

---

## Requirements

- Windows 10 or Windows 11, 64-bit.
- The hotel software installed with its `settings.ini` (normally `C:\hotel`).
- Twingate installed, running and signed in on the workstation.
- The Twingate user must have access to the branch resources; a running client
  with no access will still fail the connection check.
- Administrator rights on the workstation. The installer and the app both ask
  for them, because `C:\hotel` is usually protected.
- For source runs or rebuilds only: Python 3.10+ with tkinter (the bundled
  `.venv` uses Python 3.12).

---

## Install

The installer is a single file, `SwitcherSetup.exe`, produced by the vendor. It
contains the application, the branch catalogue and the current site licence, so
there is nothing else to copy. It always installs into `C:\hotel` and never
touches the hotel software's `settings.ini`.

### Install on a workstation

1. Install Twingate and sign in, so the connection test at the end can succeed.
2. Copy `SwitcherSetup.exe` to the workstation (USB stick, network share or
   software deployment tool) and double-click it.
3. If Windows SmartScreen appears, select **More info > Run anyway**. The build
   is not code-signed yet.
4. Approve the **User Account Control** prompt. Windows asks because the
   installer writes to `C:\hotel` and to the machine-wide uninstall entry.
5. Check the setup window:
   - **Install folder** - fixed at `C:\hotel`. The note tells you whether
     Switcher is already installed and whether `settings.ini` was found.
   - **Site licence** - the customer and expiry date read from the bundled
     `license.json`.
   - **Options** - described in the table below. The defaults are safe for an
     existing site.
6. Select **Install** and wait for the progress bar to finish.
7. Read the summary, then select **OK**. If **Open Switcher when the
   installation finishes** was left ticked, the app starts immediately;
   otherwise use the new **Switcher** shortcut.
8. Confirm `C:\hotel` now contains `Switcher.exe`, `SwitcherSetup.exe`,
   `branches.json` and `license.json`, with the hotel software's files unchanged.
9. Continue with [Using Switcher](#using-switcher).

The installer creates **Switcher** shortcuts on the public Desktop and in the
Start menu, so every Windows user on the workstation gets them. Per-user state
and logs still live in `%LOCALAPPDATA%\Afriwave\Switcher`.

### Installer options

| Option | Default | What it does |
| --- | --- | --- |
| Replace the existing `branches.json` | off | Copies the catalogue carried by the installer over the site's file. Only use when the vendor supplied a new catalogue; the old file is backed up first. |
| Replace the existing `license.json` | off | Installs the licence carried by the installer, for example a renewal delivered as a new setup file. The old file is backed up first. |
| Create Desktop and Start menu shortcuts for all users | on | Writes the two shortcuts and points them at `C:\hotel\Switcher.exe`. |
| Open Switcher when the installation finishes | on | Starts the app once the installer closes. |

The two replace options are greyed out when the file does not exist yet, so a
fresh workstation always receives the bundled catalogue and licence. Any file
that is replaced is copied to `C:\hotel\installer-backups\` with a timestamp.

### Unattended install

For Intune, a login script or a remote session:

```powershell
"SwitcherSetup.exe" --silent
```

`--silent` uses the defaults above: keep site data, create shortcuts, do not
open the app. Run it from an elevated context, because Windows cannot show a UAC
prompt to an unattended session. The process exits with `0` on success and `1`
on failure; details go to
`%LOCALAPPDATA%\Afriwave\Switcher\logs\installer.log`.

### Upgrade an existing site

1. Close Switcher.
2. Run the new `SwitcherSetup.exe` and approve UAC. It replaces `Switcher.exe`
   and the uninstaller copy, keeps the site's `branches.json`, `license.json`
   and `settings.ini`, and refreshes the shortcuts and uninstall entry.
3. Start the app. State and logs in `%LOCALAPPDATA%\Afriwave\Switcher` survive
   the upgrade.

The old executable is copied to `C:\hotel\installer-backups\` before it is
replaced.

### Uninstall

Use **Settings > Apps > Installed apps > Switcher > Uninstall**, or run:

```powershell
"C:\hotel\SwitcherSetup.exe" --uninstall
```

The uninstaller removes `Switcher.exe`, `SwitcherSetup.exe`, both shortcuts and
the Add/Remove Programs entry. It deliberately keeps `settings.ini`,
`branches.json`, `license.json`, `backups\` and `installer-backups\`, so the
hotel software keeps working and a reinstall keeps its configuration.

> The executables are not code-signed. SmartScreen may warn the first time they
> run on a new machine; use **More info > Run anyway**, or code-sign the build
> before a wider rollout.

### Manual copy (alternative)

If the installer cannot be used, the app still runs as plain files:

1. Install and sign in to Twingate.
2. Copy `Switcher.exe`, `branches.json` and `license.json` into `C:\hotel`
   (the folder that contains the hotel software's `settings.ini`).
3. Run `Switcher.exe` once and approve UAC. A **Switcher** shortcut is placed on
   the current user's Desktop.
4. Test a switch, restart the hotel software, and confirm login.

---

## Using Switcher

### Start the app

Open **Switcher** from the Desktop or Start menu and approve the UAC prompt. The
window lists the configured branches and shows the current hotel server,
Twingate, the last connection check and the licence countdown.

### First launch: settings.ini and the shortcut

On a normal installation the app reads `C:\hotel\settings.ini`, so no setup is
needed. It looks for the file in this order:

1. `C:\hotel\settings.ini` - the deployment folder used by every site;
2. the folder next to `Switcher.exe`;
3. the path chosen last time with **File > Locate settings.ini...**;
4. the current working directory.

If none exists, it asks once whether to locate the hotel software's file; the
chosen path is remembered in `state.json`. Use **File > Locate settings.ini...**
or `--settings <path>` to point at a different folder.

When the **packaged** app starts and no valid shortcut is recorded, it creates a
`Switcher.lnk` on the current user's Desktop, targeting the running exe with the
exe's folder as the working directory. If the shortcut is missing or points at
an old folder, use **File > Create desktop shortcut**. Source runs never create
one automatically unless `SWITCHER_FORCE_SHORTCUT=1` is set.

### Switch to a branch

1. Make sure Twingate is running and signed in.
2. Check the status card: **Twingate** should say *Detected* and **Licence**
   should show time remaining.
3. Select the branch you are working at. The row marked **Current** is the
   branch already in `settings.ini`.
4. Select **Switch branch** (or double-click the row, or press `Enter`). The app
   writes the server address and probes the branch, with a progress bar and
   per-port countdown in the status bar.
5. Read the result dialog, then **restart the hotel software** so it reads the
   new `settings.ini`.
6. Log in with the account for that branch.

A successful switch looks like this:

```
Branch switched

You are now connected to the Asokoro branch.

Server: 192.168.2.16
Previous server: 192.168.0.5

Reachable at 192.168.2.16:445 (12 ms)
```

If the probe cannot reach the branch, the dialog is a warning instead and the
reason also appears in the **Connection** row. The server address has still been
written; treat it as a Twingate or network problem. Selecting the branch that is
already active reports *already set* without rewriting the file, and still runs
the check.

### Everyday actions

| Action | How |
| --- | --- |
| Add, rename, disable or re-address branches | **File > Edit branches...** (`Ctrl+E`) |
| Re-check the selected branch | **Test connection** (`Ctrl+T`) |
| Re-read `settings.ini` and Twingate | **Refresh status** (`F5`) |
| Reload an externally edited `branches.json` | **Reload** (`Ctrl+R`) |
| Send a support snapshot | **Help > Copy diagnostics** (`Ctrl+D`) |
| See the licence and renewal countdown | **Help > Licence** (`Ctrl+L`), or click the **Licence** row |
| Work in another hotel folder | **File > Locate settings.ini...** |
| Fix a missing or stale shortcut | **File > Create desktop shortcut** |
| Retry after an access-denied error | **File > Restart as administrator** |
| Find the log | **File > Open log folder** |

The full window reference, including every column and menu item, is in the
[Window guide](#window-guide).

---

## Window guide

**Status card**

| Row | Meaning |
| --- | --- |
| Current server | Value currently in `settings.ini`, plus the branch it matches. Red if the file is missing or unreadable. |
| Twingate | *Detected (client process running / background service running)* or *Not detected*. This is a liveness check only - sign-in state cannot be read locally. |
| Connection | Result of the last TCP probe: port and latency, or a troubleshooting hint. |
| Licence | Days left on the site licence, remaining grace after expiry, or a renewal warning. Amber near expiry, red when switching is blocked. Click the value for **Help > Licence**. |
| Settings file | Shortened path of the file being edited, with **Open** and **Change...** buttons. |

While a switch or connection test runs, a progress bar and percentage appear on
the right of the status bar, the busy cursor is shown, and the action buttons
are disabled. The bar is determinate, not a spinner: it reports each stage and
moves during the network check.

**Branches table**

- `Branch` - display name (`label`, else `name`) from `branches.json`.
- `Server` - address that will be written to `settings.ini`.
- `Status` - **Current** for the branch that matches `settings.ini`.
- Double-click a row, or select it and press **Enter**, to switch.
- **Reload** re-reads `branches.json`; **Edit branches** opens the in-app editor.

**Buttons**

| Button | Action |
| --- | --- |
| Test connection | Probe the selected branch (or the current server if none is selected). |
| Refresh status | Re-read `settings.ini` and re-check Twingate. |
| Edit branches... | Open the branch editor (same as `File > Edit branches`). |
| Switch branch | Write the selected branch and probe it. |

**Menus and keyboard shortcuts**

| Shortcut | Action |
| --- | --- |
| `Enter` (in the table) | Switch to the selected branch |
| `F5` | Refresh status |
| `Ctrl+T` | Test connection |
| `Ctrl+E` | Edit branches |
| `Ctrl+R` | Reload `branches.json` |
| `Ctrl+D` | Copy diagnostics to the clipboard |
| `Ctrl+L` | Show the site licence and renewal countdown |
| `File > Locate settings.ini...` | Point the app at a different hotel installation |
| `File > Edit branches...` | Open the friendly branch editor |
| `File > Open branches.json (advanced)` | Open the raw JSON in the default editor |
| `File > Create desktop shortcut` | Create or repair the shortcut |
| `File > Restart as administrator` | Relaunch elevated (shown only when not already elevated) |
| `File > Open log folder` | Open `%LOCALAPPDATA%\Afriwave\Switcher\logs` |
| `Help > About` | Version and active paths |

`branches.json` is also watched: after you edit and save it (in the app or
externally), returning focus to the window reloads the table automatically.
Invalid content produces an inline error and a dialog, and the previous table
stays usable.

---

## Editing branches in the app

Open **File > Edit branches...**, `Ctrl+E`, or the **Edit branches** button.
The dialog changes only `branches.json`; `settings.ini` is never touched until
you switch branches.

- **Left list** - every configured branch, including disabled ones (shown
  greyed out). Select a row to edit it.
- **Add** creates a new row; **Duplicate** copies the selected branch (useful
  when two sites share a server); **Remove** deletes a row; **Move up** /
  **Move down** set the order shown in the main window.
- **Branch details** - the name shown in the list, the server address, and the
  optional display label, connection alias, check host and check ports.
- **Offer this branch in the selector** - untick to hide a branch without
  deleting it. Disabled rows are preserved on save.
- **Connection defaults** - ports checked when a branch has no ports of its
  own, and the probe timeout (0.5 to 30 seconds).

**Save branches** validates every row first (name, IP address or host name,
ports, timeout) and writes the file atomically. If anything is wrong the dialog
stays open and points at the offending branch. **Cancel** asks before discarding
unsaved changes.

Only two things cannot be edited here: internal branch `id` values (generated
automatically and kept stable) and the raw JSON layout. Use
**File > Open branches.json (advanced)** if IT needs to change those.

---

## Branch catalogue reference

The normal way to change branches is **File > Edit branches...**. This section
documents the underlying file for IT and for advanced edits.

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
| Not detected | Unreachable | Start Twingate, sign in, then press **Refresh status** and test again. |
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
| "Twingate: Not detected" | Client not running, or detection blocked | Open Twingate and sign in; press **Refresh status**; check Task Manager for a Twingate process. |
| "No response from ... on port 445, 1433" | Not signed in, no resource access, server offline, or wrong ports | Sign in to Twingate, verify the branch server is up, set `check_ports`, or test from another workstation. |
| Dialog says branch was set but connection was not verified | The write succeeded; only the probe failed | Treat as a network/Twingate issue; the hotel software may still work. |
| "Could not write settings.ini" | File locked by the hotel software or the folder is administrator-protected | Close the hotel software; if the message mentions access, accept the offer to restart as administrator (or right-click the app > **Run as administrator**). |
| "settings.ini not found" | App placed elsewhere, or file renamed | **File > Locate settings.ini...**, or pass `--settings`. |
| Branch list problem / empty table | Invalid JSON, duplicate id, missing field | Read the inline error, fix `branches.json`, then **File > Reload branches** (`Ctrl+R`). |
| No branches appear after editing | JSON saved in another folder or malformed | Confirm the path shown under **Settings file** uses the app folder's `branches.json`. |
| Shortcut missing or points to an old folder | Moved exe, or shortcut deleted | **File > Create desktop shortcut**; the target is rewritten. |
| Switched, but hotel software still uses the old server | It read `settings.ini` at start-up | Restart the hotel software. |
| App window does not open | Corrupt deployment or missing files | Check `%LOCALAPPDATA%\Afriwave\Switcher\logs\switcher.log`; re-copy the exe. |
| "No licence file was found" | `license.json` is missing or in the wrong folder | Copy the site licence next to `Switcher.exe`, or run with `--license PATH`, then restart. |
| Red licence bar / switching disabled | The term ended and the 14-day grace period passed | Issue a renewal and replace `license.json`; no reinstall needed. |
| "signature does not match" | The file was edited, truncated or belongs to another customer/key | Replace it with the signed file Afriwave sent. |
| Clock warning on the licence bar | The Windows date moved backwards | Correct the date and time, then restart the app. |
| SmartScreen warning on first run | Unsigned executable | **More info > Run anyway**, or sign the build. |

### Collecting diagnostics

1. In the app, press `Ctrl+D` (**Help > Copy diagnostics**). The clipboard now
   contains the version, Windows build, active paths, current server, Twingate
   and connection status, the licence countdown and state, and any branch-list
   error.
2. Open **File > Open log folder** and attach `switcher.log` if the problem is
   reproducible.
3. Include the selected branch and the exact dialog text in the report.

---

## Command-line options

```powershell
"Switcher.exe" [--settings PATH] [--branches PATH] [--license PATH] [--no-shortcut]
```

| Option | Description |
| --- | --- |
| `--settings PATH` | Use a specific `settings.ini` instead of `C:\hotel\settings.ini` or the one next to the app. |
| `--branches PATH` | Use a specific `branches.json`. |
| `--license PATH` | Use a specific `license.json` instead of the search next to the app, `%PROGRAMDATA%` and `%LOCALAPPDATA%`. |
| `--no-shortcut` | Do not create the desktop shortcut automatically this run. |
| `--version` | Print the version and exit (source runs). |

The installer (`SwitcherSetup.exe`) accepts:

| Option | Description |
| --- | --- |
| `--silent` | Install with the default options; no window. |
| `--uninstall` | Remove the program, shortcuts and uninstall entry; site data is kept. |

Environment variables (the old `BRICKVPN_*` names are still accepted):

| Variable | Effect |
| --- | --- |
| `SWITCHER_NO_SHORTCUT=1` | Disable automatic shortcut creation for this user/session. |
| `SWITCHER_FORCE_SHORTCUT=1` | Allow automatic shortcut creation when running from source. |

Examples:

```powershell
"Switcher.exe" --settings "D:\Hotel\settings.ini"
"Switcher.exe" --no-shortcut
```

---

## Development

### Project structure

```
Switcher/
├── switcher.py              # entry point: args, logging, DPI, Tk start
├── switcher_setup.py        # entry point of the installer
├── brickvpn/
│   ├── __init__.py          # version
│   ├── branding.py          # product name, owner and developer
│   ├── ui.py                # main window, worker threads, dialogs
│   ├── branch_editor.py     # in-app branches.json editor dialog
│   ├── theme.py             # colours, fonts and ttk styles
│   ├── licensing.py         # signed licence verification, expiry and countdown
│   ├── settings_file.py     # conservative settings.ini editor
│   ├── branches.py          # branches.json model and validation
│   ├── netcheck.py          # TCP probe, Twingate detection
│   ├── shortcut.py          # shortcuts via PowerShell/WScript
│   └── paths.py             # C:\hotel, app/state paths, settings resolution
├── installer/
│   ├── core.py              # install plan, backups, registry, uninstall
│   └── setup.py             # setup window (SwitcherSetup.exe)
├── assets/
│   ├── brand_board.png      # Afriwave artwork the icon is generated from
│   ├── switcher.ico         # multi-size icon (generated)
│   └── logo_mark.png        # transparent header mark (generated)
├── tests/                   # unittest suite
├── tools/                   # vendor-only key, licence and asset tools
├── branches.json            # sample/default branch catalogue
├── license.json             # signed site licence (six-month term)
├── settings.ini             # target file for this deployment
├── Switcher.spec            # PyInstaller build for Switcher.exe
├── SwitcherSetup.spec       # PyInstaller build for SwitcherSetup.exe
├── version_info.txt         # Windows metadata for Switcher.exe
├── version_info_setup.txt   # Windows metadata for SwitcherSetup.exe
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
.\.venv\Scripts\python.exe -m compileall -q brickvpn installer switcher.py switcher_setup.py tools tests
```

The tests cover the settings editor (comments, BOM, CRLF, cp1252, backups,
atomic replacement), branch validation and document round-trips, the in-app
editor, path precedence (`C:\hotel` first), TCP probing, signed-licence
verification, the expiry and grace policy, the renewal countdown, clock-rollback
handling, shortcut script generation and the installer's copy plan (site data is
never overwritten by default). They never touch the real `settings.ini`, the real
`C:\hotel` or the registry, and never create a shortcut.

### Build the executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\make_assets.py      # rebuild icon and header mark
.\.venv\Scripts\pyinstaller.exe --noconfirm Switcher.spec
.\.venv\Scripts\pyinstaller.exe --noconfirm SwitcherSetup.spec
```

Outputs:

- `dist\Switcher.exe` - one file, no console window, ~12 MB, requires
  administrator rights, icon and header mark embedded.
- `dist\SwitcherSetup.exe` - the installer, ~24 MB (it carries `Switcher.exe`,
  `branches.json` and `license.json`), requires administrator rights.

Delete `build\` safely at any time; it is regenerated.

`branches.json`, `license.json` and `settings.ini` are deliberately **not**
bundled into `Switcher.exe`. They are data owned by the site and must sit next
to the exe at runtime. The installer carries its own copies so a fresh machine
is complete after one run.

The icon and header mark come from `assets\brand_board.png`; do not edit
`switcher.ico` or `logo_mark.png` by hand. Replace the artwork and re-run
`tools\make_assets.py` (Pillow is a build-time tool only).

### Releasing

1. Update `__version__` in `brickvpn/__init__.py`, `version_info.txt` and
   `version_info_setup.txt`.
2. Run the test suite.
3. Rebuild `Switcher.spec` and then `SwitcherSetup.spec`. The setup build
   packages the `dist\Switcher.exe` produced by the first build, so always build
   the app first and refresh `dist\branches.json` / `dist\license.json`.
4. Smoke-test the installer on a clean workstation: install, switch branch,
   restart the hotel software, log in, check `installer-backups\`, then
   uninstall and reinstall.
5. Distribute `SwitcherSetup.exe` (or `Switcher.exe` plus the site files for a
   manual deployment).

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

## Licence and renewal

Switcher is licensed for a fixed term (six months by default). The check is
offline: no activation server, no network call, and nothing that can fail
because Twingate is down.

### Files

`license.json` sits next to `Switcher.exe`. The app also looks in
`%PROGRAMDATA%\Afriwave\Switcher` and `%LOCALAPPDATA%\Afriwave\Switcher`, so IT
can install one licence centrally if preferred. The file is signed with the
vendor's RSA-2048 key; the app carries only the public half. A site can read the
customer, dates and seat count but cannot edit them or move the expiry date.

### Timeline for a six-month licence

| When | What staff see | Switching |
| --- | --- | --- |
| More than 30 days left | nothing | allowed |
| 30 to 15 days left | blue reminder bar | allowed |
| 14 days or fewer | amber reminder bar | allowed |
| Expiry day | "expires today" warning | allowed |
| The 14 days after expiry | amber grace bar | allowed |
| After grace | red bar | disabled; viewing and connection tests still work |

**Help > Licence** (`Ctrl+L`) shows the customer, licence ID, issue and expiry
dates, seat count, the renewal countdown and the file in use. The status card's
**Licence** row shows the countdown at all times: green while there is plenty of
time, amber close to expiry or during grace, and red once switching is blocked.
**Help > Copy diagnostics** includes the same summary, so a renewal support call
can be handled from one clipboard paste.

If the Windows clock is moved backwards, the app checks the licence against the
most recent launch date and shows a warning instead of granting extra time.

### Issuing a renewal

The signing key is **not** in this repository. Keep `keys\private_key.json`
offline and backed up; if it is lost, every licence has to be re-issued with a
new key.

```powershell
# One-off, only when rotating the signing key:
python tools\generate_keys.py --out keys\private_key.json

# Issue or renew a licence:
python tools\issue_license.py --key keys\private_key.json `
    --id AFR-2026-002 --customer "Brickspoint Technologies" `
    --site "All sites" --months 6 --seats 50 --out license.json
```

Copy the new `license.json` over the old one and restart the app. No reinstall
and no exe rebuild is needed.

> Client-side licensing is deterrence, not DRM: a determined attacker can patch
> the executable. Pair it with an Authenticode-signed build and a contract that
> names the customer and the renewal terms.

---

## Security and privacy

- The app stores **no credentials**. Twingate handles authentication.
- The licence check is offline: the signed file is verified locally and nothing
  is sent anywhere.
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
Yes. Use **File > Edit branches...** in the app. The list is saved to
`branches.json` next to the exe and reloaded immediately. IT can still edit the
JSON directly if preferred.

**Why must the hotel software be restarted?**
It reads `settings.ini` at start-up. The app changes the file on disk; the
running process keeps its old server until restarted.

**What happens if I select the branch already in use?**
The app reports "already set", does not rewrite the file, and still performs a
connection check so you can confirm it is healthy.

**How many backups are kept?**
The newest 10 files in `backups\`; older ones are removed automatically.

**Can several sites share one installation?**
Each workstation has one deployment folder, normally `C:\hotel`. The app checks
`C:\hotel\settings.ini` first, then the folder next to the exe, so a copy started
from another folder still edits the live hotel configuration. State (last
branch/selection) is per Windows user.

**Does the licence check need internet?**
No. `license.json` is signed and verified locally; there is no activation
server.

**What happens when the licence expires?**
A reminder bar appears 30, 14 and 7 days before expiry. Switching stays
available for 14 days after expiry, then stops until a new `license.json` is
installed. Viewing the branch list and running connection tests never stop.

**Does the installer overwrite `settings.ini` or my licence?**
No. It never reads or writes `settings.ini`. An existing `branches.json` and
`license.json` are kept unless the operator ticks the replace options, and any
replaced file is copied to `C:\hotel\installer-backups` first.

**Why does the app always look in `C:\hotel`?**
That is where the hotel software keeps its live `settings.ini`. The app checks
that folder first, then its own folder and a previously chosen file, so staff
cannot accidentally edit a stale copy. Use **File > Locate settings.ini...** or
`--settings` to override.

**Does it work without Twingate?**
The switch itself works (it is a file edit). Only the connection check depends
on the network path.

**The connection check fails but the hotel software works - why?**
The probe uses generic TCP ports. The application may use a different port; set
`check_ports` for that branch. The server address has already been written.

**Where can I see what the app did?**
`%LOCALAPPDATA%\Afriwave\Switcher\logs\switcher.log`, plus the `backups\` folder next to
`settings.ini`.

---

## Known limitations and roadmap

- Twingate sign-in state is not readable locally; the app can only detect the
  client/service and rely on the TCP probe.
- The app does not launch or restart Twingate (deliberate - avoids interfering
  with an existing session).
- Checks are TCP-level only, not a hotel-application login test.
- Windows-only.
- No auto-update; run the new `SwitcherSetup.exe` during maintenance, which
  keeps site data and refreshes the shortcuts.
- The exe is unsigned.
- The licence is enforced client-side; a patched executable can bypass it. It is
  deterrence backed by the support contract, not DRM.
- Possible future work: code signing, Intune/MSI packaging, optional logging of
  every switch to a shared audit file, and a per-branch application-level health
  check.
