# HedgeFund One-Click Launcher — Design Spec
**Date:** 2026-05-14
**Status:** Approved

---

## Goal

A customer-facing launcher that starts the HedgeFund server silently, waits until it is ready, and opens the browser automatically. No terminal window is ever visible. Logs are stored in the existing `logs/` directory. A shutdown button in the web UI is the primary stop mechanism, with a fallback `.vbs` file for when the browser is unavailable.

---

## Files

### New files (project root)

| File | Purpose |
|------|---------|
| `launch.py` | Core launcher: starts uvicorn silently, writes PID, polls until ready, opens browser |
| `Start HedgeFund.vbs` | Silent entry point — calls `pythonw.exe launch.py` with hidden window |
| `Stop HedgeFund.vbs` | Fallback shutdown — reads PID file, kills process, cleans up |

### Modified files

| File | Change |
|------|--------|
| `main.py` | Add `POST /shutdown` endpoint |
| `templates/index.html` | Add "Stop Server" button in header |

---

## launch.py

**Behaviour:**
1. Opens `logs/server.log` in append mode; writes a `--- START {timestamp} ---` separator line
2. Checks if port 8000 is already in use (`socket.connect`). If the server is already running, skips to step 5
3. Spawns uvicorn via `subprocess.Popen` using the venv Python (`venv/Scripts/python.exe`), passing `logs/server.log` as both stdout and stderr, with `creationflags=subprocess.CREATE_NO_WINDOW`
4. Writes the child PID to `logs/server.pid`
5. Polls `GET http://127.0.0.1:8000/` every 500ms for up to 15 seconds. If the server does not respond, writes an error to `logs/server.log` and exits without opening the browser
6. Opens `http://127.0.0.1:8000/` via `webbrowser.open()`
7. The launcher process itself exits — the uvicorn subprocess continues running independently

**Dependencies:** stdlib only (`subprocess`, `socket`, `time`, `webbrowser`, `urllib.request`, `pathlib`, `datetime`)

---

## Start HedgeFund.vbs

Single-purpose: invokes `launch.py` with no visible window.

```vbs
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1)
shell.Run "venv\Scripts\pythonw.exe launch.py", 0, False
```

- Window style `0` = hidden, no flash
- `False` = fire-and-forget, VBScript exits immediately
- `CurrentDirectory` set to project root so relative paths in `launch.py` resolve correctly

---

## Stop HedgeFund.vbs

Fallback for stopping the server when the browser is unavailable.

**Behaviour:**
1. Reads `logs/server.pid`
2. If the file exists, calls `taskkill /PID <pid> /F` via `WScript.Shell.Run`
3. Deletes `logs/server.pid`
4. Shows a brief message box: "HedgeFund server stopped."
5. If the PID file does not exist, shows: "Server does not appear to be running."

---

## POST /shutdown endpoint (main.py)

```
POST /shutdown
→ 200 {"status": "shutting_down"}
```

**Behaviour:**
- Starts a 500ms background thread that calls `os.kill(os.getpid(), signal.CTRL_C_EVENT)` (Windows SIGINT — triggers uvicorn's graceful shutdown handler)
- Returns the 200 response immediately before the signal fires
- Also deletes `logs/server.pid` if it exists

**Why CTRL_C_EVENT not os._exit:** Uvicorn catches SIGINT and runs its shutdown lifecycle (closes DB connections, finishes in-flight requests). `os._exit` would kill the process instantly, potentially corrupting the SQLite DB.

---

## Shutdown button (templates/index.html)

- Location: top-right of the existing header/nav bar, visually separated from primary actions
- Style: small, muted — e.g. grey outline button labelled "⏻ Stop Server"
- On click: `fetch('POST /shutdown')` → replaces button text with "Server stopped — you can close this tab."
- No page navigation or reload — the response is the last thing the user sees

---

## Logging

All server stdout/stderr is appended to `logs/server.log`. Each launch session is separated by:

```
--- START 2026-05-14T16:30:00 ---
```

The existing `logs/` directory is already `.gitignore`d. `logs/server.pid` is also excluded.

---

## Error cases

| Scenario | Behaviour |
|----------|-----------|
| Server already running on port 8000 | `launch.py` skips startup, opens browser directly |
| Server fails to start within 15s | Error written to `server.log`, browser not opened, launcher exits silently |
| `venv/Scripts/python.exe` not found | Error written to `server.log`, exits silently — user must run `python -m venv venv && pip install -r requirements.txt` first |
| `/shutdown` called but PID file missing | Endpoint still kills current process; no error |
| `Stop HedgeFund.vbs` run when server not running | Shows "Server does not appear to be running." message |
| PID belongs to a different process (stale PID file) | `taskkill` will fail silently; VBS shows a "stopped" message regardless — acceptable edge case |

---

## Out of scope

- Custom `.ico` icon for the VBS files
- Auto-restart on crash
- Multi-user / remote access (localhost only)
- Port configurability (hardcoded 8000)
