import asyncio
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import importlib
import edge_tts

# Guard against stale edge-tts v1 protocol cached in long-running processes
try:
    if getattr(getattr(edge_tts, "constants", None), "SEC_MS_GEC_VERSION", "").startswith("1-"):
        import edge_tts.constants
        import edge_tts.drm
        import edge_tts.communicate
        importlib.reload(edge_tts.constants)
        importlib.reload(edge_tts.drm)
        importlib.reload(edge_tts.communicate)
        importlib.reload(edge_tts)
except Exception:
    pass

from .audio_video_processor import get_audio_duration, time_stretch_audio
from .config import FFMPEG_PATH, KHMER_VOICES, TEMP_DIR

logger = logging.getLogger("tts_engine")
logger.setLevel(logging.INFO)


def _clean_edge_param(val: Optional[str], unit: str, default: str) -> str:
    """Normalize Edge-TTS rate/pitch/volume parameter strings to ensure signed prefix."""
    if not val:
        return default
    val_str = str(val).strip()
    if val_str.lower().endswith(unit.lower()):
        val_str = val_str[:-len(unit)].strip()
    val_str = val_str.replace(" ", "")
    if not val_str:
        return default
    try:
        num = int(round(float(val_str)))
        return f"+{num}{unit}" if num >= 0 else f"{num}{unit}"
    except Exception:
        return default


def normalize_rate(rate: Optional[str]) -> str:
    return _clean_edge_param(rate, "%", "+0%")


def normalize_pitch(pitch: Optional[str]) -> str:
    return _clean_edge_param(pitch, "Hz", "+0Hz")


def normalize_volume(volume: Optional[str]) -> str:
    return _clean_edge_param(volume, "%", "+60%")


# Voice parameter specifications including pitch and rate offsets for child voices
VOICE_SPECS = {
    "km-KH-PisethNeural": {"voice": "km-KH-PisethNeural", "pitch_offset": 0, "rate_offset": 0},
    "km-KH-SreymomNeural": {"voice": "km-KH-SreymomNeural", "pitch_offset": 0, "rate_offset": 0},
    "km-KH-PisethNeural-Boy": {"voice": "km-KH-PisethNeural", "pitch_offset": 14, "rate_offset": 6},
    "km-KH-SreymomNeural-Girl": {"voice": "km-KH-SreymomNeural", "pitch_offset": 16, "rate_offset": 6},
    "Khmer Male 01": {"voice": "km-KH-PisethNeural", "pitch_offset": 0, "rate_offset": 0},
    "Khmer Female 01": {"voice": "km-KH-SreymomNeural", "pitch_offset": 0, "rate_offset": 0},
    "Khmer Boy 01": {"voice": "km-KH-PisethNeural", "pitch_offset": 14, "rate_offset": 6},
    "Khmer Girl 01": {"voice": "km-KH-SreymomNeural", "pitch_offset": 16, "rate_offset": 6},
    "Piseth": {"voice": "km-KH-PisethNeural", "pitch_offset": 0, "rate_offset": 0},
    "Sreymom": {"voice": "km-KH-SreymomNeural", "pitch_offset": 0, "rate_offset": 0},
    "PisethBoy": {"voice": "km-KH-PisethNeural", "pitch_offset": 14, "rate_offset": 6},
    "SreymomGirl": {"voice": "km-KH-SreymomNeural", "pitch_offset": 16, "rate_offset": 6},
    "Boy": {"voice": "km-KH-PisethNeural", "pitch_offset": 14, "rate_offset": 6},
    "Girl": {"voice": "km-KH-SreymomNeural", "pitch_offset": 16, "rate_offset": 6},
}


PACING_SPECS = {
    "normal": 0,
    "fast": 10,
    "slow": -8,
    "urgent": 15,
}

# Emotion parameter specifications:
# Calibrated for natural Khmer dialogue performance while strictly preserving 100% original voice timbre,
# clarity, and vocal identity (Piseth & Sreymom).
# Destructive distortion filters are completely eliminated; subtle EQ presence and dynamics are applied
# to sculpt expressive vocal acoustics.
EMOTION_SPECS = {
    "neutral": {
        "pitch_offset": 0,
        "rate_offset": 0,
        "volume_offset": 0,
        "filter": None,
        "label": "Neutral (ធម្មតា)",
        "emoji": "😐",
    },
    "whisper": {
        # Soft and intimate pacing; preserves high-frequency clarity and air so Khmer consonants remain distinct
        "pitch_offset": -1,
        "rate_offset": -4,
        "volume_offset": -6,
        "filter": "equalizer=f=7500:t=q:w=1.5:g=3.0,equalizer=f=220:t=q:w=1.0:g=-3.0",
        "label": "Whisper (ខ្សឹប)",
        "emoji": "🤫",
    },
    "angry": {
        # Firm and energetic delivery with midrange bite and safe headroom
        "pitch_offset": 3,
        "rate_offset": 6,
        "volume_offset": 8,
        "filter": "equalizer=f=2800:t=q:w=1.2:g=3.0,alimiter=limit=0.92:level=true",
        "label": "Angry (ខឹង/ស្រែក)",
        "emoji": "😡",
    },
    "sad": {
        # Somber, emotional downbeat pacing with warm low-mid vocal curve
        "pitch_offset": -2,
        "rate_offset": -6,
        "volume_offset": -5,
        "filter": "equalizer=f=350:t=q:w=1.0:g=2.5,equalizer=f=6000:t=q:w=1.5:g=-2.0",
        "label": "Sad (យំសោក)",
        "emoji": "😭",
    },
    "excited": {
        # Lively, upbeat delivery with crisp vocal clarity
        "pitch_offset": 3,
        "rate_offset": 6,
        "volume_offset": 6,
        "filter": "equalizer=f=4000:t=q:w=1.5:g=3.0,equalizer=f=120:t=q:w=1.0:g=-1.5",
        "label": "Excited (រំភើប)",
        "emoji": "🤩",
    },
    "terrified": {
        # Tense, breathless pacing while keeping natural human voice quality intact
        "pitch_offset": 2,
        "rate_offset": 7,
        "volume_offset": 5,
        "filter": "equalizer=f=3200:t=q:w=1.2:g=2.5",
        "label": "Terrified (ភ័យខ្លាច)",
        "emoji": "😨",
    },
    "romantic": {
        # Warm, gentle, velvety affectionate cadence
        "pitch_offset": -2,
        "rate_offset": -4,
        "volume_offset": -4,
        "filter": "equalizer=f=300:t=q:w=1.0:g=2.0,equalizer=f=4500:t=q:w=1.2:g=1.5",
        "label": "Romantic (ផ្អែមល្ហែម)",
        "emoji": "🥰",
    },
    "suspense": {
        # Deep, hushed atmospheric resonance with deliberate suspenseful delivery
        "pitch_offset": -2,
        "rate_offset": -7,
        "volume_offset": -3,
        "filter": "equalizer=f=250:t=q:w=1.0:g=3.0,equalizer=f=6500:t=q:w=1.2:g=-2.5",
        "label": "Suspense (អាថ៌កំបាំង)",
        "emoji": "🔮",
    },
    "sarcastic": {
        # Wry, ironic inflection with punchy dialogue presence
        "pitch_offset": 1,
        "rate_offset": -2,
        "volume_offset": 2,
        "filter": "equalizer=f=2200:t=q:w=1.5:g=2.5",
        "label": "Sarcastic (បញ្ចើច/ឌឺដង)",
        "emoji": "😏",
    },
    "exhausted": {
        # Fatigued low breath with subdued volume and decelerated tempo
        "pitch_offset": -2,
        "rate_offset": -6,
        "volume_offset": -6,
        "filter": "equalizer=f=200:t=q:w=1.0:g=2.0,equalizer=f=5000:t=q:w=1.5:g=-3.0",
        "label": "Exhausted (ហត់នឿយ)",
        "emoji": "😮‍💨",
    },
}

# Emotion & Pacing tag matching regexes
_EMOTION_TAG_MAP = {
    "whisper": "whisper",
    "ខ្សឹប": "whisper",
    "angry": "angry",
    "shout": "angry",
    "ខឹង": "angry",
    "ស្រែក": "angry",
    "sad": "sad",
    "crying": "sad",
    "យំសោក": "sad",
    "កម្សត់": "sad",
    "excited": "excited",
    "happy": "excited",
    "រំភើប": "excited",
    "សប្បាយ": "excited",
    "terrified": "terrified",
    "fear": "terrified",
    "panic": "terrified",
    "ភ័យខ្លាច": "terrified",
    "ផ្អើល": "terrified",
    "romantic": "romantic",
    "sensual": "romantic",
    "ផ្អែមល្ហែម": "romantic",
    "ស្នេហា": "romantic",
    "suspense": "suspense",
    "mystery": "suspense",
    "អាថ៌កំបាំង": "suspense",
    "sarcastic": "sarcastic",
    "smirk": "sarcastic",
    "បញ្ចើច": "sarcastic",
    "ឌឺដង": "sarcastic",
    "exhausted": "exhausted",
    "tired": "exhausted",
    "ហត់នឿយ": "exhausted",
    "អស់កម្លាំង": "exhausted",
    "neutral": "neutral",
    "ធម្មតា": "neutral",
}

_PACING_TAG_MAP = {
    "fast": "fast",
    "quick": "fast",
    "rapid": "fast",
    "លឿន": "fast",
    "slow": "slow",
    "calm": "slow",
    "យឺត": "slow",
    "urgent": "urgent",
    "បន្ទាន់": "urgent",
    "normal": "normal",
    "ធម្មតា": "normal",
}


class EmotionalTagResult(tuple):
    """
    Tuple containing (clean_text, emotion, pacing, pitch_offset, rate_offset).
    Supports both tuple unpacking:
      clean_text, emo, pacing, p_ovr, r_ovr = extract_emotional_tags(text)
    and dict-like access:
      res["emotion"], res.get("pacing"), res.clean_text, res.volume_offset
    """
    def __new__(
        cls,
        clean_text: str,
        emotion: Optional[str],
        pacing: Optional[str],
        pitch_offset: int = 0,
        rate_offset: int = 0,
        volume_offset: int = 0,
    ):
        instance = super().__new__(cls, (clean_text, emotion, pacing, pitch_offset, rate_offset))
        instance._volume_offset = volume_offset
        return instance

    @property
    def clean_text(self) -> str:
        return self[0]

    @property
    def emotion(self) -> Optional[str]:
        return self[1]

    @property
    def pacing(self) -> Optional[str]:
        return self[2]

    @property
    def pitch_offset(self) -> int:
        return self[3]

    @property
    def rate_offset(self) -> int:
        return self[4]

    @property
    def volume_offset(self) -> int:
        return getattr(self, "_volume_offset", 0)

    def __getitem__(self, key):
        if isinstance(key, str):
            mapping = {
                "clean_text": self[0],
                "emotion": self[1],
                "pacing": self[2],
                "pitch_offset": self[3],
                "pitch_override": self[3],
                "rate_offset": self[4],
                "rate_override": self[4],
                "volume_offset": getattr(self, "_volume_offset", 0),
                "volume_override": getattr(self, "_volume_offset", 0),
            }
            if key in mapping:
                return mapping[key]
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            val = self[key]
            return val if val is not None else default
        except KeyError:
            return default

    def to_dict(self):
        return {
            "clean_text": self[0],
            "emotion": self[1],
            "pacing": self[2],
            "pitch_offset": self[3],
            "rate_offset": self[4],
            "volume_offset": getattr(self, "_volume_offset", 0),
        }


def extract_emotional_tags(text: str) -> EmotionalTagResult:
    """
    Extracts emotional and pacing bracket tags from dialogue text.
    Examples:
      '[Whisper] តើឯងកំពុងធ្វើអ្វីហ្នឹង?' -> ('តើឯងកំពុងធ្វើអ្វីហ្នឹង?', 'whisper', None, 0, 0)
      '[Angry] [Pacing: Fast] ចេញទៅភ្លាម!' -> ('ចេញទៅភ្លាម!', 'angry', 'fast', 0, 0)
      '[Pitch: +3] [Rate: +10%] សួស្តី!' -> ('សួស្តី!', None, None, 3, 10)
    Returns:
      EmotionalTagResult(clean_text, detected_emotion, detected_pacing, pitch_override_offset, rate_override_offset)
    """
    if not text:
        return EmotionalTagResult("", None, None, 0, 0, 0)

    clean_text = text
    detected_emotion: Optional[str] = None
    detected_pacing: Optional[str] = None
    pitch_override = 0
    rate_override = 0
    volume_override = 0

    # 1. Match [Pacing: Fast], [Speed: Slow], [Tempo: ...], [ល្បឿន: ...]
    def _sub_pacing(match):
        nonlocal detected_pacing
        val = match.group(1).strip().lower()
        if val in _PACING_TAG_MAP:
            detected_pacing = _PACING_TAG_MAP[val]
        return ""

    clean_text = re.sub(
        r"\[(?:pacing|speed|tempo|ល្បឿន)\s*:\s*([a-zA-Z\u1780-\u17d2]+)\]",
        _sub_pacing,
        clean_text,
        flags=re.IGNORECASE,
    )

    # 2. Match [Pitch: +2Hz], [Pitch: -3]
    def _sub_pitch(match):
        nonlocal pitch_override
        try:
            pitch_override = int(match.group(1))
        except Exception:
            pass
        return ""

    clean_text = re.sub(
        r"\[(?:pitch|សម្លេង)\s*:\s*([+-]?\d+)(?:hz)?\]",
        _sub_pitch,
        clean_text,
        flags=re.IGNORECASE,
    )

    # 3. Match [Rate: +10%], [Speed: +15%]
    def _sub_rate(match):
        nonlocal rate_override
        try:
            rate_override = int(match.group(1))
        except Exception:
            pass
        return ""

    clean_text = re.sub(
        r"\[(?:rate|speed)\s*:\s*([+-]?\d+)(?:%)?\]",
        _sub_rate,
        clean_text,
        flags=re.IGNORECASE,
    )

    # 4. Match [Volume: +3dB], [Volume: -5%], [កម្រិតសម្លេង: ...]
    def _sub_volume(match):
        nonlocal volume_override
        try:
            volume_override = int(match.group(1))
        except Exception:
            pass
        return ""

    clean_text = re.sub(
        r"\[(?:volume|vol|កម្រិតសម្លេង)\s*:\s*([+-]?\d+)(?:db|%)?\]",
        _sub_volume,
        clean_text,
        flags=re.IGNORECASE,
    )

    # 5. Match general Emotion tags [Whisper], [Angry], [ខ្សឹប], [Fast], etc.
    def _sub_emotion(match):
        nonlocal detected_emotion, detected_pacing
        tag_val = match.group(1).strip().lower()
        if tag_val in _EMOTION_TAG_MAP:
            detected_emotion = _EMOTION_TAG_MAP[tag_val]
        elif tag_val in _PACING_TAG_MAP:
            detected_pacing = _PACING_TAG_MAP[tag_val]
        return ""

    all_keys = "|".join(re.escape(k) for k in list(_EMOTION_TAG_MAP.keys()) + list(_PACING_TAG_MAP.keys()))
    clean_text = re.sub(
        rf"\[(?:emotion\s*:\s*)?({all_keys})\]",
        _sub_emotion,
        clean_text,
        flags=re.IGNORECASE,
    )

    # Clean redundant whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return EmotionalTagResult(clean_text, detected_emotion, detected_pacing, pitch_override, rate_override, volume_override)


def format_speech_text_for_natural_pacing(text: str) -> str:
    """
    Subtly prepares Khmer dialogue text for natural Edge-TTS pacing without breaking Unicode.
    Inserts micro-pausing commas after full stops or ellipsis if missing.
    """
    if not text:
        return ""
    # Strip any remaining unmatched square brackets
    cleaned = re.sub(r"\[[^\]]*\]", "", text).strip()
    return cleaned


def estimate_khmer_syllables(text: str) -> int:
    """
    Estimates Khmer syllable count via Unicode-aware consonant nucleus detection.

    Algorithm: each Khmer consonant (U+1780–U+17A2) that is NOT a subscript
    (i.e., not immediately preceded by COENG U+17D2) is one syllable nucleus.
    Independent vowels (U+17A0–U+17B5) are also syllable-bearing.
    Subscript consonants (coeng-stacked) are part of the preceding syllable.

    Calibrated to Edge-TTS km-KH voices at +0% rate: ~3.0–3.4 syllables/second.
    """
    count = 0
    prev_was_coeng = False
    for ch in text:
        cp = ord(ch)
        if cp == 0x17D2:  # KHMER SIGN COENG — next consonant is subscript
            prev_was_coeng = True
        elif 0x1780 <= cp <= 0x17A2:  # Khmer consonants
            if not prev_was_coeng:
                count += 1
            prev_was_coeng = False
        elif 0x17A0 <= cp <= 0x17B5:  # Independent vowels (each = one syllable)
            count += 1
            prev_was_coeng = False
        else:
            prev_was_coeng = False
    return max(1, count)


def apply_emotion_dsp_filter(audio_path: str, emotion: Optional[str]) -> bool:
    """
    Safely process audio for character emotion using high-precision FFmpeg audio filters.
    Applies tailored EQ frequency shaping (air presence for whisper, bite for angry, warmth for sad)
    without clipping or loss of original neural voice clarity.
    """
    if not emotion or emotion.lower() in ("neutral", "none", "normal", ""):
        return True

    spec = EMOTION_SPECS.get(emotion.lower())
    if not spec or not spec.get("filter"):
        return True

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return False

    import subprocess
    import shutil

    filter_str = spec["filter"]
    temp_filtered = audio_path.replace(".mp3", f"_dsp_{uuid.uuid4().hex[:6]}.mp3")

    cmd = [
        FFMPEG_PATH, "-y", "-i", audio_path,
        "-af", filter_str,
        "-b:a", "192k",
        temp_filtered
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(temp_filtered) and os.path.getsize(temp_filtered) > 0:
            shutil.move(temp_filtered, audio_path)
            return True
    except Exception as e:
        logger.warning(f"Failed to apply DSP filter for emotion '{emotion}': {e}")
        if os.path.exists(temp_filtered):
            try:
                os.remove(temp_filtered)
            except Exception:
                pass
    return False


class VoiceParamsResult(tuple):
    """
    3-tuple containing (voice, rate, pitch).
    Unpacks as (voice, rate, pitch) for backwards compatibility:
      voice_id, rate_str, pitch_str = resolve_voice_params(...)
    Also exposes properties:
      .voice, .rate, .pitch, .volume, .filter, .emotion, .pacing
    """
    def __new__(
        cls,
        voice: str,
        rate: str,
        pitch: str,
        volume: str = "+60%",
        filter_spec: Optional[str] = None,
        emotion: str = "neutral",
        pacing: str = "normal",
    ):
        instance = super().__new__(cls, (voice, rate, pitch))
        instance.voice = voice
        instance.rate = rate
        instance.pitch = pitch
        instance.volume = volume
        instance.filter = filter_spec
        instance.emotion = emotion
        instance.pacing = pacing
        return instance

    def __getitem__(self, key):
        if isinstance(key, str):
            mapping = {
                "voice": self[0],
                "rate": self[1],
                "pitch": self[2],
                "volume": getattr(self, "volume", "+60%"),
                "filter": getattr(self, "filter", None),
                "emotion": getattr(self, "emotion", "neutral"),
                "pacing": getattr(self, "pacing", "normal"),
            }
            if key in mapping:
                return mapping[key]
            raise KeyError(key)
        return super().__getitem__(key)


def resolve_voice_params(
    voice_key: Optional[str] = "km-KH-PisethNeural",
    base_rate: Optional[str] = "+0%",
    base_pitch: Optional[str] = "+0Hz",
    emotion: Optional[str] = "neutral",
    pacing: Optional[str] = "normal",
    pitch_override_offset: int = 0,
    rate_override_offset: int = 0,
    base_volume: Optional[str] = "+60%",
    volume_override_offset: int = 0,
) -> VoiceParamsResult:
    """
    Resolves voice identifier and computes effective pitch, rate, and volume including:
    - Base voice specs (Piseth, Sreymom, Boy, Girl)
    - Emotion offsets (Whisper, Angry, Sad, Excited, Terrified, Romantic, Suspense, Sarcastic, Exhausted)
    - Pacing offsets (Normal, Fast, Slow, Urgent)
    - Explicit tag overrides
    Returns VoiceParamsResult tuple (voice, effective_rate, effective_pitch) with .volume and .filter.
    """
    clean_key = (voice_key or "km-KH-PisethNeural").strip()
    spec = VOICE_SPECS.get(clean_key)
    if not spec:
        for k, s in VOICE_SPECS.items():
            if k.lower() == clean_key.lower():
                spec = s
                break
    if not spec:
        if "girl" in clean_key.lower() or "ក្មេងស្រី" in clean_key:
            spec = VOICE_SPECS["Khmer Girl 01"]
        elif "boy" in clean_key.lower() or "ក្មេងប្រុស" in clean_key:
            spec = VOICE_SPECS["Khmer Boy 01"]
        elif "sreymom" in clean_key.lower() or "female" in clean_key.lower():
            spec = VOICE_SPECS["Khmer Female 01"]
        else:
            spec = {"voice": clean_key, "pitch_offset": 0, "rate_offset": 0}

    # Resolve emotion spec
    emo_key = (emotion or "neutral").strip().lower()
    emo_spec = EMOTION_SPECS.get(emo_key, EMOTION_SPECS["neutral"])

    # Resolve pacing offset
    pacing_key = (pacing or "normal").strip().lower()
    pacing_offset = PACING_SPECS.get(pacing_key, 0)

    # Pitch calculation with natural human vocal bounds
    pitch_offset = (
        spec.get("pitch_offset", 0)
        + emo_spec.get("pitch_offset", 0)
        + pitch_override_offset
    )
    bp_match = re.search(r"[-+]?\d+", str(base_pitch or "0"))
    base_p = int(bp_match.group(0)) if bp_match else 0
    final_p = max(-10, min(24, base_p + pitch_offset))
    safe_pitch = f"+{final_p}Hz" if final_p >= 0 else f"{final_p}Hz"

    # Rate calculation with natural conversational bounds
    rate_offset = (
        spec.get("rate_offset", 0)
        + emo_spec.get("rate_offset", 0)
        + pacing_offset
        + rate_override_offset
    )
    br_match = re.search(r"[-+]?\d+", str(base_rate or "0"))
    base_r = int(br_match.group(0)) if br_match else 0
    final_r = max(-25, min(45, base_r + rate_offset))
    safe_rate = f"+{final_r}%" if final_r >= 0 else f"{final_r}%"

    # Volume calculation with natural bounds
    emo_vol_offset = emo_spec.get("volume_offset", 0)
    bv_match = re.search(r"[-+]?\d+", str(base_volume or "60"))
    base_v = int(bv_match.group(0)) if bv_match else 60
    final_v = max(10, min(100, base_v + emo_vol_offset + volume_override_offset))
    safe_volume = f"+{final_v}%"

    return VoiceParamsResult(
        voice=spec["voice"],
        rate=safe_rate,
        pitch=safe_pitch,
        volume=safe_volume,
        filter_spec=emo_spec.get("filter"),
        emotion=emo_key,
        pacing=pacing_key,
    )


async def synthesize_speech_async(
    text: str,
    voice: str = "km-KH-PisethNeural",
    output_path: str = "",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+60%",
    emotion: str = "neutral",
    pacing: str = "normal",
    max_retries: int = 3,
) -> bool:
    """Synthesize text to audio using edge-tts asynchronously with expressive emotion DSP.
    
    Extracts emotional and pacing tags ([Whisper], [Angry], [Fast], etc.) from text,
    normalizes prosodic parameters, and applies tailored non-destructive acoustic EQ.
    Retries up to max_retries times with exponential backoff on transient edge-tts failures.
    """
    if not text.strip():
        return False

    # Extract any inline emotion/pacing tags before synthesis
    clean_text, tag_emo, tag_pacing, p_ovr, r_ovr = extract_emotional_tags(text)
    eff_text = format_speech_text_for_natural_pacing(clean_text)
    if not eff_text:
        eff_text = text.strip()

    eff_emotion = tag_emo or emotion or "neutral"
    eff_pacing = tag_pacing or pacing or "normal"

    resolved_voice, safe_rate, safe_pitch = resolve_voice_params(
        voice_key=voice,
        base_rate=rate,
        base_pitch=pitch,
        emotion=eff_emotion,
        pacing=eff_pacing,
        pitch_override_offset=p_ovr,
        rate_override_offset=r_ovr,
    )
    
    # Calculate volume with emotion offset
    emo_key = eff_emotion.strip().lower()
    emo_vol_offset = EMOTION_SPECS.get(emo_key, {}).get("volume_offset", 0)
    import re
    bv_match = re.search(r"[-+]?\d+", str(volume or "60"))
    base_v = int(bv_match.group(0)) if bv_match else 60
    final_v = max(10, min(100, base_v + emo_vol_offset))
    safe_volume = f"+{final_v}%"

    # Parse initial rate value for retry step-down
    rm = re.search(r"[-+]?\d+", safe_rate)
    rate_val = int(rm.group(0)) if rm else 0

    for attempt in range(max_retries):
        current_rate = safe_rate
        if attempt > 0:
            stepped = max(-20, rate_val - attempt * 5)
            current_rate = f"+{stepped}%" if stepped >= 0 else f"{stepped}%"
            backoff = 0.5 * (2 ** (attempt - 1))
            logger.warning(
                f"edge-tts retry #{attempt + 1} for voice '{resolved_voice}' "
                f"(rate stepped to {current_rate}, backoff {backoff:.1f}s)..."
            )
            await asyncio.sleep(backoff)

        try:
            communicate = edge_tts.Communicate(
                text=eff_text,
                voice=resolved_voice,
                rate=current_rate,
                pitch=safe_pitch,
                volume=safe_volume
            )
            await communicate.save(output_path)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                apply_emotion_dsp_filter(output_path, eff_emotion)
                return True

            logger.warning(f"edge-tts produced empty audio (attempt {attempt + 1}/{max_retries})")

        except Exception as e:
            err_str = str(e).lower()
            is_transient = "no audio" in err_str or "no data" in err_str or "connection" in err_str
            if not is_transient or attempt >= max_retries - 1:
                logger.error(f"Error in edge-tts synthesis: {e}")
                return False
            logger.warning(f"Transient edge-tts error (attempt {attempt + 1}/{max_retries}): {e}")

    return False


def synthesize_segment(
    text: str,
    voice: str = "km-KH-PisethNeural",
    output_path: Optional[str] = None,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+60%",
    emotion: str = "neutral",
    pacing: str = "normal",
) -> Optional[str]:
    """Synchronous wrapper for single segment synthesis."""
    if not output_path:
        output_path = str(TEMP_DIR / f"tts_preview_{uuid.uuid4().hex[:8]}.mp3")
        
    success = asyncio.run(synthesize_speech_async(
        text=text,
        voice=voice,
        output_path=output_path,
        rate=rate,
        pitch=pitch,
        volume=volume,
        emotion=emotion,
        pacing=pacing,
    ))
    return output_path if success else None


async def synthesize_all_segments(
    segments: List[Dict],
    voice: str = "km-KH-PisethNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+60%",
    auto_adjust_duration: bool = True,
    max_total_duration: Optional[float] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict]:
    """
    Synthesize Khmer TTS audio for all segments.
    Per-segment voice is resolved from each segment's 'voice' field.
    Automatically parses emotional bracket tags ([Whisper], [Angry], etc.),
    modulates speed/pitch/volume prosody, and applies acoustic EQ filtering.
    """
    total = len(segments)
    sem = asyncio.Semaphore(6)
    completed_count = 0

    async def _process_single(idx: int, seg: Dict) -> Dict:
        nonlocal completed_count
        seg_copy = dict(seg)
        khmer_text = seg_copy.get("khmer_text", "").strip()
        if not khmer_text:
            khmer_text = seg_copy.get("text", "").strip()
            
        if not khmer_text:
            return seg_copy

        # Extract emotional / pacing tags from text
        clean_text, tag_emo, tag_pace, p_ovr, r_ovr = extract_emotional_tags(khmer_text)
        if clean_text:
            seg_copy["khmer_text"] = clean_text
            khmer_text = clean_text

        segment_id = seg_copy.get("id", idx + 1)
        raw_audio_path = str(TEMP_DIR / f"seg_{segment_id}_raw_{uuid.uuid4().hex[:6]}.mp3")

        # Resolve per-segment voice and emotion/pacing
        seg_voice_label = (seg_copy.get("voice") or "").strip()
        target_voice = seg_voice_label if seg_voice_label else voice
        seg_emotion = (tag_emo or seg_copy.get("emotion") or "neutral").strip()
        seg_pacing = (tag_pace or seg_copy.get("pacing") or "normal").strip()
        seg_copy["emotion"] = seg_emotion
        seg_copy["pacing"] = seg_pacing

        seg_start = float(seg_copy.get("start", 0.0))
        seg_orig_end = float(seg_copy.get("end", seg_start + 1.0))
        target_duration = max(0.4, seg_orig_end - seg_start)

        next_seg_start = None
        if idx + 1 < total:
            try:
                next_seg_start = float(segments[idx + 1].get("start", 0.0))
            except (ValueError, TypeError):
                next_seg_start = None

        if next_seg_start is not None and next_seg_start > seg_start:
            available_slot = max(0.4, (next_seg_start - 0.05) - seg_start)
        elif max_total_duration and max_total_duration > 0:
            available_slot = max(0.4, (max_total_duration - 0.05) - seg_start)
        else:
            available_slot = target_duration

        effective_rate = rate
        syllable_count = estimate_khmer_syllables(khmer_text)
        if available_slot > 0 and syllable_count > 0:
            # Edge-TTS km-KH natural pacing at +0% rate: ~3.2 syllables/second
            est_dur = syllable_count / 3.2
            if est_dur > available_slot:
                ratio = est_dur / available_slot
                needed_boost = int(min(50, max(8, (ratio - 1.0) * 100)))
                import re
                m = re.search(r"[-+]?\d+", str(rate or "0"))
                base_val = int(m.group(0)) if m else 0
                effective_rate = f"+{base_val + needed_boost}%"

        async with sem:
            success = await synthesize_speech_async(
                text=khmer_text,
                voice=target_voice,
                output_path=raw_audio_path,
                rate=effective_rate,
                pitch=pitch,
                volume=volume,
                emotion=seg_emotion,
                pacing=seg_pacing,
            )

        completed_count += 1
        if progress_callback:
            progress_callback(completed_count, total, f"Synthesized Khmer speech ({completed_count}/{total})...")

        if success and os.path.exists(raw_audio_path):
            actual_duration = get_audio_duration(raw_audio_path)
            final_audio_path = raw_audio_path

            slot_limit = min(target_duration * 1.25, available_slot) if available_slot > target_duration else available_slot
            if max_total_duration and max_total_duration > 0:
                slot_limit = min(slot_limit, max(0.4, (max_total_duration - 0.05) - seg_start))

            if auto_adjust_duration and slot_limit > 0 and actual_duration > (slot_limit + 0.05):
                stretched_path = str(TEMP_DIR / f"seg_{segment_id}_fit_{uuid.uuid4().hex[:6]}.mp3")
                stretched = await asyncio.to_thread(time_stretch_audio, raw_audio_path, stretched_path, slot_limit)
                if stretched and os.path.exists(stretched_path):
                    final_audio_path = stretched_path
                    actual_duration = get_audio_duration(final_audio_path)
                    
            seg_copy["audio_path"] = final_audio_path
            seg_copy["actual_duration"] = actual_duration

            seg_end = round(seg_start + actual_duration, 2)
            if next_seg_start is not None and next_seg_start > seg_start and seg_end > (next_seg_start - 0.03):
                seg_end = round(next_seg_start - 0.03, 2)
            if max_total_duration and seg_end > (max_total_duration - 0.05):
                seg_end = round(max_total_duration - 0.05, 2)

            seg_copy["end"] = seg_end
        else:
            seg_copy["audio_path"] = None
            seg_copy["actual_duration"] = 0.0

        return seg_copy

    tasks = [_process_single(i, seg) for i, seg in enumerate(segments)]
    updated_segments = await asyncio.gather(*tasks)
    return list(updated_segments)
