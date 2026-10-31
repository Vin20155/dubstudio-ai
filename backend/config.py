import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
# BASE_DIR holds bundled, read-only assets (frontend, package code when frozen).
# APP_DIR is the folder the user actually launched from and is used for
# writable runtime data (.env, uploads, temp files, database).
IS_FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else BASE_DIR


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


# Load keys from the exe folder first, then fall back to any bundled .env
for _env_path in (APP_DIR / ".env", BASE_DIR / ".env"):
    if _env_path.exists():
        load_dotenv(_env_path)
        ENV_PATH = _env_path
        break
else:
    ENV_PATH = APP_DIR / ".env"
    load_dotenv(ENV_PATH)

BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

DATA_DIR = Path(os.environ.get("KHMERDUB_DATA_DIR") or (APP_DIR / "data"))
if not _writable(DATA_DIR):
    # e.g. installed under Program Files: fall back to the user profile.
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "KhmerDubAI" / "data"

UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
TEMP_DIR = DATA_DIR / "temp"

# Ensure runtime directories exist
for directory in [DATA_DIR, UPLOADS_DIR, PROCESSED_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# FFmpeg Paths - prefer a copy shipped next to the exe, then the system PATH.
_FFMPEG_CANDIDATES = [
    APP_DIR / "bin" / "ffmpeg.exe",
    APP_DIR / "ffmpeg.exe",
    BASE_DIR / "bin" / "ffmpeg.exe",
    BASE_DIR / "ffmpeg.exe",
    Path(r"C:\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe"),
    Path(shutil.which("ffmpeg") or "ffmpeg"),
]
_FFPROBE_CANDIDATES = [
    APP_DIR / "bin" / "ffprobe.exe",
    APP_DIR / "ffprobe.exe",
    BASE_DIR / "bin" / "ffprobe.exe",
    BASE_DIR / "ffprobe.exe",
    Path(r"C:\ffmpeg-8.0.1-essentials_build\bin\ffprobe.exe"),
    Path(shutil.which("ffprobe") or "ffprobe"),
]

KNOWN_FFMPEG_PATHS = [str(p) for p in _FFMPEG_CANDIDATES]
KNOWN_FFPROBE_PATHS = [str(p) for p in _FFPROBE_CANDIDATES]

FFMPEG_PATH = next((str(p) for p in _FFMPEG_CANDIDATES if p.exists()), "ffmpeg")
FFPROBE_PATH = next((str(p) for p in _FFPROBE_CANDIDATES if p.exists()), "ffprobe")

# Khmer Edge-TTS Voices
KHMER_VOICES = {
    "Piseth": {
        "id": "km-KH-PisethNeural",
        "name": "Piseth (Male - ពិសិដ្ឋ)",
        "gender": "Male",
        "locale": "km-KH"
    },
    "Sreymom": {
        "id": "km-KH-SreymomNeural",
        "name": "Sreymom (Female - ស្រីមុំ)",
        "gender": "Female",
        "locale": "km-KH"
    },
    "PisethBoy": {
        "id": "km-KH-PisethNeural-Boy",
        "name": "Piseth Boy (ក្មេងប្រុស)",
        "gender": "Boy",
        "locale": "km-KH"
    },
    "SreymomGirl": {
        "id": "km-KH-SreymomNeural-Girl",
        "name": "Sreymom Girl (ក្មេងស្រី)",
        "gender": "Girl",
        "locale": "km-KH"
    }
}

# Supported STT Engines
STT_ENGINES = {
    "whisper": {
        "name": "Whisper (faster-whisper)",
        "models": ["tiny", "base", "small", "medium", "large-v3"],
        "default_model": "base"
    },
    "sensevoice": {
        "name": "SenseVoiceSmall (FunASR)",
        "models": ["iic/SenseVoiceSmall"],
        "default_model": "iic/SenseVoiceSmall"
    },
    "gemini": {
        "name": "Gemini Multimodal Audio",
        "models": ["auto", "gemini-3-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-pro", "gemini-3.6-pro", "gemini-2.5-flash"],
        "default_model": "auto"
    }
}

# Translation Models (only real, production-available Gemini models)
GEMINI_TRANSLATION_MODELS = [
    "auto",
    "gemini-3-flash",          # Gemini 3 Flash (Latest Generation)
    "gemini-2.5-flash",        # Fastest & recommended
    "gemini-2.5-flash-lite",   # Ultra-lightweight fast option
    "gemini-2.5-pro",          # Best quality
    "gemini-2.0-flash-lite",   # Fast lightweight fallback
    "gemini-1.5-flash",        # Stable proven model
    "gemini-1.5-pro",          # Stable proven pro model
]

# API Keys & Secrets
DEFAULT_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_CODECRAFT_API_KEY = os.environ.get("CODECRAFT_API_KEY", "")
DEFAULT_CODECRAFT_BASE_URL = os.environ.get("CODECRAFT_BASE_URL", "https://codecraftapi.com/v1")


def persist_env_key(key_name: str, key_value: str) -> None:
    """
    Persist an API key or configuration value to the .env file permanently on disk,
    and update current runtime environment and module-level variables.
    """
    key_name = key_name.strip()
    key_value = key_value.strip() if key_value else ""
    os.environ[key_name] = key_value

    global DEFAULT_GEMINI_API_KEY, DEFAULT_CODECRAFT_API_KEY, DEFAULT_CODECRAFT_BASE_URL
    if key_name == "GEMINI_API_KEY":
        DEFAULT_GEMINI_API_KEY = key_value
    elif key_name == "CODECRAFT_API_KEY":
        DEFAULT_CODECRAFT_API_KEY = key_value
    elif key_name == "CODECRAFT_BASE_URL":
        DEFAULT_CODECRAFT_BASE_URL = key_value

    env_path = ENV_PATH
    lines = []
    found = False
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key_name}=") or stripped.startswith(f"{key_name} ="):
            new_lines.append(f"{key_name}={key_value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key_name}={key_value}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[config] Warning: could not write to .env at {env_path}: {e}")

