import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# When frozen by PyInstaller the exe lives in the outer folder (e.g.
# dist/KhmerDubAI/), while bundled code/assets live in "_internal".
# __file__ points inside "_internal", so resolve the real app folder from the
# executable itself. This keeps writable data (uploads, temp files, .env)
# next to the exe instead of inside the read-only bundle.
IS_FROZEN = bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _app_dir()
if not IS_FROZEN:
    # Add project root to sys.path
    sys.path.insert(0, str(BASE_DIR))

# Silence harmless Windows asyncio ConnectionResetError (WinError 10054) on client disconnect
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _silence_connection_lost(self, exc=None):
            try:
                return _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _silence_connection_lost
    except Exception:
        pass

# pyrefly: ignore [missing-import]
import uvicorn

# ---------------------------------------------------------------------------
# Runtime folders / logging
# ---------------------------------------------------------------------------
DEFAULT_HOST = os.environ.get("KHMERDUB_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("KHMERDUB_PORT", "8000"))
PORT_SCAN_LIMIT = 20
STARTUP_LOG = BASE_DIR / "startup.log"


def _is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _runtime_base() -> Path:
    """Pick a writable location for data/logs (exe folder, else LOCALAPPDATA)."""
    if _is_writable(BASE_DIR):
        return BASE_DIR
    fallback = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "KhmerDubAI"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


RUNTIME_BASE = _runtime_base()
DATA_DIR = RUNTIME_BASE / "data"
# Tell backend.config where to store uploads/temp/DB files.
os.environ.setdefault("KHMERDUB_DATA_DIR", str(DATA_DIR))
STARTUP_LOG = RUNTIME_BASE / "startup.log"

# Dump Python and native (access violation / abort) tracebacks to startup.log.
# Without this the console window can close before the reason is visible.
try:
    import faulthandler

    _crash_log = open(STARTUP_LOG, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_log)
except Exception:
    pass


def log(message: str = "") -> None:
    print(message, flush=True)
    try:
        with open(STARTUP_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Port / instance helpers
# ---------------------------------------------------------------------------
def _url(port: int, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{port}"


def _is_our_app(port: int, timeout: float = 0.5) -> bool:
    """Return True when a KhmerDub AI server already answers on this port."""
    try:
        with urlopen(f"{_url(port)}/health", timeout=timeout) as response:
            body = response.read(200)
        return b'"status":"ok"' in body.replace(b" ", b"")
    except (URLError, OSError, ValueError):
        return False


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform == "win32":
            # Match uvicorn behaviour (no address reuse) so a busy port is detected.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((DEFAULT_HOST, port))
        except OSError:
            return False
    return True


def _find_available_port(start: int = DEFAULT_PORT, limit: int = PORT_SCAN_LIMIT) -> int:
    for port in range(start, start + limit):
        if _port_is_free(port):
            return port
    raise RuntimeError(
        f"No free port found in range {start}-{start + limit - 1}. "
        "Close other applications using these ports and try again."
    )


def _open_browser_when_ready(port: int = DEFAULT_PORT) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urlopen(_url(port), timeout=1):
                if not webbrowser.open(f"http://localhost:{port}"):
                    log(f"Could not open a browser automatically. Visit http://localhost:{port}")
                return
        except OSError:
            time.sleep(0.5)

    log("The web server did not become ready. Check the startup errors above.")


def _reuse_running_instance() -> bool:
    """If the app is already running, just focus the browser instead of crashing."""
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT):
        if _port_is_free(port):
            # Nothing is listening on this port.
            continue
        if _is_our_app(port):
            log(f"KhmerDub AI is already running on http://localhost:{port} - opening browser.")
            webbrowser.open(f"http://localhost:{port}")
            return True
    return False


def _run_server(port: int) -> None:
    log("==================================================================")
    log("       KhmerDub AI - Video Dubbing Studio (Whisper + SenseVoice + Gemini + Edge-TTS)")
    log("==================================================================")
    log(f"Starting Web Server at http://localhost:{port} ...")
    log(f"Data folder: {DATA_DIR}")

    threading.Thread(target=lambda: _open_browser_when_ready(port), daemon=True).start()

    uvicorn.run(
        "backend.main:app",
        host=DEFAULT_HOST,
        port=port,
        reload=not getattr(sys, "frozen", False),
    )


def _wait_before_exit() -> None:
    """Keep the console window open after a crash so the error is readable."""
    if not getattr(sys, "frozen", False):
        return
    try:
        if sys.stdin and sys.stdin.isatty():
            input("\nStartup failed. Press Enter to close this window...")
        else:
            time.sleep(30)
    except Exception:
        time.sleep(30)


def main() -> None:
    try:
        if _reuse_running_instance():
            return

        port = _find_available_port()
        _run_server(port)

    except SystemExit:
        # uvicorn calls sys.exit(1) when it cannot bind the port.
        if _reuse_running_instance():
            return
        log("Could not start the web server. Another program may be using the port.")
        log(traceback.format_exc())
        _wait_before_exit()
        raise
    except Exception as exc:
        log(f"FATAL: {type(exc).__name__}: {exc}")
        log(traceback.format_exc())
        _wait_before_exit()
        raise


if __name__ == "__main__":
    main()
