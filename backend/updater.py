"""One-click self-updater for the packaged Windows app.

Release flow (admin):

1. Bump ``backend/version.py``.
2. Run ``release.ps1`` - it builds the exe, zips it and writes ``update.json``
   containing the version, download URL, size and SHA-256 checksum.
3. Upload ``KhmerDubAI-Windows-Portable.zip`` and ``update.json`` as assets of
   a GitHub release (``release.ps1 -Publish`` does this with the GitHub CLI).

The app reads the manifest from::

    https://github.com/<owner>/<repo>/releases/latest/download/update.json

so the URL never changes between releases. Users only press
Settings -> Updates -> "Check for Updates" -> "Download & Install".
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import APP_DIR, IS_FROZEN
from .version import __version__

# Admin setting, e.g. "myuser/khmerdub-ai" or a full https URL to update.json.
# Can be overridden per install through the .env file / Settings -> Updates.
DEFAULT_UPDATE_SOURCE = ""

MANIFEST_ASSET = "update.json"
PACKAGE_ASSET = "KhmerDubAI-Windows-Portable.zip"
CHECK_CACHE_SECONDS = 300
MAX_MANIFEST_BYTES = 512 * 1024
MAX_PACKAGE_BYTES = 2 * 1024 ** 3
CHUNK_SIZE = 1024 * 1024

_lock = threading.Lock()
_cancel = threading.Event()
_cache: Dict[str, Any] = {"at": 0.0, "data": None}

_state: Dict[str, Any] = {
    "state": "idle",  # idle | downloading | verifying | extracting | restarting | error
    "progress": 0,
    "message": "",
    "error": "",
    "target_version": "",
    "updated_at": 0.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _source() -> str:
    return (os.environ.get("KHMERDUB_UPDATE_SOURCE") or DEFAULT_UPDATE_SOURCE or "").strip()


def _manifest_url(source: Optional[str] = None) -> Optional[str]:
    src = (source if source is not None else _source()).strip()
    if not src:
        return None
    if "://" in src:
        if src.lower().endswith(".json"):
            return src
        return src.rstrip("/") + "/" + MANIFEST_ASSET
    # GitHub "owner/repo" shorthand.
    return f"https://github.com/{src.strip('/')}/releases/latest/download/{MANIFEST_ASSET}"


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "file":
        return True  # local testing
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return True  # local testing
    return False


def _version_key(value: Any) -> tuple:
    numbers = re.findall(r"\d+", str(value or ""))
    key = tuple(int(n) for n in numbers[:4])
    return key + (0,) * (4 - len(key)) if key else (0, 0, 0, 0)


def _dir_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _human_size(num: Optional[int]) -> str:
    if not num:
        return ""
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def _set_state(**changes: Any) -> None:
    with _lock:
        _state.update(changes)
        _state["updated_at"] = time.time()


def _read_url(url: str, timeout: int = 25) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": f"KhmerDubAI/{__version__}",
            "Cache-Control": "no-cache",
            "Accept": "application/json,application/zip,*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(MAX_MANIFEST_BYTES)


def _install_blockers() -> str:
    """Return a human readable reason when self-install is not possible."""
    if sys.platform != "win32":
        return "Automatic updates are only supported on Windows."
    if not IS_FROZEN:
        return "Automatic updates are only available in the packaged .exe app."
    if "KhmerDubAI.old-" in str(APP_DIR):
        return "This copy is an old version kept as a backup. Open the normal KhmerDubAI folder."
    if not _dir_writable(APP_DIR):
        return (
            "The app folder is read-only (for example Program Files). "
            "Move the KhmerDubAI folder to Desktop or Documents, then try again."
        )
    return ""


def _package_url(info: Dict[str, Any], manifest_url: str) -> str:
    url = str(info.get("url") or info.get("download_url") or "").strip()
    if url:
        return url
    src = _source()
    if src and "://" not in src:
        return f"https://github.com/{src.strip('/')}/releases/latest/download/{PACKAGE_ASSET}"
    # Fall back to a sibling asset next to the manifest.
    return manifest_url.rsplit("/", 1)[0] + "/" + PACKAGE_ASSET


def _public_check(info: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    payload = {
        "success": True,
        "configured": True,
        "source": _source(),
        "current_version": __version__,
        "latest_version": info.get("latest_version"),
        "available": bool(info.get("available")),
        "notes": info.get("notes") or "",
        "published_at": info.get("published_at") or "",
        "size": info.get("size"),
        "size_human": _human_size(info.get("size")),
        "mandatory": bool(info.get("mandatory")),
        "can_install": not bool(_install_blockers()),
        "install_reason": _install_blockers(),
        "checked_at": info.get("checked_at") or "",
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Check for updates
# ---------------------------------------------------------------------------
def clear_cache() -> None:
    _cache["at"] = 0.0
    _cache["data"] = None


def check_for_update(force: bool = False) -> Dict[str, Any]:
    source = _source()
    if not source:
        return {
            "success": True,
            "configured": False,
            "source": "",
            "current_version": __version__,
            "available": False,
            "can_install": False,
            "install_reason": (
                "No update source is configured. Ask the app administrator to set "
                "the GitHub repository in Settings -> Updates."
            ),
            "notes": "",
        }

    manifest_url = _manifest_url(source)
    if not manifest_url or not _allowed_url(manifest_url):
        return {
            "success": False,
            "configured": True,
            "source": source,
            "current_version": __version__,
            "available": False,
            "error": "The update source must be a GitHub repository (owner/repo) or an https URL.",
        }

    cached = _cache.get("data")
    if not force and cached and (time.time() - float(_cache.get("at") or 0)) < CHECK_CACHE_SECONDS:
        return dict(cached)

    try:
        raw = _read_url(manifest_url)
        info = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(info, dict):
            raise ValueError("manifest is not a JSON object")
        latest = str(info.get("version") or "").strip()
        if not latest:
            raise ValueError("manifest has no version field")
    except HTTPError as exc:
        if exc.code == 404:
            message = "No update information found. The administrator has not published a release yet."
        else:
            message = f"The update server returned HTTP {exc.code}. Please try again later."
        return {
            "success": False,
            "configured": True,
            "source": source,
            "current_version": __version__,
            "available": False,
            "error": message,
        }
    except (URLError, TimeoutError) as exc:
        return {
            "success": False,
            "configured": True,
            "source": source,
            "current_version": __version__,
            "available": False,
            "error": f"Cannot reach the update server. Check your Internet connection. ({exc})",
        }
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "success": False,
            "configured": True,
            "source": source,
            "current_version": __version__,
            "available": False,
            "error": f"The update information is invalid: {exc}",
        }

    available = _version_key(latest) > _version_key(__version__)
    package_url = _package_url(info, manifest_url)
    if available and not _allowed_url(package_url):
        return {
            "success": False,
            "configured": True,
            "source": source,
            "current_version": __version__,
            "available": False,
            "error": "The update download link is not a secure https URL. Ask the administrator to fix update.json.",
        }

    size = info.get("size")
    try:
        size = int(size) if size else None
    except (TypeError, ValueError):
        size = None

    result = {
        "success": True,
        "configured": True,
        "source": source,
        "current_version": __version__,
        "latest_version": latest,
        "available": available,
        "notes": str(info.get("notes") or "").strip(),
        "published_at": str(info.get("published_at") or ""),
        "size": size,
        "sha256": str(info.get("sha256") or "").strip().lower(),
        "mandatory": bool(info.get("mandatory")),
        "url": package_url,
        "can_install": not bool(_install_blockers()),
        "install_reason": _install_blockers(),
        "checked_at": _now_iso(),
    }
    _cache["at"] = time.time()
    _cache["data"] = result
    return dict(result)


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
def get_status() -> Dict[str, Any]:
    checked = _cache.get("data")
    blockers = _install_blockers()
    payload: Dict[str, Any] = {
        "success": True,
        "current_version": __version__,
        "configured": bool(_source()),
        "source": _source(),
        "can_install": not bool(blockers),
        "install_reason": blockers,
        "state": _state["state"],
        "progress": _state["progress"],
        "message": _state["message"],
        "error": _state["error"],
        "target_version": _state["target_version"],
        "available": bool(checked.get("available")) if checked else None,
        "latest_version": (checked or {}).get("latest_version"),
        "notes": (checked or {}).get("notes") or "",
        "size": (checked or {}).get("size"),
        "size_human": _human_size((checked or {}).get("size")),
        "checked_at": (checked or {}).get("checked_at") or "",
    }
    return payload


def cancel_install() -> Dict[str, Any]:
    if _state["state"] not in {"downloading", "verifying", "extracting"}:
        return {"success": False, "error": "Nothing to cancel."}
    _cancel.set()
    _set_state(state="idle", progress=0, message="Update cancelled.", error="")
    return {"success": True, "message": "Update cancelled."}


def start_install() -> Dict[str, Any]:
    with _lock:
        if _state["state"] in {"downloading", "verifying", "extracting", "restarting"}:
            return {"success": False, "error": "An update is already in progress."}
    _cancel.clear()

    info = _cache.get("data") or check_for_update(force=True)
    if not info.get("success"):
        return {
            "success": False,
            "error": info.get("error") or "Could not check for updates.",
        }
    if not info.get("configured"):
        return {
            "success": False,
            "error": info.get("install_reason") or "No update source is configured.",
        }
    if not info.get("available"):
        return {"success": False, "error": "You already have the latest version."}

    blockers = _install_blockers()
    if blockers:
        return {"success": False, "error": blockers}

    size = info.get("size") or 0
    try:
        free = shutil.disk_usage(str(APP_DIR)).free
        needed = int(size) * 3 + 300 * 1024 * 1024 if size else 4 * 1024 ** 3
        if free < needed:
            return {
                "success": False,
                "error": (
                    "Not enough free disk space for the update. "
                    f"Need about {_human_size(needed)}, only {_human_size(free)} free."
                ),
            }
    except OSError:
        pass

    _set_state(
        state="downloading",
        progress=1,
        message="Starting download...",
        error="",
        target_version=str(info.get("latest_version") or ""),
    )
    thread = threading.Thread(target=_install_worker, args=(dict(info),), daemon=True)
    thread.start()
    return {"success": True, "message": "Download started.", "target_version": info.get("latest_version")}


def _install_worker(info: Dict[str, Any]) -> None:
    work_dir: Optional[Path] = None
    try:
        work_dir = Path(tempfile.mkdtemp(prefix="khmerdub-update-"))
        zip_path = work_dir / "package.zip"
        _download(info, zip_path)

        expected = str(info.get("sha256") or "").lower()
        _set_state(state="verifying", progress=78, message="Checking the downloaded file...")
        if _cancel.is_set():
            raise RuntimeError("Update cancelled.")
        if expected:
            digest = _sha256(zip_path)
            if digest != expected:
                raise RuntimeError(
                    "The downloaded update is damaged (checksum mismatch). Please try again."
                )

        extract_dir = work_dir / "extract"
        _set_state(state="extracting", progress=85, message="Unpacking the new version...")
        _safe_extract(zip_path, extract_dir)

        package_dir = _find_package_dir(extract_dir)
        if package_dir is None:
            raise RuntimeError(
                "The update package is not valid (KhmerDubAI.exe or _internal folder missing)."
            )

        # Stage next to the app so the swap is a fast same-drive rename.
        staging = APP_DIR.parent / f".khmerdub-update-{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        shutil.move(str(package_dir), str(staging))

        product = staging / "KhmerDubAI.exe"
        if not product.exists() or not (staging / "_internal").is_dir():
            raise RuntimeError("The update package is incomplete.")

        _set_state(state="restarting", progress=98, message="Installing update and restarting...")
        script = _write_swap_script(work_dir)
        _launch_detached(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-AppPid",
                str(os.getpid()),
                "-AppDir",
                str(APP_DIR),
                "-StagingDir",
                str(staging),
                "-LogFile",
                str(work_dir / "apply-update.log"),
            ],
            cwd=work_dir,
        )
        _set_state(state="restarting", progress=100, message="Restarting the app...")

        # Give the browser time to receive the "restarting" state, then quit so
        # the helper can replace the files and relaunch the new version.
        threading.Timer(2.5, lambda: os._exit(0)).start()

    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        message = str(exc) or exc.__class__.__name__
        if _cancel.is_set():
            message = "Update cancelled."
            _set_state(state="idle", progress=0, message=message, error="")
        else:
            _set_state(state="error", progress=0, message="Update failed.", error=message)
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)


def _download(info: Dict[str, Any], destination: Path) -> None:
    url = str(info.get("url") or "")
    expected_size = info.get("size") or 0
    request = Request(
        url,
        headers={"User-Agent": f"KhmerDubAI/{__version__}", "Cache-Control": "no-cache"},
    )
    with urlopen(request, timeout=60) as response, open(destination, "wb") as handle:
        total = expected_size or int(response.headers.get("Content-Length") or 0)
        received = 0
        last_update = 0.0
        while True:
            if _cancel.is_set():
                raise RuntimeError("Update cancelled.")
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            received += len(chunk)
            if received > MAX_PACKAGE_BYTES:
                raise RuntimeError("The update package is unexpectedly large. Download stopped.")
            now = time.time()
            if now - last_update > 0.5:
                last_update = now
                if total:
                    pct = min(75, int(received * 75 / total))
                else:
                    pct = min(75, _state["progress"] + 1)
                label = _human_size(received) + (f" / {_human_size(total)}" if total else "")
                _set_state(
                    state="downloading",
                    progress=max(2, pct),
                    message=f"Downloading update... {label}",
                )
    if received == 0:
        raise RuntimeError("The update download was empty. Please try again.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        total = max(1, len(members))
        for index, member in enumerate(members):
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError("The update package contains an unsafe path.")
            zf.extract(member, destination)
            if index % 400 == 0:
                _set_state(
                    state="extracting",
                    progress=min(95, 85 + int(index * 10 / total)),
                    message="Unpacking the new version...",
                )


def _find_package_dir(extract_dir: Path) -> Optional[Path]:
    direct = extract_dir / "KhmerDubAI"
    if (direct / "KhmerDubAI.exe").exists():
        return direct
    for exe in extract_dir.rglob("KhmerDubAI.exe"):
        parent = exe.parent
        if (parent / "_internal").is_dir():
            return parent
    return None


def _write_swap_script(work_dir: Path) -> Path:
    script = work_dir / "apply-update.ps1"
    script.write_text(_SWAP_SCRIPT, encoding="utf-8-sig")
    return script


def _launch_detached(command: list, cwd: Optional[Path] = None) -> None:
    flags = 0
    if sys.platform == "win32":
        # CREATE_NO_WINDOW hides the helper console; do NOT use DETACHED_PROCESS
        # here because PowerShell 5.1 exits immediately without a console.
        flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cleanup_stale(older_than_days: int = 1) -> None:
    """Remove leftover backups / staging folders from previous updates."""
    roots = []
    if IS_FROZEN:
        roots.append(APP_DIR.parent)
    roots.append(Path(tempfile.gettempdir()))

    cutoff = time.time() - older_than_days * 86400
    for root in roots:
        try:
            for pattern in ("KhmerDubAI.old-*", ".khmerdub-update-*", "khmerdub-update-*"):
                for path in root.glob(pattern):
                    try:
                        if path.is_dir() and path.stat().st_mtime < cutoff:
                            shutil.rmtree(path, ignore_errors=True)
                    except OSError:
                        continue
        except Exception:
            continue


# Runs detached after the app exits. It waits for the process to die, swaps the
# folders, restores the user's data/.env, relaunches the app and cleans up.
_SWAP_SCRIPT = r'''
param(
    [Parameter(Mandatory=$true)][int]$AppPid,
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][string]$StagingDir,
    [Parameter(Mandatory=$true)][string]$LogFile
)

$ErrorActionPreference = "Stop"
$backup = ""

# Never keep the app folder as the current directory: Windows refuses to rename
# a directory that is a process's working directory.
try {
    Set-Location -LiteralPath ([System.IO.Path]::GetPathRoot($AppDir))
} catch { }

function Write-Log([string]$message) {
    try {
        Add-Content -LiteralPath $LogFile -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message) -Encoding UTF8
    } catch { }
}

function Start-App {
    $exe = Join-Path $AppDir "KhmerDubAI.exe"
    if (Test-Path -LiteralPath $exe) {
        try {
            Start-Process -FilePath $exe -WorkingDirectory $AppDir | Out-Null
            Write-Log "App restarted."
        } catch {
            Write-Log ("Could not restart the app: " + $_.Exception.Message)
        }
    }
}

try {
    Write-Log "Update helper started. Waiting for the app process to exit (PID $AppPid)..."
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Process -Id $AppPid -ErrorAction SilentlyContinue) -and ((Get-Date) -lt $deadline)) {
        Start-Sleep -Milliseconds 400
    }
    if (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {
        throw "The app did not close in time."
    }
    Start-Sleep -Seconds 1

    # Wait until Windows releases the old executable.
    $oldExe = Join-Path $AppDir "KhmerDubAI.exe"
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $stream = [System.IO.File]::Open($oldExe, "Open", "ReadWrite", "None")
            $stream.Close()
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    $parent = Split-Path -Parent $AppDir
    $backup = Join-Path $parent ("KhmerDubAI.old-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    Write-Log "Moving the current version to $backup"
    Move-Item -LiteralPath $AppDir -Destination $backup

    Write-Log "Activating the new version..."
    Move-Item -LiteralPath $StagingDir -Destination $AppDir

    # Keep the user's projects, database and saved API key.
    $oldData = Join-Path $backup "data"
    $newData = Join-Path $AppDir "data"
    if (Test-Path -LiteralPath $oldData) {
        Write-Log "Restoring the user data folder..."
        if (Test-Path -LiteralPath $newData) {
            Remove-Item -LiteralPath $newData -Recurse -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $oldData -Destination $newData
    }
    $oldEnv = Join-Path $backup ".env"
    if (Test-Path -LiteralPath $oldEnv) {
        Copy-Item -LiteralPath $oldEnv -Destination (Join-Path $AppDir ".env") -Force
    }

    Write-Log "Update installed successfully."
    Start-App
    Start-Sleep -Seconds 3
    try {
        Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction Stop
        Write-Log "Removed the old version backup."
    } catch {
        Write-Log ("Could not remove the backup folder: " + $_.Exception.Message)
    }
    Write-Log "Done."
} catch {
    Write-Log ("UPDATE FAILED: " + $_.Exception.Message)
    if (-not (Test-Path -LiteralPath (Join-Path $AppDir "KhmerDubAI.exe"))) {
        if ($backup -and (Test-Path -LiteralPath $backup)) {
            try {
                if (Test-Path -LiteralPath $AppDir) {
                    Remove-Item -LiteralPath $AppDir -Recurse -Force -ErrorAction SilentlyContinue
                }
                Move-Item -LiteralPath $backup -Destination $AppDir
                Write-Log "Restored the previous version."
            } catch {
                Write-Log ("Could not restore the backup: " + $_.Exception.Message)
            }
        }
    }
    Start-App
}
'''
