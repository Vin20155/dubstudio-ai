"""
Base classes, interfaces, and normalized data contracts for Multi-Provider Translation Engine.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ErrorCode(str, Enum):
    INVALID_API_KEY = "INVALID_API_KEY"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class TranslationStyle(str, Enum):
    NATURAL = "natural"
    LITERAL = "literal"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    DRAMATIC = "dramatic"
    MOVIE_DRAMA = "movie_drama"
    DOCUMENTARY = "documentary"
    YOUTUBE = "youtube"
    VOICE_DUBBING = "voice_dubbing"
    HISTORICAL_ROYAL = "historical_royal"
    ANIME_CARTOON = "anime_cartoon"
    ACTION_THRILLER = "action_thriller"
    COMEDY_HUMOR = "comedy_humor"
    VIRAL_SHORTS = "viral_shorts"
    KIDS_STORY = "kids_story"
    HORROR_SUSPENSE = "horror_suspense"


STYLE_PROMPTS: Dict[str, str] = {
    TranslationStyle.NATURAL.value: "Style: Natural colloquial dialogue as spoken in everyday Cambodian conversations.",
    TranslationStyle.LITERAL.value: "Style: Accurate, faithful direct translation maintaining original sentence structure.",
    TranslationStyle.PROFESSIONAL.value: "Style: Professional, polished formal register suitable for news and corporate presentations.",
    TranslationStyle.CASUAL.value: "Style: Friendly, casual, modern conversational Khmer.",
    TranslationStyle.DRAMATIC.value: "Style: Emotionally expressive, impactful dialogue fitting dramatic cinema scenes.",
    TranslationStyle.MOVIE_DRAMA.value: "Style: Movie and cinema dubbing style with rich character voice, natural conversational negatives and questions, and lively pacing.",
    TranslationStyle.DOCUMENTARY.value: "Style: Informative, clear, documentary narrator register.",
    TranslationStyle.YOUTUBE.value: "Style: Engaging, punchy, dynamic phrasing ideal for social media and YouTube videos.",
    TranslationStyle.VOICE_DUBBING.value: "Style: Voice dubbing optimized for Edge-TTS with strict syllable count economy and punchy delivery.",
    TranslationStyle.HISTORICAL_ROYAL.value: "Style: Historical and royal drama register using proper Khmer court vocabulary (រាជសព្ទ), formal honorifics (ទ្រង់, ព្រះអង្គ, ទូលបង្គំ, ម្ចាស់បង), and classical cinematic cadence.",
    TranslationStyle.ANIME_CARTOON.value: "Style: Lively anime and cartoon dubbing with animated character energy, playful particles (ញ៉យ, ហិហិ, វ៉ើយ), and expressive reactions.",
    TranslationStyle.ACTION_THRILLER.value: "Style: High-adrenaline action and thriller dialogue with ultra-short, punchy tactical commands (កុំកម្រើក!, រត់!, ប្រយ័ត្ន!), high urgency, and strict timing economy.",
    TranslationStyle.COMEDY_HUMOR.value: "Style: Comedic and witty sitcom dialogue adapted with natural Cambodian humor, playful sarcasm, and funny colloquial slang.",
    TranslationStyle.VIRAL_SHORTS.value: (
        "Style: TikTok & Reels Viral Shorts Cinema Adaptation (រសជាតិជាមនុស្សរស់រវើកក្នុងសាច់រឿង - Human Dramatic Story Flavor):\n"
        "1. REAL HUMAN DRAMATIC IMMERSION (មានរសជាតិជាមនុស្សនៅក្នុងសាច់រឿង មិនមែនមនុស្សយន្តអានអក្សរ):\n"
        "   - Phrasing MUST sound like living, breathing characters caught in intense, dramatic, or hilarious human moments.\n"
        "   - NEVER produce sterile, robotic, or literary textbook Khmer. Characters must express visceral gut feelings.\n"
        "   - Expressive spoken outbursts & interjections based on scene mood:\n"
        "     * Shock & disbelief: 'ហាស?! ស្អីគេហ្នឹង?!', 'យី! ម៉េចចឹង?', 'ងាប់ហើយ! ពិតមែនហ្អី?!', 'អត់សមសោះ!'\n"
        "     * High stakes / panic: 'ប្រយ័ត្ន!', 'រត់លឿនឡើង!', 'ឈប់សិន!', 'កុំអាលទៅ!', 'មិនស្រួលទេ!', 'ធ្វើម៉េចទៅ?!'\n"
        "     * Suspicion / sarcasm / mocking: 'កុំមកកុហក!', 'មែនអត់ហ្នឹង?', 'ច្បាស់ខ្លួនឯងអត់?', 'គិតថាខ្ញុំល្ងង់ហ្អី?', 'ឌឺដល់ហើយ!'\n"
        "     * Heartbreak / despair: 'ហេតុអីបានជាបែបនេះ...?', 'ខ្ញុំទ្រាំលែងបានហើយ...', 'ឈប់ទៅបានទេ...?'\n"
        "     * Tenderness / romance: 'មិនអីទេណា៎...', 'កុំភ័យអី... មានខ្ញុំនៅទីនេះ', 'ស្តាប់ខ្ញុំសិន...'\n"
        "2. NATURAL CONVERSATIONAL PRONOUNS (សព្វនាមបែបមនុស្សពិត ហាមដាច់ខាតពាក្យ អ្នក/ខ្ញុំ ស្ងួតៗ):\n"
        "   - Strictly ban cold, robotic 'អ្នក' (You) and 'ខ្ញុំ' (I) when characters have emotional relationships.\n"
        "   - Use authentic relationship address terms:\n"
        "     * Friends / peers / rivals: ឯង, គ្នា, យើង, អាឯង, ពួកយើង, អាម្នាក់ហ្នឹង, មីមួយហ្នឹង\n"
        "     * Lovers / couples: បង, អូន\n"
        "     * Elders / respect: ពូ, មីង, បងប្រុស, បងស្រី, លោកពូ, អ្នកមីង\n"
        "     * Family: ម៉ែ, ឪ, កូន, ប្អូន\n"
        "     * 3rd-person gossip / reactions: គេ, ពួកវា, អាម្នាក់ហ្នឹង, ម្នាក់ហ្នឹង\n"
        "3. NATURAL SPOKEN NEGATIVES & QUESTION ENDINGS (ភាសានិយាយរស់រវើក):\n"
        "   - Strictly ban archaic/written 'ពុំ', 'ពុំដែល', 'តើអ្នក...', 'តើ...ឬទេ?'.\n"
        "   - Use lively spoken forms: 'អត់ទៅទេ', 'អត់ដឹងទេ', 'ធ្វើមិនកើតទេ', 'ម៉េចចឹង?', 'ធ្វើអីហ្នឹង?', 'ទៅណា?', 'មែនអត់?', 'មែនតើ!', 'ហ្នឹងហើយ!', 'ណា៎!', 'ហាស!'.\n"
        "4. TIKTOK & SHORTS PACING (ក្បួនវីដេអូខ្លី TikTok & Shorts: ខ្លី ខ្លឹម ចាក់ដោត កន្ត្រាក់អារម្មណ៍):\n"
        "   - Viewers swipe in 2 seconds. Lines must be concise, punchy, and instantly hook the viewer's attention.\n"
        "   - Short segments (≤ 1.5s) must be razor-sharp exclamations (e.g. 'ឈប់សិន!', 'ទៅហើយ!', 'ប្រយ័ត្ន!', 'ស្អីគេ?!', 'មិនពិតទេ!').\n"
        "   - Respect syllable budget so Edge-TTS voice actors speak with natural human breath and cadence without rushing.\n"
        "5. DYNAMIC EMOTION & PACING TAGGING:\n"
        "   - Accurately assign character emotion ('angry', 'whisper', 'sad', 'excited', 'terrified', 'romantic', 'suspense', 'sarcastic', 'exhausted', 'neutral') and pacing ('urgent', 'fast', 'slow', 'normal') so the TTS voice sounds fully alive and human."
    ),
    TranslationStyle.KIDS_STORY.value: "Style: Gentle, sweet, simple vocabulary and storytelling cadence suitable for children's animation and bedtime tales.",
    TranslationStyle.HORROR_SUSPENSE.value: "Style: Ominous, eerie, suspenseful atmosphere with breathy phrasing, tense pauses, and dramatic tension.",
}


def get_style_prompt(style_name: Optional[str]) -> str:
    key = str(style_name or TranslationStyle.NATURAL.value).lower().strip()
    return STYLE_PROMPTS.get(key, f"Style: {key}")


@dataclass
class TranslationError(Exception):
    code: ErrorCode
    message: str
    retryable: bool = False
    provider: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value if isinstance(self.code, ErrorCode) else str(self.code),
            "message": self.message,
            "retryable": self.retryable,
            "provider": self.provider,
        }

    def __str__(self) -> str:
        return f"[{self.provider} - {self.code.value}] {self.message}"


def _parse_time_to_seconds(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return 0.0
    try:
        return float(val_str)
    except ValueError:
        pass
    # Handle "HH:MM:SS,mmm", "HH:MM:SS.mmm", "MM:SS.mmm", or "MM:SS"
    val_str = val_str.replace(",", ".")
    parts = val_str.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except Exception:
        return 0.0
    return 0.0


@dataclass
class TranslationSegment:
    id: int
    start: float
    end: float
    speaker: str = "SPEAKER_01"
    source_text: str = ""
    translated_text: str = ""
    khmer_text: str = ""
    tone: str = "neutral"
    emotion: str = "neutral"
    pacing: str = "normal"
    provider: Optional[str] = None
    locked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Ensure khmer_text and translated_text are in sync for backwards compatibility
        if not d.get("khmer_text") and d.get("translated_text"):
            d["khmer_text"] = d["translated_text"]
        elif not d.get("translated_text") and d.get("khmer_text"):
            d["translated_text"] = d["khmer_text"]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationSegment":
        text = data.get("text", "") or data.get("source_text", "")
        khmer = data.get("khmer_text", "") or data.get("translated_text", "")
        raw_id = data.get("id") if data.get("id") is not None else data.get("index", 1)
        try:
            seg_id = int(raw_id)
        except (ValueError, TypeError):
            seg_id = 1

        return cls(
            id=seg_id,
            start=round(_parse_time_to_seconds(data.get("start", 0.0)), 3),
            end=round(_parse_time_to_seconds(data.get("end", 0.0)), 3),
            speaker=str(data.get("speaker", "SPEAKER_01")),
            source_text=str(text).strip(),
            translated_text=str(khmer).strip(),
            khmer_text=str(khmer).strip(),
            tone=str(data.get("tone", "neutral")),
            emotion=str(data.get("emotion", "neutral")),
            pacing=str(data.get("pacing", "normal")),
            provider=data.get("provider"),
            locked=bool(data.get("locked", False)),
        )



@dataclass
class TranslationResult:
    success: bool
    provider: str
    model: str
    source_language: str
    target_language: str
    segments: List[TranslationSegment] = field(default_factory=list)
    error: Optional[TranslationError] = None
    cached_count: int = 0
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "success": self.success,
            "provider": self.provider,
            "model": self.model,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "segments": [s.to_dict() for s in self.segments],
            "cached_count": self.cached_count,
            "duration_ms": self.duration_ms,
        }
        if self.error:
            res["error"] = self.error.to_dict()
        return res


@dataclass
class TranslationOption:
    style: str = TranslationStyle.NATURAL.value
    use_context: bool = True
    preserve_speaker_personality: bool = True
    optimize_for_dubbing: bool = True
    use_translation_memory: bool = True
    use_glossary: bool = True
    enable_fallback: bool = True
    fallback_provider: Optional[str] = None
    temperature: float = 0.3
    custom_instructions: Optional[str] = None


class TranslationProviderInterface(ABC):
    """
    Standard interface that every translation provider must implement.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Unique provider identifier: gemini, openai, google_cloud, local_model."""
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """Human-readable provider name for UI cards."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Brief descriptive text about provider strengths."""
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """List of supported model identifiers."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Default model for this provider."""
        pass

    @abstractmethod
    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Verify provider connectivity and credentials.
        Returns: {"success": bool, "message": str, "latency_ms": int, "models": list}
        """
        pass

    @abstractmethod
    def translate(
        self,
        segments: List[TranslationSegment],
        source_language: str = "en",
        target_language: str = "km",
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TranslationResult:
        """
        Translates a list of dialogue segments. Must return a normalized TranslationResult.
        """
        pass
