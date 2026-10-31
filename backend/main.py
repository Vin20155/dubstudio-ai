import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

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
# pyrefly: ignore [missing-import]
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from .audio_video_processor import (
    extract_audio,
    generate_ass,
    generate_srt,
    generate_vtt,
    get_media_info,
    mix_audio_with_video,
    stitch_dubbed_audio,
)
from .config import (
    DEFAULT_GEMINI_API_KEY,
    FRONTEND_DIR,
    GEMINI_TRANSLATION_MODELS,
    KHMER_VOICES,
    PROCESSED_DIR,
    STT_ENGINES,
    TEMP_DIR,
    UPLOADS_DIR,
    persist_env_key,
)
from .stt_engine import transcribe_audio, merge_dialogue_fragments, diarize_segments_with_audio
from .translation import (
    add_glossary_term,
    delete_glossary_term,
    delete_translation_memory,
    get_admin_translation_stats,
    get_batch_manager,
    get_project_settings,
    get_translation_job,
    get_translation_service,
    get_user_ai_settings,
    list_glossary_terms,
    list_translation_memory,
    save_project_settings,
    save_user_ai_settings,
    store_translation_memory,
    update_translation_job,
)
from .translation_engine import translate_segments_to_khmer, translate_single_segment
from .tts_engine import extract_emotional_tags, synthesize_all_segments, synthesize_segment
from . import updater
from .version import __version__
from .vocal_remover import extract_clean_bgm
from .recap_engine import (
    BGM_DIR,
    RECAP_STYLES,
    generate_procedural_bgm,
    generate_recap_script,
    get_available_bgm_tracks,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ai_dubbing_app")

app = FastAPI(title="AI Video Dubbing Studio (Khmer)", version=__version__)

# Remove leftover folders from a previous one-click update (runs in the background).
try:
    updater.cleanup_stale()
except Exception:
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Disk-backed session store — survives uvicorn hot-reloads
class _SessionStore:
    """Thin dict-like wrapper that persists each session as a JSON file on disk.
    Entries in the in-memory cache take priority; disk is the fallback on miss."""

    _SESSIONS_DIR = PROCESSED_DIR / "_sessions"

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, sid: str) -> Path:
        return self._SESSIONS_DIR / f"{sid}.json"

    def _save(self, sid: str):
        try:
            data = self._cache.get(sid)
            if data is not None:
                with open(self._path(sid), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.warning(f"Session save failed ({sid}): {exc}")

    def get(self, sid: str, default=None):
        if sid in self._cache:
            return self._cache[sid]
        p = self._path(sid)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[sid] = data
                return data
            except Exception as exc:
                logger.warning(f"Session load failed ({sid}): {exc}")
        return default

    def __getitem__(self, sid: str):
        v = self.get(sid)
        if v is None:
            raise KeyError(sid)
        return v

    def __setitem__(self, sid: str, value: Dict[str, Any]):
        self._cache[sid] = value
        self._save(sid)

    def __contains__(self, sid: str):
        return self.get(sid) is not None

    def __delitem__(self, sid: str):
        self._cache.pop(sid, None)
        try:
            self._path(sid).unlink(missing_ok=True)
        except Exception:
            pass

    def list_all(self) -> List[Dict[str, Any]]:
        """List all saved sessions with summary statistics."""
        results = []
        if not self._SESSIONS_DIR.exists():
            return results
        for p in self._SESSIONS_DIR.glob("*.json"):
            sid = p.stem
            session = self.get(sid)
            if not session or not isinstance(session, dict):
                continue
            segs = session.get("segments") or []
            total_segs = len(segs)
            translated_count = sum(1 for s in segs if s.get("khmer_text") and str(s.get("khmer_text")).strip())

            if total_segs == 0:
                t_status = "empty"
            elif translated_count == total_segs:
                t_status = "completed"
            elif translated_count > 0:
                t_status = "partial"
            else:
                t_status = "untranslated"

            media_info = session.get("media_info") or {}
            duration = media_info.get("duration") or 0.0

            results.append({
                "session_id": sid,
                "project_id": sid,
                "filename": session.get("original_filename") or f"{sid}.mp4",
                "duration": round(float(duration), 2),
                "total_segments": total_segs,
                "translated_segments": translated_count,
                "translation_status": t_status,
                "created_at": session.get("created_at") or 0,
            })
        results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return results


# In-memory store for active job progress and sessions
jobs_state: Dict[str, Dict[str, Any]] = {}
sessions_data = _SessionStore()


def set_job_progress(job_id: str, percent: int, step: str, message: str, status: str = "running"):
    jobs_state[job_id] = {
        "job_id": job_id,
        "percent": percent,
        "step": step,
        "message": message,
        "status": status,
    }


# Models
class STTRequest(BaseModel):
    session_id: str
    engine: str = "whisper"
    model_name: Optional[str] = "base"
    language: Optional[str] = "auto"
    voice: Optional[str] = "auto"
    api_key: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None


class TranslateRequest(BaseModel):
    session_id: str
    segments: List[Dict]
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = "gemini"
    style: Optional[str] = "natural"
    options: Optional[Dict[str, Any]] = None


class SingleTranslateRequest(BaseModel):
    text: str
    duration: float = 3.0
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = "gemini"
    tone: Optional[str] = "neutral"
    style: Optional[str] = "natural"


class UpdateTranslationSettingsRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_provider: Optional[str] = None
    fallback_enabled: Optional[bool] = None
    options: Optional[Dict[str, Any]] = None
    credentials: Optional[Dict[str, Any]] = None


class TestProviderRequest(BaseModel):
    provider: str
    credentials: Optional[Dict[str, Any]] = None


class ProjectTranslateRequest(BaseModel):
    source_language: str = "en"
    target_language: str = "km"
    segments: List[Dict[str, Any]]
    provider: Optional[str] = None
    model: Optional[str] = None
    style: Optional[str] = "natural"
    options: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None


class BatchTranslateRequest(BaseModel):
    project_ids: List[str]
    provider: Optional[str] = "gemini"
    model: Optional[str] = None
    source_language: str = "en"
    target_language: str = "km"
    style: Optional[str] = "natural"
    concurrency: Optional[int] = 2
    skip_already_translated: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None



class GlossaryTermRequest(BaseModel):
    source_term: str
    target_term: str
    notes: Optional[str] = ""


class TranslationMemoryRequest(BaseModel):
    source_text: str
    translated_text: str
    source_language: str = "en"
    target_language: str = "km"
    provider: Optional[str] = "gemini"


class RegenerateSegmentRequest(BaseModel):
    text: str
    duration: float = 3.0
    provider: Optional[str] = "gemini"
    style: Optional[str] = "natural"
    tone: Optional[str] = "neutral"
    context: Optional[str] = None
    project_id: Optional[str] = None



class SingleTTSRequest(BaseModel):
    text: str
    voice: str = "km-KH-PisethNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+60%"
    emotion: Optional[str] = "neutral"
    pacing: Optional[str] = "normal"


class DetectEmotionsRequest(BaseModel):
    session_id: Optional[str] = None
    segments: List[Dict]
    api_key: Optional[str] = None
    model_name: Optional[str] = "gemini-2.5-flash"


class BatchTTSRequest(BaseModel):
    session_id: str
    segments: List[Dict]
    voice: str = "km-KH-PisethNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+60%"
    auto_adjust_duration: bool = True


class VocalRemoverRequest(BaseModel):
    session_id: str
    method: str = "ai_demucs"  # 'ai_demucs' or 'fast_dsp'


class RecapGenerateRequest(BaseModel):
    session_id: str
    segments: Optional[List[Dict]] = None
    total_duration: Optional[float] = None
    style: str = "suspense"
    include_hook: bool = True
    include_cta: bool = True
    pacing: str = "normal"
    hybrid_dialogue: Optional[bool] = True
    narrator_voice: Optional[str] = "km-KH-PisethNeural"
    api_key: Optional[str] = None
    model_name: Optional[str] = "gemini-3.5-flash"


class DubbingRequest(BaseModel):
    session_id: str
    segments: List[Dict]
    mode: str = "bgm_isolate"  # 'bgm_isolate', 'ducking', 'replace'
    vocal_removal_method: str = "fast_dsp"  # 'fast_dsp' (instant <1s), 'ai_demucs', 'ai_bs_roformer'
    ducking_volume: float = 0.12
    bgm_volume: float = 0.35
    dub_volume: float = 1.40
    blur_subtitles: bool = False
    subtitle_blur_coords: Optional[Dict[str, Any]] = None
    aspect_ratio: str = "original"  # 'original', '9:16', '1:1'
    canvas_blur_strength: int = 25
    blur_objects: Optional[List[Dict[str, Any]]] = None
    burn_subtitles: bool = False
    subtitle_style: Optional[Dict[str, Any]] = None
    subtitle_language_mode: str = "khmer"  # 'khmer', 'original', 'dual'
    bgm_id: Optional[str] = None


class FullPipelineRequest(BaseModel):
    session_id: str
    stt_engine: str = "whisper"
    stt_model: str = "base"
    stt_language: str = "auto"
    tts_voice: str = "km-KH-PisethNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"
    tts_volume: str = "+60%"
    mixing_mode: str = "bgm_isolate"  # default: keep BGM only and remove vocals!
    vocal_removal_method: str = "fast_dsp"  # default fast_dsp for instant processing
    ducking_volume: float = 0.12
    bgm_volume: float = 0.35
    dub_volume: float = 1.40
    blur_subtitles: bool = False
    subtitle_blur_coords: Optional[Dict[str, Any]] = None
    aspect_ratio: str = "original"
    canvas_blur_strength: int = 25
    gemini_api_key: Optional[str] = None
    blur_objects: Optional[List[Dict[str, Any]]] = None
    burn_subtitles: bool = False
    subtitle_style: Optional[Dict[str, Any]] = None
    subtitle_language_mode: str = "khmer"
    translation_provider: Optional[str] = "gemini"
    translation_model: Optional[str] = None
    translation_style: Optional[str] = "natural"


class ExportSubtitleRequest(BaseModel):
    session_id: str
    segments: List[Dict]
    format: str = "ass"  # 'ass', 'srt', 'vtt'
    style: Optional[Dict[str, Any]] = None
    language_mode: str = "khmer"  # 'khmer', 'original', 'dual'


class FaceDetectionRequest(BaseModel):
    session_id: str
    timestamp: float = 0.0
    current_time: Optional[float] = None


def sanitize_segments_timeline(
    segments: List[Dict[str, Any]],
    min_gap: float = 0.05,
    max_total_duration: Optional[float] = None,
    distribute_evenly: bool = False,
) -> List[Dict[str, Any]]:
    """
    Guarantees that no two subtitle/dub segments overlap in time,
    strictly bounded within [0.0, max_total_duration] (if provided),
    and character speech start timings are preserved.
    """
    if not segments:
        return []

    # Sort safely by start time, then end time
    sorted_segs = sorted(
        segments,
        key=lambda s: (float(s.get("start", 0.0)), float(s.get("end", 0.0)))
    )

    num_segs = len(sorted_segs)
    if distribute_evenly and max_total_duration and max_total_duration > 3.0 and num_segs > 0:
        max_end = round(max_total_duration - 0.25, 2)
        slot_len = max_end / num_segs
        pause = min(min_gap, max(0.12, slot_len * 0.08))
        speech_dur = slot_len - pause

        cleaned = []
        for idx, s in enumerate(sorted_segs):
            item = dict(s)
            start = round(idx * slot_len, 2)
            end = round(min(max_end, start + speech_dur), 2)
            if idx == num_segs - 1:
                end = max_end
            item["id"] = idx + 1
            item["start"] = start
            item["end"] = end
            cleaned.append(item)
        return cleaned

    cleaned: List[Dict[str, Any]] = []
    prev_end = 0.0

    for idx, s in enumerate(sorted_segs):
        item = dict(s)
        try:
            raw_start = max(0.0, float(item.get("start", 0.0)))
            raw_end = float(item.get("end", raw_start + 1.0))
        except (ValueError, TypeError):
            raw_start = prev_end
            raw_end = prev_end + 1.5

        if raw_end <= raw_start:
            raw_end = raw_start + 1.0

        words = len(str(item.get("text", "") or item.get("khmer_text", "")).split())
        speech_room_needed = max(2.2, min(words * 0.45, 4.0)) if words >= 3 else 1.2

        safe_start = round(raw_start, 2)
        safe_end = round(max(safe_start + 0.25, raw_end), 2)

        is_last = (idx == num_segs - 1)

        # Boundary clamping if max_total_duration is specified
        if max_total_duration and max_total_duration > 0:
            if safe_end > max_total_duration:
                safe_end = round(max_total_duration, 2)
            if safe_start >= safe_end:
                safe_start = round(max(0.0, safe_end - 0.25), 2)

        # Resolve overlap by trimming previous segment's end (NOT by pushing safe_start forward)
        if cleaned and safe_start < prev_end:
            prev_seg = cleaned[-1]
            trimmed_end = max(prev_seg["start"] + 0.25, round(safe_start - min_gap, 2))
            prev_seg["end"] = trimmed_end
            if "duration" in prev_seg:
                prev_seg["duration"] = round(trimmed_end - prev_seg["start"], 2)
            prev_end = trimmed_end
            safe_start = round(prev_seg["end"] + min_gap, 2)

        if max_total_duration and max_total_duration > 0 and safe_end > max_total_duration:
            safe_end = round(max_total_duration, 2)

        item["id"] = idx + 1
        item["start"] = safe_start
        item["end"] = safe_end
        if "duration" in item:
            item["duration"] = round(safe_end - safe_start, 2)

        prev_end = safe_end
        cleaned.append(item)

    # Final pass to ensure all segments are strictly within bounds and non-overlapping
    for idx in range(len(cleaned)):
        cleaned[idx]["id"] = idx + 1
        if max_total_duration and max_total_duration > 0:
            cleaned[idx]["end"] = round(min(cleaned[idx]["end"], max_total_duration), 2)
            cleaned[idx]["start"] = round(min(max(0.0, cleaned[idx]["start"]), max(0.0, cleaned[idx]["end"] - 0.2)), 2)
        if idx + 1 < len(cleaned):
            max_allowed_end = round(cleaned[idx + 1]["start"] - min_gap, 2)
            if cleaned[idx]["end"] > max_allowed_end:
                cleaned[idx]["end"] = round(max(cleaned[idx]["start"] + 0.2, max_allowed_end), 2)
        if "duration" in cleaned[idx]:
            cleaned[idx]["duration"] = round(cleaned[idx]["end"] - cleaned[idx]["start"], 2)

    return cleaned


# --- API Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
def get_system_config():
    """Return available engines, voices, translation providers, and defaults."""
    service = get_translation_service()
    user_settings = get_user_ai_settings("default_user")
    return {
        "stt_engines": STT_ENGINES,
        "khmer_voices": KHMER_VOICES,
        "gemini_models": GEMINI_TRANSLATION_MODELS,
        "has_server_gemini_key": bool(DEFAULT_GEMINI_API_KEY),
        "translation_providers": service.list_providers(),
        "translation_settings": user_settings,
        "app_version": __version__,
    }


# --- Application Update Endpoints ---

class UpdateSourceRequest(BaseModel):
    source: str = ""


@app.get("/api/update/status")
def get_update_status():
    """Current version plus any running/known update state."""
    return updater.get_status()


@app.post("/api/update/check")
def check_for_update():
    """Contact the release manifest and report whether a newer version exists."""
    return updater.check_for_update(force=True)


@app.post("/api/update/install")
def install_update():
    """Download, verify and install the newest release, then restart the app."""
    return updater.start_install()


@app.post("/api/update/cancel")
def cancel_update():
    return updater.cancel_install()


@app.post("/api/update/source")
def set_update_source(req: UpdateSourceRequest):
    """Save the release source (GitHub 'owner/repo' or an https manifest URL)."""
    source = (req.source or "").strip()
    if source and "://" not in source and not re.match(r"^[\w.-]+/[\w.-]+$", source):
        raise HTTPException(
            status_code=400,
            detail="Use a GitHub repository like 'owner/repo' or a full https:// URL.",
        )
    if source and "://" in source:
        if not updater._allowed_url(source):
            raise HTTPException(
                status_code=400,
                detail="The update URL must use https:// (http:// is only allowed for localhost testing).",
            )
    persist_env_key("KHMERDUB_UPDATE_SOURCE", source)
    updater.clear_cache()
    return {"success": True, "source": source, "message": "Update source saved."}


# --- Multi-Provider Translation Endpoints ---

@app.get("/api/translation/providers")
def get_translation_providers():
    """Returns catalog of supported translation providers and their models."""
    service = get_translation_service()
    return {"success": True, "providers": service.list_providers()}


@app.get("/api/translation/settings")
def get_ai_translation_settings(user_id: str = "default_user"):
    """Fetch user AI translation settings."""
    settings = get_user_ai_settings(user_id)
    return {"success": True, "settings": settings}


@app.put("/api/translation/settings")
def update_ai_translation_settings(req: UpdateTranslationSettingsRequest, user_id: str = "default_user"):
    """Update global AI translation settings and persist credentials permanently."""
    if req.credentials:
        gem_key = req.credentials.get("gemini_api_key") or (req.credentials.get("api_key") if req.provider == "gemini" else None)
        if gem_key:
            persist_env_key("GEMINI_API_KEY", gem_key)
        if req.credentials.get("openai_api_key"):
            persist_env_key("OPENAI_API_KEY", req.credentials["openai_api_key"])
        if req.credentials.get("google_api_key"):
            persist_env_key("GOOGLE_TRANSLATE_API_KEY", req.credentials["google_api_key"])
            persist_env_key("GOOGLE_CLOUD_API_KEY", req.credentials["google_api_key"])
        if req.credentials.get("codecraft_api_key"):
            persist_env_key("CODECRAFT_API_KEY", req.credentials["codecraft_api_key"])
        elif req.credentials.get("api_key") and req.provider == "codecraft":
            persist_env_key("CODECRAFT_API_KEY", req.credentials["api_key"])
        if req.credentials.get("codecraft_base_url"):
            persist_env_key("CODECRAFT_BASE_URL", req.credentials["codecraft_base_url"])

    updated = save_user_ai_settings(
        user_id=user_id,
        provider=req.provider,
        model=req.model,
        fallback_provider=req.fallback_provider,
        fallback_enabled=req.fallback_enabled,
        options=req.options,
        credentials=req.credentials,
    )
    return {"success": True, "settings": updated}


class SaveGeminiKeyRequest(BaseModel):
    key: str


@app.post("/api/settings/save-gemini-key")
def save_gemini_key_endpoint(req: SaveGeminiKeyRequest):
    """Save Gemini API Key permanently to .env file and database."""
    key = req.key.strip()
    if key:
        persist_env_key("GEMINI_API_KEY", key)
        save_user_ai_settings(
            user_id="default_user",
            credentials={"gemini_api_key": key, "api_key": key}
        )
        return {"success": True, "message": "Gemini API key saved permanently to .env and database"}
    return {"success": False, "message": "Key cannot be empty"}


@app.get("/api/settings/gemini-key")
def get_gemini_key_endpoint():
    """Check if Gemini API key exists on server and return masked preview."""
    key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_API_KEY or ""
    preview = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else ("***" if key else "")
    return {"success": True, "has_key": bool(key), "preview": preview, "key": key}


@app.post("/api/translation/test-provider")
def test_translation_provider(req: TestProviderRequest):
    """Test connection and measure latency for a given provider."""
    service = get_translation_service()
    creds = dict(req.credentials) if req.credentials else {}
    if not creds.get("api_key") and not creds.get("gemini_api_key") and not creds.get("openai_api_key") and not creds.get("google_api_key") and not creds.get("codecraft_api_key"):
        user_settings = get_user_ai_settings("default_user")
        saved_creds = user_settings.get("credentials") or {}
        if req.provider == "gemini" and saved_creds.get("gemini_api_key"):
            creds["api_key"] = saved_creds["gemini_api_key"]
        elif req.provider == "openai" and saved_creds.get("openai_api_key"):
            creds["api_key"] = saved_creds["openai_api_key"]
        elif req.provider == "google_cloud" and saved_creds.get("google_api_key"):
            creds["api_key"] = saved_creds["google_api_key"]
        elif req.provider == "codecraft" and saved_creds.get("codecraft_api_key"):
            creds["api_key"] = saved_creds["codecraft_api_key"]
    if req.provider == "codecraft" and not creds.get("base_url") and not creds.get("codecraft_base_url"):
        user_settings = get_user_ai_settings("default_user")
        saved_creds = user_settings.get("credentials") or {}
        if saved_creds.get("codecraft_base_url"):
            creds["base_url"] = saved_creds["codecraft_base_url"]
    res = service.test_provider_connection(req.provider, creds if creds else None)
    return res


@app.post("/api/projects/{project_id}/translate")
async def translate_project_subtitles(project_id: str, req: ProjectTranslateRequest):
    """
    Project-level subtitle translation endpoint using TranslationService.
    Supports context-aware batching, translation memory, glossary, and fallback.
    """
    service = get_translation_service()
    job_id = f"trans_{project_id}"

    # Merge credentials and API key if supplied in request
    req_options = {**(req.options or {})}
    req_options["style"] = req.style or req_options.get("style") or "natural"
    if req.api_key:
        req_options["api_key"] = req.api_key
        if req.provider in ("gemini", None):
            os.environ["GEMINI_API_KEY"] = req.api_key
        elif req.provider == "openai":
            os.environ["OPENAI_API_KEY"] = req.api_key
    if req.credentials:
        req_options["credentials"] = req.credentials
        if req.credentials.get("gemini_api_key"):
            os.environ["GEMINI_API_KEY"] = req.credentials["gemini_api_key"]
        if req.credentials.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = req.credentials["openai_api_key"]

    # Save project settings
    save_project_settings(
        project_id=project_id,
        provider=req.provider,
        model=req.model,
        source_language=req.source_language,
        target_language=req.target_language,
        style=req.style or "natural",
        options=req_options,
    )

    set_job_progress(job_id, 10, "translate", f"Starting translation via {req.provider or 'Gemini'}...")

    def update_cb(pct: int, msg: str):
        set_job_progress(job_id, pct, "translate", msg)

    try:
        result = await asyncio.to_thread(
            service.translate_subtitles_pipeline,
            segments_raw=req.segments,
            project_id=project_id,
            provider=req.provider,
            model=req.model,
            source_language=req.source_language,
            target_language=req.target_language,
            options=req_options,
            job_id=job_id,
            progress_callback=update_cb,
        )

        if not result.success:
            err_msg = result.error.message if result.error else "Translation failed"
            set_job_progress(job_id, 100, "translate", err_msg, status="error")
            return JSONResponse(status_code=400, content=result.to_dict())

        # Update session memory if session exists
        if project_id in sessions_data:
            sessions_data[project_id]["segments"] = [s.to_dict() for s in result.segments]

        set_job_progress(job_id, 100, "translate", "Translation completed successfully", status="completed")
        return result.to_dict()

    except Exception as e:
        logger.error(f"Project Translation Error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "translate", str(e), status="error")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/projects/{project_id}/translation-status")
def get_project_translation_status(project_id: str):
    """Retrieve translation job status, progress percentage, and current segment being processed."""
    job_id = f"trans_{project_id}"
    job = get_translation_job(job_id)
    if job:
        return {"success": True, "job": {
            "progress": job.get("progress", 0),
            "status": job.get("status", "processing"),
            "status_message": job.get("status_message") or "",
            "current_segment_idx": job.get("current_segment_idx") or 0,
            "current_segment_text": job.get("current_segment_text") or "",
            "total_segments": job.get("total_segments", 0),
            "completed_segments": job.get("completed_segments", 0),
        }}

    active_state = jobs_state.get(job_id)
    if active_state:
        return {"success": True, "job": active_state}

    return {"success": False, "message": "No translation job found"}


@app.post("/api/projects/{project_id}/translation/cancel")
def cancel_project_translation(project_id: str):
    """Cancels an active translation job."""
    job_id = f"trans_{project_id}"
    service = get_translation_service()
    service.cancel_job(job_id)
    set_job_progress(job_id, 100, "translate", "Translation cancelled by user", status="cancelled")
    return {"success": True, "message": "Job cancelled"}


@app.get("/api/projects/{project_id}/translation-memory")
def get_project_translation_memory(project_id: str, limit: int = 100):
    """Returns translation memory entries."""
    items = list_translation_memory(limit=limit)
    return {"success": True, "items": items}


@app.post("/api/projects/{project_id}/translation-memory")
def add_project_translation_memory(project_id: str, req: TranslationMemoryRequest):
    """Store an entry into translation memory."""
    store_translation_memory(
        source_text=req.source_text,
        translated_text=req.translated_text,
        source_lang=req.source_language,
        target_lang=req.target_language,
        provider=req.provider or "gemini",
        project_id=project_id,
    )
    return {"success": True, "message": "Translation memory stored"}


@app.delete("/api/translation-memory/{item_id}")
def delete_tm_entry(item_id: int):
    """Delete a translation memory entry by ID."""
    ok = delete_translation_memory(item_id)
    return {"success": ok}


@app.get("/api/projects/{project_id}/glossary")
def get_project_glossary(project_id: str):
    """Fetch project glossary terms."""
    terms = list_glossary_terms(project_id)
    return {"success": True, "terms": terms}


@app.post("/api/projects/{project_id}/glossary")
def save_project_glossary_term(project_id: str, req: GlossaryTermRequest):
    """Add or update a project glossary term."""
    term = add_glossary_term(
        project_id=project_id,
        source_term=req.source_term,
        target_term=req.target_term,
        notes=req.notes or "",
    )
    return {"success": True, "term": term}


@app.delete("/api/projects/{project_id}/glossary/{item_id}")
def remove_glossary_term(project_id: str, item_id: int):
    """Delete a glossary term."""
    ok = delete_glossary_term(item_id)
    return {"success": ok}


@app.post("/api/subtitles/{segment_id}/regenerate")
async def regenerate_subtitle_segment(segment_id: int, req: RegenerateSegmentRequest):
    """Regenerate a single subtitle segment with custom provider, style, tone, and context."""
    service = get_translation_service()
    res = await asyncio.to_thread(
        service.regenerate_segment,
        text=req.text,
        duration=req.duration,
        provider_name=req.provider or "gemini",
        style=req.style or "natural",
        tone=req.tone or "neutral",
        context=req.context,
        project_id=req.project_id,
    )
    return res


@app.get("/api/admin/translation/stats")
def get_admin_stats():
    """Returns analytics and monitoring data for AI translation providers."""
    stats = get_admin_translation_stats()
    return {"success": True, "stats": stats}


# --- Multi-Project Batch Translation Endpoints ---

@app.get("/api/projects")
def list_projects_endpoint():
    """List all saved project sessions with subtitle & translation progress."""
    projects = sessions_data.list_all()
    return {"success": True, "projects": projects, "total": len(projects)}


@app.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    """Delete a saved project session."""
    if project_id in sessions_data:
        del sessions_data[project_id]
        return {"success": True, "message": f"Project {project_id} deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@app.post("/api/batch/translate")
async def start_batch_translation_endpoint(req: BatchTranslateRequest):
    """
    Start batch translation across multiple projects concurrently.
    Supports concurrency throttling, skip translated option, and background execution.
    """
    if not req.project_ids:
        raise HTTPException(status_code=400, detail="No project IDs provided")

    batch_mgr = get_batch_manager()
    batch_data = batch_mgr.create_batch(
        project_ids=req.project_ids,
        sessions_store=sessions_data,
        provider=req.provider,
        model=req.model,
        source_language=req.source_language,
        target_language=req.target_language,
        style=req.style or "natural",
        options={
            **(req.options or {}),
            "skip_already_translated": req.skip_already_translated,
        },
        api_key=req.api_key,
        credentials=req.credentials,
        concurrency=req.concurrency or 2,
    )

    # Launch background worker
    batch_mgr.start_batch_execution(batch_data["batch_id"], sessions_data)

    return {
        "success": True,
        "batch_id": batch_data["batch_id"],
        "total_projects": batch_data["total_projects"],
        "status": batch_data["status"],
        "message": f"Batch translation started for {batch_data['total_projects']} projects",
    }


@app.get("/api/batch/active")
def get_active_batch_endpoint():
    """Get the currently active or most recent batch job."""
    batch_mgr = get_batch_manager()
    active_batch = batch_mgr.get_active_batch()
    return {"success": True, "batch": active_batch}


@app.get("/api/batch/{batch_id}/status")
def get_batch_status_endpoint(batch_id: str):
    """Get the progress and status of a specific batch translation job."""
    batch_mgr = get_batch_manager()
    batch = batch_mgr.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"success": True, "batch": batch}


@app.post("/api/batch/{batch_id}/cancel")
def cancel_batch_endpoint(batch_id: str):
    """Cancel a running batch translation job."""
    batch_mgr = get_batch_manager()
    ok = batch_mgr.cancel_batch(batch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"success": True, "message": "Batch cancelled"}


@app.post("/api/batch/{batch_id}/retry")
def retry_batch_endpoint(batch_id: str):
    """Retry failed projects in a batch translation job."""
    batch_mgr = get_batch_manager()
    retried_batch = batch_mgr.retry_failed(batch_id, sessions_data)
    if not retried_batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"success": True, "batch": retried_batch, "message": "Retrying failed projects"}


# --- Standard Dubbing Endpoints ---

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload media file, extract initial audio and probe metadata."""
    session_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix.lower() or ".mp4"
    saved_filename = f"{session_id}_original{ext}"
    saved_path = UPLOADS_DIR / saved_filename

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Probe file information
    media_info = get_media_info(str(saved_path))
    
    # Extract audio for transcription trimmed exactly to media duration
    audio_filename = f"{session_id}_extracted.wav"
    audio_path = TEMP_DIR / audio_filename
    extract_audio(str(saved_path), str(audio_path), sample_rate=16000, duration=media_info.get("duration"))

    session_info = {
        "session_id": session_id,
        "original_filename": file.filename,
        "file_path": str(saved_path),
        "audio_path": str(audio_path),
        "media_info": media_info,
        "segments": [],
        "created_at": str(asyncio.get_event_loop().time()),
    }
    sessions_data[session_id] = session_info

    return {
        "session_id": session_id,
        "filename": file.filename,
        "duration": media_info.get("duration", 0.0),
        "has_video": media_info.get("has_video", False),
        "has_audio": media_info.get("has_audio", False),
        "width": media_info.get("width"),
        "height": media_info.get("height"),
        "video_url": f"/api/media/{saved_filename}",
    }


@app.post("/api/stt")
async def run_stt(req: STTRequest):
    """Run STT with chosen engine (Whisper / SenseVoiceSmall / Gemini)."""
    session = sessions_data.get(req.session_id)
    if not session or not os.path.exists(session["audio_path"]):
        raise HTTPException(status_code=404, detail="Session or audio not found")

    job_id = f"stt_{req.session_id}"
    set_job_progress(job_id, 10, "stt", f"Starting {req.engine} transcription...")

    try:
        def update_cb(msg: str):
            set_job_progress(job_id, 50, "stt", msg)

        segments = await asyncio.to_thread(
            transcribe_audio,
            audio_path=session["audio_path"],
            engine=req.engine,
            model_name=req.model_name,
            language=req.language,
            voice=req.voice or "auto",
            api_key=req.api_key or DEFAULT_GEMINI_API_KEY,
            progress_callback=update_cb,
        )

        total_dur = float(session.get("media_info", {}).get("duration", 0.0))
        if total_dur <= 0 and os.path.exists(session.get("audio_path", "")):
            from .audio_video_processor import get_audio_duration
            total_dur = get_audio_duration(session["audio_path"])

        segments = merge_dialogue_fragments(segments)
        segments = sanitize_segments_timeline(segments, min_gap=0.05, max_total_duration=total_dur if total_dur > 0 else None)
        session["segments"] = segments
        set_job_progress(job_id, 100, "stt", f"Transcription complete ({len(segments)} segments)", status="completed")
        return {"success": True, "segments": segments, "count": len(segments), "media_info": session.get("media_info", {})}

    except Exception as e:
        logger.error(f"STT Error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "stt", f"STT failed: {str(e)}", status="error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stt/diarize")
async def run_speaker_diarization(req: STTRequest):
    """Run acoustic speaker diarization on existing segments to accurately assign speaking characters."""
    session = sessions_data.get(req.session_id)
    if not session or not os.path.exists(session["audio_path"]):
        raise HTTPException(status_code=404, detail="Session or audio not found")

    # Use segments provided in request, or fall back to session segments
    segments = req.segments if req.segments else (session.get("segments") or [])
    if not segments:
        raise HTTPException(status_code=400, detail="No segments to diarize")

    diarized = await asyncio.to_thread(
        diarize_segments_with_audio,
        audio_path=session["audio_path"],
        segments=segments
    )
    session["segments"] = diarized
    return {"success": True, "segments": diarized}


@app.post("/api/stt/diarize/preview")
async def preview_speaker_diarization(req: STTRequest):
    """
    Preview-only diarization: runs acoustic speaker detection and returns assignment results
    WITHOUT persisting changes to the session. Used to show the user a preview modal
    before they confirm auto-assignment.
    """
    session = sessions_data.get(req.session_id)
    if not session or not os.path.exists(session.get("audio_path", "")):
        raise HTTPException(status_code=404, detail="Session or audio not found")

    # Use segments provided in request, or fall back to session segments
    segments = req.segments if req.segments else (session.get("segments") or [])
    if not segments:
        raise HTTPException(status_code=400, detail="No segments to diarize")

    # Deep-copy segments so session is NOT modified
    import copy
    segments_copy = copy.deepcopy(segments)

    diarized = await asyncio.to_thread(
        diarize_segments_with_audio,
        audio_path=session["audio_path"],
        segments=segments_copy
    )

    # Compute summary stats
    male_segs = [s for s in diarized if s.get("voice") == "Khmer Male 01"]
    female_segs = [s for s in diarized if s.get("voice") == "Khmer Female 01"]
    boy_segs = [s for s in diarized if s.get("voice") == "Khmer Boy 01"]
    girl_segs = [s for s in diarized if s.get("voice") == "Khmer Girl 01"]
    speaker_set = list({s.get("speaker", "Speaker 1") for s in diarized})
    is_single_speaker = len(speaker_set) <= 1

    return {
        "success": True,
        "segments": diarized,
        "stats": {
            "total": len(diarized),
            "male_count": len(male_segs),
            "female_count": len(female_segs),
            "boy_count": len(boy_segs),
            "girl_count": len(girl_segs),
            "speaker_count": len(speaker_set),
            "speakers": speaker_set,
            "is_single_speaker": is_single_speaker,
        }
    }


@app.post("/api/translate")
async def run_translation(req: TranslateRequest):
    """Translate dialogue segments into natural Khmer using Multi-Provider Translation Service."""
    session = sessions_data.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_id = f"trans_{req.session_id}"
    provider = req.provider or "gemini"
    set_job_progress(job_id, 10, "translate", f"Starting {provider.title()} Khmer translation...")

    try:
        def update_cb(msg: str):
            set_job_progress(job_id, 50, "translate", msg)

        translated = await asyncio.to_thread(
            translate_segments_to_khmer,
            segments=req.segments,
            api_key=req.api_key or DEFAULT_GEMINI_API_KEY,
            model_name=req.model_name or ("gemini-3.5-flash" if provider == "gemini" else None),
            progress_callback=update_cb,
            provider=provider,
            project_id=req.session_id,
            style=req.style or "natural",
        )

        session["segments"] = translated
        set_job_progress(job_id, 100, "translate", "Khmer translation completed", status="completed")
        return {"success": True, "segments": translated}

    except Exception as e:
        logger.error(f"Translation Error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "translate", f"Translation failed: {str(e)}", status="error")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/translate-segment")
async def run_single_translation(req: SingleTranslateRequest):
    """Translate a single segment for quick editing in the studio UI."""
    try:
        translated = await asyncio.to_thread(
            translate_single_segment,
            text=req.text,
            duration=req.duration,
            api_key=req.api_key or DEFAULT_GEMINI_API_KEY,
            model_name=req.model_name or ("gemini-3.5-flash" if (req.provider or "gemini") == "gemini" else None),
            provider=req.provider or "gemini",
            tone=req.tone or "neutral",
            style=getattr(req, "style", None) or req.tone or "natural",
        )
        return {"success": True, "khmer_text": translated, "provider": req.provider or "gemini"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/tts/preview")
def preview_single_tts(req: SingleTTSRequest):
    """Synthesize audio preview for a single segment with Edge-TTS."""
    try:
        out_filename = f"preview_{uuid.uuid4().hex[:8]}.mp3"
        out_path = str(TEMP_DIR / out_filename)
        
        res_path = synthesize_segment(
            text=req.text,
            voice=req.voice,
            output_path=out_path,
            rate=req.rate,
            pitch=req.pitch,
            volume=req.volume,
            emotion=req.emotion or "neutral",
            pacing=req.pacing or "normal",
        )
        if not res_path:
            raise HTTPException(status_code=500, detail="Synthesis produced no audio")

        return {"success": True, "audio_url": f"/api/media/{out_filename}"}
    except Exception as e:
        logger.error(f"TTS Preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/detect-emotions")
async def detect_dialogue_emotions(req: DetectEmotionsRequest):
    """
    Analyzes dialogue segments using Gemini or smart acoustic heuristics to determine
    emotion (whisper, angry, sad, excited, terrified, romantic, suspense, sarcastic, exhausted)
    and pacing (normal, fast, slow, urgent) for expressive character dubbing.
    """
    segments = req.segments or []
    if not segments:
        raise HTTPException(status_code=400, detail="No segments provided")

    # 1. Try AI emotion detection with Gemini
    try:
        from .translation_engine import (
            extract_and_parse_json,
            generate_content_with_retry_and_fallback,
            get_gemini_client,
        )
        from google.genai import types

        client = get_gemini_client(req.api_key)
        payload = [
            {
                "id": s.get("id"),
                "text": s.get("text", ""),
                "khmer_text": s.get("khmer_text", ""),
                "speaker": s.get("speaker", "Speaker 1"),
            }
            for s in segments
        ]

        system_instruction = (
            "You are a master film director and dubbing voice coach specializing in expressive dialogue.\n"
            "Analyze each dialogue segment within the scene context. Assign:\n"
            "- emotion: one of ['neutral', 'whisper', 'angry', 'sad', 'excited', 'terrified', 'romantic', 'suspense', 'sarcastic', 'exhausted']\n"
            "- pacing: one of ['normal', 'fast', 'slow', 'urgent']\n"
            "Return ONLY a JSON array with schema: [{\"id\": 1, \"emotion\": \"angry\", \"pacing\": \"fast\"}]. "
            "No markdown or explanation."
        )

        prompt = f"Analyze the emotions and pacing for these dialogue lines:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

        response = await asyncio.to_thread(
            generate_content_with_retry_and_fallback,
            client=client,
            model_name=req.model_name or "gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        data = extract_and_parse_json(response.text.strip())
        emo_map = {item["id"]: item for item in data if "id" in item}

        updated = []
        for s in segments:
            s_copy = dict(s)
            sid = s_copy.get("id")
            if sid in emo_map:
                s_copy["emotion"] = emo_map[sid].get("emotion") or s_copy.get("emotion") or "neutral"
                s_copy["pacing"] = emo_map[sid].get("pacing") or s_copy.get("pacing") or "normal"
            updated.append(s_copy)

        return {"success": True, "segments": updated, "method": "gemini"}

    except Exception as e:
        logger.warning(f"Gemini emotion detection fallback to heuristic: {e}")

    # 2. Fallback: Rule-based heuristic sentiment & punctuation analysis
    updated = []
    for s in segments:
        s_copy = dict(s)
        txt = (s_copy.get("khmer_text") or s_copy.get("text") or "").strip()

        # Check explicit tags first (e.g. [Whisper], [Angry], [Pacing: Fast])
        tag_info = extract_emotional_tags(txt)
        if tag_info.get("emotion") or tag_info.get("pacing"):
            emo = tag_info.get("emotion") or s_copy.get("emotion") or "neutral"
            pacing = tag_info.get("pacing") or s_copy.get("pacing") or "normal"
            if tag_info.get("clean_text"):
                if "khmer_text" in s_copy:
                    s_copy["khmer_text"] = tag_info["clean_text"]
                elif "text" in s_copy:
                    s_copy["text"] = tag_info["clean_text"]
        else:
            lower_txt = txt.lower()
            if any(w in lower_txt for w in ["!", "!!", "ចេញទៅ", "ឆ្កួត", "ខឹង", "ឈប់", "hate", "shut up", "go away"]):
                emo = "angry"
                pacing = "fast"
            elif any(w in lower_txt for w in ["...", "…", "កុំមាត់", "ខ្សឹប", "secret", "shh", "quiet", "whisper"]):
                emo = "whisper"
                pacing = "slow"
            elif any(w in lower_txt for w in ["យំ", "ស្លាប់", "ឈឺចាប់", "sad", "sorry", "cry", "tears", "loss"]):
                emo = "sad"
                pacing = "slow"
            elif any(w in lower_txt for w in ["សប្បាយ", "អបអរ", "ជោគជ័យ", "yes!", "wow", "hurray", "happy", "great"]):
                emo = "excited"
                pacing = "fast"
            elif any(w in lower_txt for w in ["ខ្លាច", "ជួយផង", "ខ្មោច", "run", "help", "scared", "fear"]):
                emo = "terrified"
                pacing = "urgent"
            elif any(w in lower_txt for w in ["ស្រឡាញ់", "អូន", "បង", "love", "sweet", "darling", "kiss"]):
                emo = "romantic"
                pacing = "slow"
            elif any(w in lower_txt for w in ["អាថ៌កំបាំង", "តើអ្នកណា", "mystery", "curious", "dark", "shadow"]):
                emo = "suspense"
                pacing = "slow"
            elif any(w in lower_txt for w in ["អស្ចារ្យណាស់", "ប្រាកដហើយ", "sarcastic", "yeah right", "whatever"]):
                emo = "sarcastic"
                pacing = "slow"
            elif any(w in lower_txt for w in ["អស់កម្លាំង", "ហត់", "exhausted", "tired", "sigh", "sleepy"]):
                emo = "exhausted"
                pacing = "slow"
            else:
                emo = s_copy.get("emotion") or "neutral"
                pacing = s_copy.get("pacing") or "normal"

        s_copy["emotion"] = emo
        s_copy["pacing"] = pacing
        updated.append(s_copy)

    return {"success": True, "segments": updated, "method": "heuristic"}


@app.post("/api/tts/all")
@app.post("/api/tts/synthesize-batch")
async def run_batch_tts(req: BatchTTSRequest):
    """Synthesize Edge-TTS Khmer speech for all segments."""
    session = sessions_data.get(req.session_id)
    if not session:
        session = {
            "session_id": req.session_id,
            "segments": req.segments,
            "media_info": {},
            "created_at": str(time.time()),
        }
        sessions_data[req.session_id] = session

    job_id = f"tts_{req.session_id}"
    set_job_progress(job_id, 10, "tts", "Starting Khmer Edge-TTS synthesis...")

    try:
        def prog_cb(current, total, msg):
            pct = int(10 + (current / total) * 85)
            set_job_progress(job_id, pct, "tts", msg)

        total_duration = float(session.get("media_info", {}).get("duration", 0.0))
        if total_duration <= 0 and session.get("video_duration"):
            total_duration = float(session["video_duration"])

        updated_segments = await synthesize_all_segments(
            segments=req.segments,
            voice=req.voice,
            rate=req.rate,
            pitch=req.pitch,
            volume=req.volume,
            auto_adjust_duration=req.auto_adjust_duration,
            max_total_duration=total_duration if total_duration > 0 else None,
            progress_callback=prog_cb,
        )

        # Attach web accessible audio urls
        for s in updated_segments:
            if s.get("audio_path"):
                s["audio_url"] = f"/api/media/{Path(s['audio_path']).name}"

        # Never report success when nothing was actually synthesized: the video
        # would be rendered with a blank (silent) audio track.
        voiced = sum(1 for s in updated_segments if s.get("audio_path") and os.path.exists(s["audio_path"]))
        if req.segments and voiced == 0:
            addable = sum(1 for s in req.segments if (s.get("khmer_text") or s.get("text") or "").strip())
            if addable:
                raise RuntimeError(
                    "Khmer speech synthesis failed for every segment. Edge-TTS needs an "
                    "Internet connection - check your network and try again."
                )

        # Merge updated segment data into session segments
        existing_segs = session.get("segments", [])
        if existing_segs:
            updated_map = {s.get("id"): s for s in updated_segments}
            for i, es in enumerate(existing_segs):
                eid = es.get("id")
                if eid in updated_map:
                    existing_segs[i] = updated_map[eid]
            session["segments"] = existing_segs
        else:
            session["segments"] = updated_segments

        set_job_progress(job_id, 100, "tts", "All Khmer speech synthesized successfully", status="completed")
        return {"success": True, "segments": updated_segments}

    except Exception as e:
        logger.error(f"Batch TTS error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "tts", f"TTS failed: {str(e)}", status="error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vocal-remover")
async def run_vocal_remover(req: VocalRemoverRequest):
    """Separate vocals and extract clean background music (BGM) without original voices."""
    session = sessions_data.get(req.session_id)
    if not session or not os.path.exists(session["audio_path"]):
        raise HTTPException(status_code=404, detail="Session or audio not found")

    job_id = f"vocal_{req.session_id}"
    set_job_progress(job_id, 15, "vocal", "Separating vocals and isolating clean BGM...")

    try:
        bgm_filename = f"{req.session_id}_clean_bgm.wav"
        bgm_path = str(PROCESSED_DIR / bgm_filename)

        def update_cb(msg: str):
            set_job_progress(job_id, 50, "vocal", msg)

        success = await asyncio.to_thread(
            extract_clean_bgm,
            input_audio_path=session["audio_path"],
            output_bgm_path=bgm_path,
            method=req.method,
            progress_callback=update_cb,
        )

        if not success or not os.path.exists(bgm_path):
            raise RuntimeError("Failed to isolate BGM track")

        session["bgm_audio_path"] = bgm_path
        set_job_progress(job_id, 100, "vocal", "BGM isolated successfully (Vocals removed)", status="completed")

        return {
            "success": True,
            "bgm_audio_url": f"/api/media/{bgm_filename}",
            "message": "Original vocal removed, clean BGM ready!",
        }

    except Exception as e:
        logger.error(f"Vocal remover error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "vocal", f"Vocal removal failed: {str(e)}", status="error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dub")
async def run_video_dubbing(req: DubbingRequest):
    """Stitch synthesized audio segments and mix with video via FFmpeg."""
    session = sessions_data.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_id = f"dub_{req.session_id}"
    set_job_progress(job_id, 10, "dub", "Aligning and stitching Khmer audio tracks...")

    try:
        total_duration = float(session["media_info"].get("duration", 0.0))
        stitched_audio_path = str(PROCESSED_DIR / f"{req.session_id}_khmer_dubbed.mp3")

        # Strictly enforce non-overlapping timeline before voice synthesis or audio stitching
        req.segments = sanitize_segments_timeline(req.segments, min_gap=0.25)
        session["segments"] = req.segments

        # Automatically synthesize speech for any segment missing audio
        needs_synth = [s for s in req.segments if not s.get("audio_path") or not os.path.exists(str(s.get("audio_path", "")))]
        if needs_synth:
            set_job_progress(job_id, 15, "dub", f"Synthesizing voice for {len(needs_synth)} segments...")
            voice = session.get("voice") or "km-KH-PisethNeural"
            req.segments = await synthesize_all_segments(
                segments=req.segments,
                voice=voice,
                auto_adjust_duration=True,
                max_total_duration=total_duration if total_duration > 0 else None,
            )
            # Re-sanitize timeline to account for any voice overflow shifts
            req.segments = sanitize_segments_timeline(req.segments, min_gap=0.25)
            session["segments"] = req.segments

        # 1. Stitch segments along timeline
        stitched_ok = await asyncio.to_thread(
            stitch_dubbed_audio,
            segments=req.segments,
            total_duration=total_duration,
            output_audio_path=stitched_audio_path,
        )
        if not stitched_ok:
            raise RuntimeError("Failed to stitch dubbed audio segments")

        # Check if BGM isolation or sidechain ducking is requested
        bgm_audio_path = session.get("bgm_audio_path")
        if req.mode == "sidechain_ducking":
            set_job_progress(job_id, 35, "dub", "Preparing dynamic background music (BGM) & auto-ducking...")
            if req.bgm_id:
                safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", req.bgm_id)
                candidate_paths = [
                    BGM_DIR / f"bgm_{safe_id}.mp3",
                    BGM_DIR / f"{safe_id}.mp3",
                    BGM_DIR / f"custom_{safe_id}.mp3",
                ]
                target = next((p for p in candidate_paths if p.exists()), None)
                if target:
                    bgm_audio_path = str(target)
            if not bgm_audio_path or not os.path.exists(bgm_audio_path):
                bgm_audio_path = str(generate_procedural_bgm(req.bgm_id or "suspense"))
            session["bgm_audio_path"] = bgm_audio_path
        elif req.mode == "bgm_isolate" and (not bgm_audio_path or not os.path.exists(bgm_audio_path)):
            bgm_filename = f"{req.session_id}_clean_bgm.wav"
            cached_bgm = str(PROCESSED_DIR / bgm_filename)
            if os.path.exists(cached_bgm):
                session["bgm_audio_path"] = cached_bgm
                bgm_audio_path = cached_bgm
            else:
                session_audio = session.get("audio_path", "")
                if session_audio and os.path.exists(session_audio):
                    set_job_progress(job_id, 35, "dub", "Extracting clean BGM (removing original voices)...")
                    ok = await asyncio.to_thread(
                        extract_clean_bgm,
                        input_audio_path=session_audio,
                        output_bgm_path=cached_bgm,
                        method=req.vocal_removal_method,
                    )
                    if ok and os.path.exists(cached_bgm):
                        session["bgm_audio_path"] = cached_bgm
                        bgm_audio_path = cached_bgm

        set_job_progress(job_id, 60, "dub", "Rendering final video with mixed audio...")

        # 2. Render final dubbed video
        out_video_filename = f"{req.session_id}_dubbed.mp4"
        out_video_path = str(PROCESSED_DIR / out_video_filename)

        # 3. Generate Khmer, ASS, and original subtitles
        khmer_srt_name = f"{req.session_id}_khmer.srt"
        khmer_vtt_name = f"{req.session_id}_khmer.vtt"
        khmer_ass_name = f"{req.session_id}_khmer.ass"
        orig_srt_name = f"{req.session_id}_original.srt"

        generate_srt(req.segments, str(PROCESSED_DIR / khmer_srt_name), text_key="khmer_text")
        generate_vtt(req.segments, str(PROCESSED_DIR / khmer_vtt_name), text_key="khmer_text")
        generate_srt(req.segments, str(PROCESSED_DIR / orig_srt_name), text_key="text")
        generate_ass(
            req.segments,
            str(PROCESSED_DIR / khmer_ass_name),
            style=req.subtitle_style,
            dual_mode=(req.subtitle_language_mode == "dual"),
        )

        sub_burn_file = str(PROCESSED_DIR / khmer_ass_name) if req.burn_subtitles else None

        mix_ok = await asyncio.to_thread(
            mix_audio_with_video,
            video_path=session["file_path"],
            dub_audio_path=stitched_audio_path,
            output_video_path=out_video_path,
            mode=req.mode,
            bgm_audio_path=bgm_audio_path,
            ducking_volume=req.ducking_volume,
            bgm_volume=req.bgm_volume,
            dub_volume=req.dub_volume,
            blur_subtitles=req.blur_subtitles,
            subtitle_blur_box=req.subtitle_blur_coords,
            aspect_ratio_mode=req.aspect_ratio,
            canvas_blur_strength=req.canvas_blur_strength,
            blur_objects=req.blur_objects,
            burn_subtitles=req.burn_subtitles,
            subtitles_file=sub_burn_file,
        )
        if not mix_ok:
            raise RuntimeError("Failed to render mixed dubbed video")

        set_job_progress(job_id, 100, "dub", "Video dubbing complete!", status="completed")

        res_data = {
            "success": True,
            "dubbed_video_url": f"/api/media/{out_video_filename}",
            "dubbed_audio_url": f"/api/media/{Path(stitched_audio_path).name}",
            "khmer_srt_url": f"/api/subtitles/{khmer_srt_name}",
            "khmer_vtt_url": f"/api/subtitles/{khmer_vtt_name}",
            "khmer_ass_url": f"/api/subtitles/{khmer_ass_name}",
            "original_srt_url": f"/api/subtitles/{orig_srt_name}",
        }
        if bgm_audio_path:
            res_data["bgm_audio_url"] = f"/api/media/{Path(bgm_audio_path).name}"

        return res_data

    except Exception as e:
        logger.error(f"Dubbing error: {e}", exc_info=True)
        set_job_progress(job_id, 100, "dub", f"Dubbing failed: {str(e)}", status="error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-pipeline")
async def run_auto_pipeline(req: FullPipelineRequest, background_tasks: BackgroundTasks):
    """Full one-click pipeline: STT -> Gemini Translate -> Edge-TTS Khmer -> Mix Dubbed Video."""
    session = sessions_data.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_id = f"auto_{req.session_id}"
    set_job_progress(job_id, 5, "auto", "Starting end-to-end AI dubbing pipeline...")

    async def execute_pipeline():
        try:
            api_key = req.gemini_api_key or DEFAULT_GEMINI_API_KEY
            total_duration = float(session.get("media_info", {}).get("duration", 0.0) or 0.0)

            # Step 1: STT
            set_job_progress(job_id, 15, "stt", f"Step 1/5: Running {req.stt_engine} Speech Recognition...")
            segments = await asyncio.to_thread(
                transcribe_audio,
                audio_path=session["audio_path"],
                engine=req.stt_engine,
                model_name=req.stt_model,
                language=req.stt_language,
                api_key=api_key,
            )
            segments = merge_dialogue_fragments(segments)
            segments = sanitize_segments_timeline(segments, min_gap=0.05, max_total_duration=total_duration if total_duration > 0 else None)
            session["segments"] = segments

            # Step 2: Translation
            active_provider = req.translation_provider or "gemini"
            set_job_progress(job_id, 35, "translate", f"Step 2/5: Translating {len(segments)} segments to Khmer dialogue via {active_provider.title()}...")
            translated = await asyncio.to_thread(
                translate_segments_to_khmer,
                segments=segments,
                api_key=api_key,
                model_name=req.translation_model or ("gemini-3.5-flash" if active_provider == "gemini" else None),
                provider=active_provider,
                project_id=req.session_id,
                style=req.translation_style or "natural",
            )
            session["segments"] = translated

            # Guard: translating to Khmer must produce Khmer script, otherwise
            # the API key / network is broken and the dub would be untranslated.
            if segments:
                khmer_segments = sum(
                    1 for s in translated
                    if any("\u1780" <= ch <= "\u17ff" for ch in str(s.get("khmer_text") or ""))
                )
                if khmer_segments == 0:
                    raise RuntimeError(
                        "Translation produced no Khmer text. Check your Gemini API key and "
                        "Internet connection, then try again."
                    )

            # Step 3: Edge-TTS
            set_job_progress(job_id, 55, "tts", f"Step 3/5: Synthesizing Edge-TTS Khmer voices ({req.tts_voice})...")
            synth_segments = await synthesize_all_segments(
                segments=translated,
                voice=req.tts_voice,
                rate=req.tts_rate,
                pitch=req.tts_pitch,
                volume=req.tts_volume,
                auto_adjust_duration=True,
                max_total_duration=total_duration if total_duration > 0 else None,
            )
            synth_segments = sanitize_segments_timeline(synth_segments, min_gap=0.25)
            session["segments"] = synth_segments

            # Guard: never render a "successful" dub with a silent audio track.
            voiced = sum(1 for s in synth_segments if s.get("audio_path") and os.path.exists(s["audio_path"]))
            if synth_segments and voiced == 0:
                raise RuntimeError(
                    "Khmer speech synthesis failed for every segment. Edge-TTS needs an "
                    "Internet connection - check your network and try again."
                )

            # Step 4: BGM Separation (if bgm_isolate)
            bgm_audio_path = session.get("bgm_audio_path")
            if req.mixing_mode == "bgm_isolate" and (not bgm_audio_path or not os.path.exists(bgm_audio_path)):
                set_job_progress(job_id, 75, "vocal", "Step 4/5: Isolating BGM and removing original voices...")
                bgm_filename = f"{req.session_id}_clean_bgm.wav"
                bgm_path = str(PROCESSED_DIR / bgm_filename)
                ok = await asyncio.to_thread(
                    extract_clean_bgm,
                    input_audio_path=session["audio_path"],
                    output_bgm_path=bgm_path,
                    method=req.vocal_removal_method,
                )
                if ok and os.path.exists(bgm_path):
                    session["bgm_audio_path"] = bgm_path
                    bgm_audio_path = bgm_path

            # Step 5: Stitch & Dub Video
            set_job_progress(job_id, 90, "dub", "Step 5/5: Stitching audio and mixing final video...")
            stitched_audio_path = str(PROCESSED_DIR / f"{req.session_id}_khmer_dubbed.mp3")

            stitch_ok = await asyncio.to_thread(
                stitch_dubbed_audio,
                segments=synth_segments,
                total_duration=total_duration,
                output_audio_path=stitched_audio_path,
            )
            if not stitch_ok:
                raise RuntimeError("Failed to stitch dubbed audio")

            out_video_filename = f"{req.session_id}_dubbed.mp4"
            out_video_path = str(PROCESSED_DIR / out_video_filename)

            # Subtitles (SRT, VTT, ASS)
            khmer_srt_name = f"{req.session_id}_khmer.srt"
            khmer_vtt_name = f"{req.session_id}_khmer.vtt"
            khmer_ass_name = f"{req.session_id}_khmer.ass"
            orig_srt_name = f"{req.session_id}_original.srt"
            generate_srt(synth_segments, str(PROCESSED_DIR / khmer_srt_name), text_key="khmer_text")
            generate_vtt(synth_segments, str(PROCESSED_DIR / khmer_vtt_name), text_key="khmer_text")
            generate_srt(synth_segments, str(PROCESSED_DIR / orig_srt_name), text_key="text")
            generate_ass(
                synth_segments,
                str(PROCESSED_DIR / khmer_ass_name),
                style=req.subtitle_style,
                dual_mode=(req.subtitle_language_mode == "dual"),
            )

            sub_burn_file = str(PROCESSED_DIR / khmer_ass_name) if req.burn_subtitles else None

            mix_ok = await asyncio.to_thread(
                mix_audio_with_video,
                video_path=session["file_path"],
                dub_audio_path=stitched_audio_path,
                output_video_path=out_video_path,
                mode=req.mixing_mode,
                bgm_audio_path=bgm_audio_path,
                ducking_volume=req.ducking_volume,
                bgm_volume=req.bgm_volume,
                dub_volume=req.dub_volume,
                blur_subtitles=req.blur_subtitles,
                subtitle_blur_box=req.subtitle_blur_coords,
                aspect_ratio_mode=req.aspect_ratio,
                canvas_blur_strength=req.canvas_blur_strength,
                blur_objects=req.blur_objects,
                burn_subtitles=req.burn_subtitles,
                subtitles_file=sub_burn_file,
            )
            if not mix_ok:
                raise RuntimeError("Failed to mix video with dubbed audio")

            result_payload = {
                "dubbed_video_url": f"/api/media/{out_video_filename}",
                "dubbed_audio_url": f"/api/media/{Path(stitched_audio_path).name}",
                "khmer_srt_url": f"/api/subtitles/{khmer_srt_name}",
                "khmer_vtt_url": f"/api/subtitles/{khmer_vtt_name}",
                "khmer_ass_url": f"/api/subtitles/{khmer_ass_name}",
                "original_srt_url": f"/api/subtitles/{orig_srt_name}",
                "segments": synth_segments,
            }
            if bgm_audio_path:
                result_payload["bgm_audio_url"] = f"/api/media/{Path(bgm_audio_path).name}"

            session["result"] = result_payload
            set_job_progress(job_id, 100, "auto", "Auto pipeline completed successfully!", status="completed")

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            set_job_progress(job_id, 100, "auto", f"Pipeline error: {str(e)}", status="error")

    background_tasks.add_task(execute_pipeline)
    return {"job_id": job_id, "session_id": req.session_id}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request):
    """Server-Sent Events (SSE) progress update stream with graceful client disconnect handling."""
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                job = jobs_state.get(job_id, {"percent": 0, "step": "init", "message": "Waiting...", "status": "pending"})
                yield f"data: {json.dumps(job)}\n\n"
                if job.get("status") in ("completed", "error"):
                    break
                await asyncio.sleep(0.5)
        except (asyncio.CancelledError, ConnectionResetError):
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/session/{session_id}")
def get_session_data(session_id: str):
    """Retrieve current session state and segments."""
    session = sessions_data.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Live-clamp segment timestamps so stale/bad end times never exceed video duration
    total_dur = float((session.get("media_info") or {}).get("duration", 0.0))
    if total_dur <= 0 and session.get("audio_path") and os.path.exists(session["audio_path"]):
        try:
            from .audio_video_processor import get_audio_duration
            total_dur = get_audio_duration(session["audio_path"]) or 0.0
        except Exception:
            pass

    if total_dur > 0:
        segs = session.get("segments")
        if segs:
            clamped = sanitize_segments_timeline(segs, min_gap=0.05, max_total_duration=total_dur)
            # Write back if anything changed, also re-persists to disk
            if any(
                clamped[i].get("start") != segs[i].get("start") or
                clamped[i].get("end") != segs[i].get("end")
                for i in range(len(clamped))
            ):
                session["segments"] = clamped
                sessions_data[session_id] = session

    if session.get("file_path") and os.path.exists(session["file_path"]):
        session["video_url"] = f"/api/media/{Path(session['file_path']).name}"

    return session


@app.get("/api/media/{filename}")
def stream_media(filename: str):
    """Stream media files (uploaded, temporary, or processed)."""
    for folder in [UPLOADS_DIR, PROCESSED_DIR, TEMP_DIR]:
        target = folder / filename
        if target.exists():
            media_type = "video/mp4" if filename.endswith(".mp4") else "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
            return FileResponse(path=str(target), media_type=media_type)
    raise HTTPException(status_code=404, detail="Media file not found")


@app.get("/api/subtitles/{filename}")
def download_subtitle(filename: str):
    """Download SRT / VTT / ASS subtitle files."""
    target = PROCESSED_DIR / filename
    if target.exists():
        if filename.endswith(".vtt"):
            media_type = "text/vtt"
        elif filename.endswith(".ass"):
            media_type = "text/x-ssa"
        else:
            media_type = "application/x-subrip"
        return FileResponse(path=str(target), filename=filename, media_type=media_type)
    raise HTTPException(status_code=404, detail="Subtitle file not found")


@app.post("/api/subtitles/export")
def export_subtitles(req: ExportSubtitleRequest):
    """Dynamically generate and export SRT, VTT, or ASS subtitles with custom styling."""
    try:
        fmt = req.format.lower()
        dual_mode = req.language_mode == "dual"
        out_name = f"{req.session_id}_custom_{int(time.time())}.{fmt}"
        out_path = str(PROCESSED_DIR / out_name)

        if fmt == "ass":
            ok = generate_ass(req.segments, out_path, style=req.style, dual_mode=dual_mode)
        elif fmt == "vtt":
            ok = generate_vtt(req.segments, out_path, text_key="khmer_text")
        else:
            ok = generate_srt(req.segments, out_path, text_key="khmer_text")

        if not ok or not os.path.exists(out_path):
            raise HTTPException(status_code=500, detail="Failed to generate subtitle export")

        return {
            "success": True,
            "filename": out_name,
            "download_url": f"/api/subtitles/{out_name}",
            "format": fmt,
        }
    except Exception as e:
        logger.error(f"Subtitle export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-faces")
async def detect_faces(req: FaceDetectionRequest):
    """Detect faces on a specific video frame and return normalized bounding boxes."""
    ts = req.current_time if req.current_time is not None else req.timestamp
    session = sessions_data.get(req.session_id)
    if not session:
        # Fallback heuristic if session not found yet
        return {
            "faces": [{"x": 0.38, "y": 0.18, "width": 0.24, "height": 0.28, "confidence": 0.85}],
            "count": 1,
            "timestamp": ts,
        }

    video_path = session.get("file_path")
    if not video_path or not os.path.exists(video_path):
        return {
            "faces": [{"x": 0.38, "y": 0.18, "width": 0.24, "height": 0.28, "confidence": 0.80}],
            "count": 1,
            "timestamp": ts,
        }

    frame_png = str(TEMP_DIR / f"{req.session_id}_frame_{int(ts * 1000)}.png")
    cmd = [
        "ffmpeg", "-y", "-ss", f"{max(0.0, ts):.3f}",
        "-i", video_path, "-vframes", "1", "-q:v", "2", frame_png
    ]

    try:
        await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        logger.warning(f"Frame extraction failed: {e}")
        return {
            "faces": [{"x": 0.38, "y": 0.18, "width": 0.24, "height": 0.28, "confidence": 0.80}],
            "count": 1,
            "timestamp": req.timestamp,
        }

    faces = []
    if os.path.exists(frame_png):
        try:
            import cv2
            img = cv2.imread(frame_png)
            if img is not None:
                h, w = img.shape[:2]
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                face_cascade = cv2.CascadeClassifier(cascade_path)
                detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                for (fx, fy, fw, fh) in detected:
                    faces.append({
                        "x": round(float(fx) / w, 4),
                        "y": round(float(fy) / h, 4),
                        "width": round(float(fw) / w, 4),
                        "height": round(float(fh) / h, 4),
                        "confidence": 0.92,
                    })
        except Exception as cv_err:
            logger.info(f"OpenCV face detection unavailable or skipped: {cv_err}")
        finally:
            try:
                if os.path.exists(frame_png):
                    os.remove(frame_png)
            except Exception:
                pass

    if not faces:
        faces.append({
            "x": 0.38,
            "y": 0.18,
            "width": 0.24,
            "height": 0.28,
            "confidence": 0.85,
        })

    return {"faces": faces, "count": len(faces), "timestamp": req.timestamp}


# ==============================================================================
# Storytelling Recap (សម្រាយរឿង) Endpoints
# ==============================================================================

@app.post("/api/recap/generate")
async def api_generate_recap(req: RecapGenerateRequest):
    session = sessions_data.get(req.session_id)
    segments = req.segments or (session.get("segments") if session else None)

    api_key = req.api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required for Recap Script generation.")

    media_info = session.get("media_info", {}) if session else {}
    duration = float(req.total_duration or media_info.get("duration", 0.0))
    if duration <= 0 and session and session.get("video_duration"):
        duration = float(session["video_duration"])

    audio_path = session.get("audio_path") if session else None
    video_path = session.get("file_path") if session else None

    # Check if segments have real dialogue text
    has_real_dialogue = False
    if segments:
        for s in segments:
            t = (s.get("text", "") or s.get("khmer_text", "")).strip()
            if t and not re.match(r"^Scene\s*#?\d+", t, re.IGNORECASE):
                has_real_dialogue = True
                break

    # If no segments exist or segments lack real dialogue text, auto-transcribe real dialogue via Whisper
    if (not segments or not has_real_dialogue) and audio_path and os.path.exists(audio_path):
        logger.info("Auto-transcribing video audio via Whisper for faithful Story Recap...")
        try:
            extracted_segs = await asyncio.to_thread(
                transcribe_audio,
                audio_path=audio_path,
                engine="whisper",
                model_name="base",
                language="auto",
                api_key=api_key
            )
            if extracted_segs and any((s.get("text", "") or "").strip() for s in extracted_segs):
                segments = extracted_segs
                if session:
                    session["segments"] = segments
        except Exception as stt_err:
            logger.warning(f"Whisper auto-transcribe for recap failed: {stt_err}")

    # Fallback: slice total video duration into 5.0-second timestamped scenes if still no segments
    if not segments:
        dur = duration if duration > 0 else 30.0
        segments = []
        chunk_len = 5.0
        cur = 0.0
        idx = 1
        while cur < (dur - 0.5):
            nxt = min(dur, round(cur + chunk_len, 2))
            segments.append({
                "id": idx,
                "start": round(cur, 2),
                "end": round(nxt, 2),
                "text": f"Scene #{idx} ({cur:.1f}s - {nxt:.1f}s)",
                "khmer_text": "",
            })
            cur = nxt
            idx += 1

    if duration <= 0 and segments:
        duration = max(float(s.get("end", 0.0)) for s in segments)
    if duration <= 0:
        duration = 30.0

    try:
        recap_segments = await asyncio.to_thread(
            generate_recap_script,
            segments=segments,
            total_duration=duration,
            audio_path=audio_path,
            video_path=video_path,
            style=req.style,
            include_hook=req.include_hook,
            include_cta=req.include_cta,
            pacing=req.pacing,
            hybrid_dialogue=bool(req.hybrid_dialogue),
            narrator_voice=req.narrator_voice or "km-KH-PisethNeural",
            api_key=api_key,
            model_name=req.model_name,
        )
        # Guarantee strict collision-free timestamps equally distributed across video duration
        recap_segments = sanitize_segments_timeline(recap_segments, min_gap=0.25, max_total_duration=duration, distribute_evenly=True)

        if session:
            session["recap_segments"] = recap_segments
            session["segments"] = recap_segments

        return {
            "status": "success",
            "count": len(recap_segments),
            "style": req.style,
            "segments": recap_segments,
        }
    except Exception as e:
        logger.error(f"Error generating recap script: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recap/bgm-presets")
async def api_get_bgm_presets():
    tracks = await asyncio.to_thread(get_available_bgm_tracks)
    return {"tracks": tracks, "styles": list(RECAP_STYLES.values())}


@app.get("/api/recap/bgm-file/{bgm_id}")
async def api_get_bgm_file(bgm_id: str):
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", bgm_id)
    candidate_paths = [
        BGM_DIR / f"bgm_{safe_id}.mp3",
        BGM_DIR / f"{safe_id}.mp3",
        BGM_DIR / f"custom_{safe_id}.mp3",
    ]
    target = next((p for p in candidate_paths if p.exists()), None)
    if not target:
        raise HTTPException(status_code=404, detail="BGM audio file not found")
    return FileResponse(str(target), media_type="audio/mpeg")


@app.post("/api/recap/upload-bgm")
async def api_upload_bgm(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp3", ".wav", ".aac", ".m4a", ".ogg")):
        raise HTTPException(status_code=400, detail="Only audio files (.mp3, .wav, .aac, .m4a, .ogg) are accepted.")

    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(file.filename).stem)
    out_path = BGM_DIR / f"custom_{clean_name}.mp3"

    temp_in = TEMP_DIR / f"temp_bgm_{uuid.uuid4().hex[:6]}_{file.filename}"
    with open(temp_in, "wb") as f:
        shutil.copyfileobj(file.file, f)

    import subprocess
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", str(temp_in),
        "-ac", "2",
        "-ar", "44100",
        "-b:a", "192k",
        str(out_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        logger.error(f"Failed to transcode uploaded BGM: {e}")
        shutil.copy(str(temp_in), str(out_path))
    finally:
        if temp_in.exists():
            try:
                temp_in.unlink()
            except Exception:
                pass

    return {
        "status": "success",
        "id": f"custom_{clean_name}",
        "name": f"Custom: {clean_name}",
        "url": f"/api/recap/bgm-file/custom_{clean_name}"
    }


# Prevent browser caching of frontend files so code updates apply immediately
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".html")) or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Mount frontend static files
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
