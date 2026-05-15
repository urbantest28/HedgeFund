"""
One-click launcher: starts uvicorn silently, waits until ready, opens browser.
Run via: pythonw.exe launch.py  (no console window)
"""
import subprocess
import socket
import time
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "logs" / "server.log"
PID_FILE = BASE_DIR / "logs" / "server.pid"
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"
POLL_INTERVAL = 0.5
POLL_TIMEOUT = 15


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _port_in_use() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


def _server_ready() -> bool:
    try:
        urllib.request.urlopen(URL, timeout=2)
        return True
    except Exception:
        return False


def main() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    _log(f"--- START {timestamp} ---")

    if _port_in_use():
        _log("Port 8000 already in use — skipping startup, opening browser.")
    else:
        if not VENV_PYTHON.exists():
            _log(
                f"ERROR: venv not found at {VENV_PYTHON}. "
                "Run: python -m venv venv && pip install -r requirements.txt"
            )
            return

        proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
            stdout=open(LOG_FILE, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        _log(f"Spawned uvicorn PID {proc.pid}")

        deadline = time.time() + POLL_TIMEOUT
        while time.time() < deadline:
            if _server_ready():
                break
            time.sleep(POLL_INTERVAL)
        else:
            _log("ERROR: Server did not respond within 15 seconds — browser not opened.")
            return

    webbrowser.open(URL)
    _log("Browser opened.")


if __name__ == "__main__":
    main()
