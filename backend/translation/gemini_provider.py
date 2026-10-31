"""
Google Gemini Translation Provider.
Optimized for natural spoken Khmer dialogue adaptation, timing preservation, and dynamic model fallback.
"""

import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

from ..config import DEFAULT_GEMINI_API_KEY, GEMINI_TRANSLATION_MODELS
from .base import (
    ErrorCode,
    STYLE_PROMPTS,
    TranslationError,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
    TranslationStyle,
    get_style_prompt,
)

logger = logging.getLogger("gemini_provider")

DEFAULT_SYSTEM_INSTRUCTION = """
You are an award-winning Cambodian cinema dubbing director and master audiovisual translator specializing in vibrant, natural, authentic spoken Khmer (ភាសាខ្មែរ) dialogue adaptation for voice actors.

Your mission is to adapt dialogue segments into natural, spoken cinema Khmer dialogue for AI character dubbing (Edge-TTS voices Piseth & Sreymom):

1. Authentic Cinema Spoken Dialogue (របៀបនិយាយបែបភាពយន្តខ្មែររស់រវើក):
   - Phrasing MUST sound like real people talking in contemporary Cambodian movies and TV series — NEVER robotic literal translation or bookish text.
   - Use natural conversational negatives: Use "អត់" or "មិន" (e.g. "អត់ទៅទេ", "អត់ដឹងទេ", "ធ្វើមិនកើតទេ"), NEVER archaic/literary "ពុំ" or "ពុំដែល".
   - Use natural conversational questions and endings: "ម៉េចចឹង?", "ធ្វើអីហ្នឹង?", "ទៅណា?", "មែនអត់?", "ពិតមែនហ្អី?", "មែនតើ!". Avoid bookish "តើអ្នក...".
   - Rich natural spoken particles & interjections: (ណា៎, ណាស់, ហ្នឹងហើយ, អីចឹង, អើ, ហាស!, អូ!, ហេ!, ម៉េចក៏, គ្នា, ឯង, ខ្ញុំ, គេ, ចាស, បាទ...).
   - Adapt idioms and slang into equivalent everyday Cambodian colloquial phrasing so characters feel alive, dynamic, and emotionally expressive.

2. Syllable Budget & Dubbing Timing Economy (CRITICAL FOR DUBBING):
   - Each segment includes `syllable_budget`: maximum Khmer syllables that fit within the timestamp duration at Edge-TTS natural pacing (~3.2 syllables/second).
   - Your translation MUST NOT exceed `syllable_budget`. Aim for 80–92% of the budget to allow natural breathing pauses between dialogue lines.
   - For short segments (budget ≤ 5 syllables), use ultra-concise, punchy Khmer exclamations (e.g., "ឈប់សិន!", "ទៅហើយ!", "ប្រយ័ត្ន!", "អីហ្នឹង?!").
   - Count syllables accurately: independent vowels and consonant clusters without subscript coeng = 1 syllable each. Subscript stacks (្) do NOT add extra syllables.

3. Character Emotion & Voice Persona Direction:
   - Accurately determine and assign character emotion and pacing for each segment based on the dialogue context:
     * "neutral": everyday casual conversation / narration
     * "whisper": soft, secret, confidential, intimate tension
     * "angry": aggressive, shouting, arguing, high energy
     * "sad": tearful, depressed, grieving, gentle low cadence
     * "excited": cheerful, joyful, celebratory, energetic
     * "terrified": panicked, breathless, screaming in fear
     * "romantic": warm, tender, sensual, affectionate
     * "suspense": mysterious, ominous, intense dramatic tension
     * "sarcastic": witty, ironic, teasing, humorous
     * "exhausted": tired, weary, breathless, drained
   - Assign pacing: "normal", "fast" (arguments/action), "slow" (sadness/suspense), or "urgent".
   - Mirror the emotion in your vocabulary choices and sentence punctuation.

4. Names, Places & Technical Terms:
   - Transcribe international names, locations, and brands into clean, phonetic Khmer script.

5. Strict JSON Output:
   - Return ONLY a valid JSON array of objects with schema:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 3.5,
    "khmer_text": "អត្ថបទភាសាខ្មែរនិយាយបែបធម្មជាតិរស់រវើក",
    "tone": "natural",
    "emotion": "neutral",
    "pacing": "normal"
  }
]
Output pure raw JSON only. No markdown formatting, no code fences, no explanations.
"""


class GeminiProvider(TranslationProviderInterface):
    """Google Gemini translation provider with automated model fallback and retry."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_API_KEY
        self._cached_models: List[str] = []

    def get_name(self) -> str:
        return "gemini"

    def get_display_name(self) -> str:
        return "Gemini"

    def get_description(self) -> str:
        return "Best for context-aware dubbing, natural spoken Khmer, and dialogue adaptation."

    def get_supported_models(self) -> List[str]:
        return GEMINI_TRANSLATION_MODELS

    def get_default_model(self) -> str:
        return "gemini-2.5-flash"  # Real, fast, production model

    def _get_client(self, api_key: Optional[str] = None) -> genai.Client:
        key = api_key or self._api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_API_KEY
        if not key:
            raise TranslationError(
                code=ErrorCode.INVALID_API_KEY,
                message="Google Gemini API Key is missing. Please configure GEMINI_API_KEY.",
                retryable=False,
                provider="gemini",
            )
        return genai.Client(api_key=key)

    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        creds = credentials or {}
        key = creds.get("api_key") or creds.get("gemini_api_key") or self._api_key or DEFAULT_GEMINI_API_KEY
        if not key:
            return {
                "success": False,
                "message": "No Gemini API key provided",
                "latency_ms": 0,
                "models": self.get_supported_models(),
            }

        start_t = time.time()
        try:
            from ..translation_engine import generate_content_with_retry_and_fallback

            client = genai.Client(api_key=key)
            # Fast ping with tiny prompt using exponential backoff retry & model fallback
            response = generate_content_with_retry_and_fallback(
                client=client,
                model_name="gemini-2.5-flash",
                contents="Hi",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
            elapsed = int((time.time() - start_t) * 1000)
            used_model = getattr(response, "_used_model", "gemini-2.5-flash")
            return {
                "success": True,
                "message": f"Connected successfully! (Model: {used_model}, Latency: {elapsed}ms)",
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }
        except Exception as e:
            elapsed = int((time.time() - start_t) * 1000)
            err_str = str(e)
            return {
                "success": False,
                "message": f"Connection failed: {err_str[:150]}",
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }

    def _parse_llm_json(self, text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # 1. Standard json.loads
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # 2. Strict=False
        try:
            data = json.loads(text, strict=False)
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # 3. Bracket extraction
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                data = json.loads(candidate, strict=False)
                if isinstance(data, list):
                    return data
            except Exception:
                pass

        # 4. Regex extraction fallback
        items = []
        pattern = r'\{\s*"id"\s*:\s*(\d+).*?"khmer_text"\s*:\s*"((?:\\.|[^"\\])*)"'
        for match in re.finditer(pattern, text, re.DOTALL):
            try:
                seg_id = int(match.group(1))
                val = match.group(2).replace('\\"', '"').replace('\\n', '\n')
                items.append({"id": seg_id, "khmer_text": val})
            except Exception:
                pass

        if items:
            return items

        raise ValueError(f"Could not parse valid JSON from Gemini output: {text[:160]}")

    def translate(
        self,
        segments: List[TranslationSegment],
        source_language: str = "en",
        target_language: str = "km",
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TranslationResult:
        if not segments:
            return TranslationResult(
                success=True,
                provider="gemini",
                model=self.get_default_model(),
                source_language=source_language,
                target_language=target_language,
                segments=[],
            )

        start_time = time.time()
        opts = options or {}
        model_name = opts.get("model") or opts.get("model_name") or self.get_default_model()
        style_instruction = get_style_prompt(opts.get("style"))
        glossary_instruction = opts.get("glossary_instruction", "")

        api_key = opts.get("api_key") or self._api_key

        try:
            client = self._get_client(api_key)
        except TranslationError as te:
            return TranslationResult(
                success=False,
                provider="gemini",
                model=model_name,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=te,
            )

        # Build payload with per-segment syllable budget for precise timing guidance
        payload = [
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "speaker": s.speaker,
                "text": s.source_text,
                "syllable_budget": max(3, int((s.end - s.start) * 3.2)),
            }
            for s in segments
        ]

        system_instruction = (
            DEFAULT_SYSTEM_INSTRUCTION
            + f"\nSource Language: {source_language}\nTarget Language: {target_language}\n"
            + f"{style_instruction}\n"
            + glossary_instruction
        )

        user_prompt = (
            f"Translate these dialogue segments into natural spoken Khmer for voice dubbing:\n"
            f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
        )

        # Resolve candidates order for Auto Detect / Fallback
        try:
            from ..translation_engine import generate_content_with_retry_and_fallback

            response = generate_content_with_retry_and_fallback(
                client=client,
                model_name=model_name or "gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=float(opts.get("temperature", 0.3)),
                    response_mime_type="application/json",
                ),
                progress_callback=progress_callback,
            )

            actual_model = getattr(response, "_used_model", model_name or "gemini-2.5-flash")
            response_text = (response.text or "").strip()
            parsed = self._parse_llm_json(response_text)
            trans_map = {item["id"]: item for item in parsed if "id" in item}

            from ..tts_engine import extract_emotional_tags

            updated_segments: List[TranslationSegment] = []
            for s in segments:
                seg_copy = TranslationSegment.from_dict(s.to_dict())
                if s.id in trans_map:
                    item = trans_map[s.id]
                    raw_trans = item.get("khmer_text") or item.get("translated_text") or s.source_text
                    clean_text, tag_emo, tag_pace, _, _ = extract_emotional_tags(raw_trans)
                    final_text = clean_text or raw_trans
                    seg_copy.khmer_text = final_text
                    seg_copy.translated_text = final_text
                    seg_copy.tone = item.get("tone", s.tone or "neutral")
                    seg_copy.emotion = tag_emo or item.get("emotion") or s.emotion or "neutral"
                    seg_copy.pacing = tag_pace or item.get("pacing") or s.pacing or "normal"
                else:
                    if not seg_copy.khmer_text:
                        seg_copy.khmer_text = seg_copy.source_text
                        seg_copy.translated_text = seg_copy.source_text

                seg_copy.provider = "gemini"
                updated_segments.append(seg_copy)

            duration_ms = int((time.time() - start_time) * 1000)
            return TranslationResult(
                success=True,
                provider="gemini",
                model=actual_model,
                source_language=source_language,
                target_language=target_language,
                segments=updated_segments,
                duration_ms=duration_ms,
            )

        except Exception as err:
            err_str = str(err)
            is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()
            is_auth_error = "API_KEY_INVALID" in err_str or "unauthorized" in err_str.lower() or "401" in err_str

            if is_auth_error:
                last_error = TranslationError(
                    code=ErrorCode.INVALID_API_KEY,
                    message=f"Gemini API key is invalid: {err_str}",
                    retryable=False,
                    provider="gemini",
                )
            elif is_rate_limit:
                last_error = TranslationError(
                    code=ErrorCode.RATE_LIMIT,
                    message=f"Gemini quota or rate limit exceeded: {err_str}",
                    retryable=True,
                    provider="gemini",
                )
            else:
                last_error = TranslationError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Gemini translation error: {err_str}",
                    retryable=True,
                    provider="gemini",
                )

            return TranslationResult(
                success=False,
                provider="gemini",
                model=model_name or "gemini",
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=last_error,
                duration_ms=int((time.time() - start_time) * 1000),
            )
