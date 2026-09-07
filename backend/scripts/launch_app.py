"""One-click launcher for the SovereignAI Workbench (used by start.bat).

Starts (or reuses) the local FastAPI backend and the Vite frontend, waits until
both answer HTTP, then opens the browser at http://127.0.0.1:5173.

Usage:
    python backend/scripts/launch_app.py            # start + open browser
    python backend/scripts/launch_app.py --stop     # stop servers on :8000/:5173

Everything runs locally. Server output is written to temp files:
    %TEMP%/sovereignai-backend.log and %TEMP%/sovereignai-frontend.log
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"
BACKEND_URL = f"http://{HOST}:8000"
FRONTEND_URL = f"http://{HOST}:5173"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def log(*parts) -> None:
    print("[launch]", *parts, flush=True)


def find_python() -> Path | None:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
        BACKEND / ".venv" / "Scripts" / "python.exe",
        BACKEND / ".venv" / "bin" / "python",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def find_npm() -> str | None:
    import shutil

    for name in ("npm.cmd", "npm"):
        path = shutil.which(name)
        if path:
            return path
    return None


def port_open(port: int, host: str = HOST) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def _logfile(name: str):
    return open(os.path.join(tempfile.gettempdir(), name), "ab")


def start_backend(python: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    log("starting backend:", BACKEND_URL)
    subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app",
         "--host", HOST, "--port", "8000"],
        cwd=str(BACKEND), env=env,
        stdout=_logfile("sovereignai-backend.log"),
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def start_frontend() -> None:
    npm = find_npm()
    if npm is None:
        log("ERROR: npm not found on PATH. Install Node.js and run: cd frontend && npm install")
        return
    log("starting frontend:", FRONTEND_URL)
    subprocess.Popen(
        [npm, "run", "dev", "--", "--host", HOST],
        cwd=str(FRONTEND),
        stdout=_logfile("sovereignai-frontend.log"),
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def wait_for(url: str, seconds: int, what: str) -> bool:
    log("waiting for", what, "to come up...")
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_ok(url):
            log(what, "is up:", url)
            return True
        time.sleep(1)
    log("WARNING:", what, "did not answer within", seconds, "s")
    log("check the log file for errors:", os.path.join(tempfile.gettempdir(),
                                                       "sovereignai-backend.log"))
    return False


def stop_servers() -> None:
    """Kill whatever listens on the app's ports (Windows netstat/taskkill)."""
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        pids: set[str] = set()
        for line in out.splitlines():
            for port in ("8000", "5173"):
                if f":{port}" in line and "LISTENING" in line.upper():
                    toks = line.split()
                    if toks and toks[-1].isdigit():
                        pids.add(toks[-1])
        if not pids:
            log("nothing was running on :8000 / :5173")
            return
        for pid in pids:
            log("stopping pid", pid)
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                           capture_output=True)
        return
    log("run: kill $(lsof -ti:8000,5173)  (or use Docker: docker compose down)")


def main() -> int:
    if "--stop" in sys.argv:
        stop_servers()
        return 0

    log("SovereignAI Workbench launcher")
    log("project folder:", ROOT)

    # prerequisites ---------------------------------------------------------
    python = find_python()
    if python is None:
        log("Python environment not found. Run once:")
        log("  python -m venv .venv")
        log(f"  {'.venv' + os.sep}Scripts{os.sep}python -m pip install -r backend/requirements.txt")
        log("  cd frontend && npm install && cd ..")
        return 1
    if not (FRONTEND / "node_modules").is_dir():
        log("Frontend dependencies missing. Run once: cd frontend && npm install && cd ..")
        return 1

    # one-time (online) embedding model provisioning ------------------------
    model_cache = (Path.home() / ".cache" / "chroma" / "onnx_models"
                   / "all-MiniLM-L6-v2" / "onnx" / "model.onnx")
    if not model_cache.is_file():
        log("first run: provisioning the local embedding model (needs internet once)...")
        subprocess.run([str(python), str(BACKEND / "scripts" / "embed_setup.py")],
                       cwd=str(BACKEND))

    # start servers if not already running ----------------------------------
    if port_open(8000):
        log("backend already running:", BACKEND_URL)
    else:
        start_backend(python)
        wait_for(BACKEND_URL + "/api/health", 60, "backend")

    if port_open(5173):
        log("frontend already running:", FRONTEND_URL)
    else:
        start_frontend()
        wait_for(FRONTEND_URL, 45, "frontend")

    if os.environ.get("NO_BROWSER", "").lower() not in ("1", "true", "yes"):
        log("opening browser at", FRONTEND_URL)
        webbrowser.open(FRONTEND_URL)
    else:
        log("browser launch skipped (NO_BROWSER set)")
    log("done. To stop later, run stop.bat (or this script with --stop).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
