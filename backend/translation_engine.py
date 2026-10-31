import json
import logging
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

try:
    from tenacity import (
        Retrying,
        retry_if_exception,
        stop_after_attempt,
        wait_random_exponential,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

from .config import DEFAULT_GEMINI_API_KEY

logger = logging.getLogger("translation_engine")
logger.setLevel(logging.INFO)


def get_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    """Initialize and return Google GenAI client."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_API_KEY
    if not key:
        raise ValueError("Google Gemini API Key is required for translation and Gemini STT.")
    return genai.Client(api_key=key)


KHMER_DUBBING_SYSTEM_INSTRUCTION = """
You are an award-winning Cambodian cinema dubbing director and master audiovisual translator specializing in vibrant, natural, authentic spoken Khmer (ភាសាខ្មែរ) dialogue adaptation for voice actors.

Your mission is to adapt spoken dialogue from the video transcript into natural, spoken cinema Khmer dialogue for AI character dubbing (Edge-TTS voices Piseth & Sreymom):

1. Authentic Cinema Spoken Dialogue (របៀបនិយាយបែបភាពយន្តខ្មែររស់រវើក):
   - Phrasing MUST sound like real people talking in contemporary Cambodian cinema — NEVER robotic literal translation or bookish text.
   - Use natural conversational negatives: Use "អត់" or "មិន" (e.g. "អត់ទៅទេ", "អត់ដឹងទេ", "ធ្វើមិនកើតទេ"), NEVER archaic/literary "ពុំ" or "ពុំដែល".
   - Use natural conversational questions and endings: "ម៉េចចឹង?", "ធ្វើអីហ្នឹង?", "ទៅណា?", "មែនអត់?", "ពិតមែនហ្អី?", "មែនតើ!". Avoid bookish "តើអ្នក...".
   - Rich natural spoken particles & interjections: (ណា៎, ណាស់, ហ្នឹងហើយ, អីចឹង, អើ, ហាស!, អូ!, ហេ!, ម៉េចក៏, គ្នា, ឯង, ខ្ញុំ, គេ, ចាស, បាទ...).
   - Adapt idioms and expressions into equivalent everyday Cambodian colloquial phrasing so characters feel alive, dynamic, and emotionally expressive.

2. Syllable Budget & Dubbing Timing Economy (CRITICAL FOR DUBBING):
   - Each input segment includes `syllable_budget`: maximum Khmer syllables that fit within the timestamp duration at Edge-TTS natural pacing (~3.2 syllables/second).
   - Your translation MUST NOT exceed `syllable_budget`. Aim for 80–92% of the budget to allow natural breathing pauses between dialogue lines.
   - For short segments (budget ≤ 5 syllables), use ultra-concise, punchy Khmer exclamations (e.g., "ឈប់សិន!", "ទៅហើយ!", "ប្រយ័ត្ន!", "អីហ្នឹង?!").
   - Count syllables accurately: independent vowels and consonant clusters without subscript coeng = 1 syllable each. Subscript stacks (្) do NOT add extra syllables.

3. Tone & Character Emotion Direction:
   - Accurately determine and assign character emotion and pacing for each segment:
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
   - Reflect this in the vocabulary and dialogue flow.

4. Retention of Names & Terms: Keep international proper nouns, brand names, and technical terms phonetically accurate in clean Khmer script.

5. Strict JSON Output: Output a valid JSON array of objects with the exact schema:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 3.5,
    "text": "original text",
    "khmer_text": "អត្ថបទភាសាខ្មែរដែលត្រូវនិយាយ",
    "emotion": "neutral",
    "pacing": "normal"
  }
]
Do not include markdown codeblocks or explanation. Return ONLY the raw JSON array.
"""


def extract_and_parse_json(text: str) -> List[Dict]:
    """Robustly decodes JSON response from LLM, handling malformed syntax, unescaped quotes, or trailing commas."""
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

    # 2. Strict=False (permits control characters/newlines)
    try:
        data = json.loads(text, strict=False)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    # 3. Extract bracketed array [ ... ] and strip trailing commas
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

    # 4. Regex extraction salvage for [{"id": ..., "khmer_text": ...}]
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

    # 5. Line-by-line fallback regex
    pattern_fallback = r'"id"\s*:\s*(\d+).*?"khmer_text"\s*:\s*"([^"\r\n]*)'
    for match in re.finditer(pattern_fallback, text):
        try:
            seg_id = int(match.group(1))
            val = match.group(2)
            items.append({"id": seg_id, "khmer_text": val})
        except Exception:
            pass

    if items:
        return items

    raise ValueError(f"Could not parse translation JSON from Gemini response: {text[:200]}")


_cached_gemini_models: List[str] = []
_cached_gemini_models_ts: float = 0.0
_MODEL_CACHE_TTL: float = 600.0  # 10 minutes — avoid per-call network round-trips


def get_available_gemini_models(client: genai.Client) -> List[str]:
    """Queries Google GenAI API to discover available models, with 10-min in-memory TTL cache.
    Returns empty list on failure (caller falls back to hardcoded candidates).
    """
    global _cached_gemini_models, _cached_gemini_models_ts
    now = time.time()
    if _cached_gemini_models and (now - _cached_gemini_models_ts) < _MODEL_CACHE_TTL:
        return _cached_gemini_models

    try:
        models_list = []
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            methods = getattr(m, "supported_generation_methods", None)
            if methods is None or "generateContent" in methods:
                models_list.append(name)
        if models_list:
            logger.info(f"Discovered {len(models_list)} Gemini models (cached for {int(_MODEL_CACHE_TTL)}s): {models_list[:8]}")
            _cached_gemini_models = models_list
            _cached_gemini_models_ts = now
            return models_list
    except Exception as err:
        logger.warning(f"Could not list models via client.models.list(): {err}")

    return []


def is_transient_gemini_error(e: BaseException) -> bool:
    """
    Identifies temporary API errors suitable for retry with exponential backoff and jitter:
    - 503 UNAVAILABLE (high demand, spikes in demand, overloaded, please try again later)
    - 429 RESOURCE_EXHAUSTED (rate limits, quota spikes)
    - 500 / 502 / 504 server errors and gateway timeouts
    - Network drops, connection reset, connection refused, or socket timeouts
    """
    err_str = str(e).lower()

    # Non-retriable model errors that should immediately skip to next fallback model
    if any(code in err_str for code in ["404", "not_found", "unknown model"]):
        return False
    # Permanent auth errors
    if any(code in err_str for code in ["api_key_invalid", "unauthenticated", "401"]):
        return False

    transient_indicators = [
        "503",
        "unavailable",
        "high demand",
        "spikes in demand",
        "try again later",
        "overloaded",
        "temporarily unavailable",
        "429",
        "resource_exhausted",
        "quota",
        "rate limit",
        "500",
        "502",
        "504",
        "gateway timeout",
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "remotedisconnected",
        "broken pipe",
    ]
    return any(ind in err_str for ind in transient_indicators)


def execute_model_call_with_retry(
    client: genai.Client,
    model_name: str,
    contents: Any,
    config: Any,
    max_retries: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 6.0,
) -> Any:
    """
    Executes client.models.generate_content for a single model with exponential backoff and jitter.
    Prefers `tenacity` if installed, with a built-in full jitter exponential backoff fallback.
    """
    if HAS_TENACITY:
        for attempt in Retrying(
            stop=stop_after_attempt(max_retries),
            wait=wait_random_exponential(multiplier=1.0, min=min_wait, max=max_wait),
            retry=retry_if_exception(is_transient_gemini_error),
            reraise=True,
        ):
            with attempt:
                attempt_num = attempt.retry_state.attempt_number
                if attempt_num > 1:
                    logger.warning(f"Tenacity retry #{attempt_num} for Gemini model '{model_name}'...")
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
    else:
        last_exc = None
        for attempt in range(max_retries):
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                last_exc = e
                if not is_transient_gemini_error(e) or attempt >= max_retries - 1:
                    raise e

                # Standard Exponential Backoff with Full Jitter:
                base_delay = min(max_wait, min_wait * (2 ** attempt))
                jittered_delay = random.uniform(0.6, 1.2) * base_delay
                logger.warning(
                    f"Transient error calling '{model_name}' (attempt {attempt + 1}/{max_retries}): {str(e)[:120]}. "
                    f"Retrying with jitter backoff in {jittered_delay:.2f}s..."
                )
                time.sleep(jittered_delay)
        if last_exc:
            raise last_exc


def generate_content_with_retry_and_fallback(
    client: genai.Client,
    model_name: str,
    contents: Any,
    config: Any,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Any:
    """
    Executes Gemini generate_content with tenacity exponential backoff and automatic fallback
    across models when encountering 503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, 404 NOT_FOUND, or temporary spikes.
    """
    candidates: List[str] = []

    clean_model = (model_name or "").strip()
    # Strip fake/non-existent model aliases to avoid wasting a guaranteed 404 round-trip
    _NONEXISTENT_ALIASES = {"auto", "auto_detect", "default", "gemini-3.5-flash", "gemini-3.6-flash",
                            "gemini-3.5-pro", "gemini-3.6-pro", "gemini-flash-latest", "gemini-pro-latest",
                            "gemini-2.0-flash"}
    if clean_model and clean_model.lower() not in _NONEXISTENT_ALIASES:
        candidates.append(clean_model)
        if clean_model.lower() == "gemini-3-flash":
            if "gemini-3-flash-preview" not in candidates:
                candidates.append("gemini-3-flash-preview")
        elif clean_model.lower() == "gemini-3-flash-preview":
            if "gemini-3-flash" not in candidates:
                candidates.append("gemini-3-flash")

    # Real, production-available Gemini models ordered by speed preference
    reliable_fallbacks = [
        "gemini-2.5-flash",       # Primary: fastest, cheapest, excellent quality
        "gemini-2.5-flash-lite",  # Ultra-fast lightweight option
        "gemini-2.0-flash-lite",  # Fast lightweight fallback
        "gemini-1.5-flash",       # Stable proven fallback
        "gemini-2.5-pro",         # Pro quality fallback
        "gemini-1.5-pro",         # Proven stable pro fallback
    ]
    for alt in reliable_fallbacks:
        if alt not in candidates:
            candidates.append(alt)

    # Only query dynamic model list if cache is warm (already populated) — never block on cold call
    discovered = get_available_gemini_models(client) if _cached_gemini_models else []
    if discovered:
        for m in discovered:
            if "flash" in m and m not in candidates:
                candidates.append(m)
        for m in discovered:
            if m not in candidates:
                candidates.append(m)

    if not candidates:
        candidates = ["gemini-2.5-flash", "gemini-1.5-flash"]

    last_err = None
    for idx, candidate in enumerate(candidates):
        try:
            logger.info(f"Invoking Gemini generate_content with candidate model: {candidate}...")
            response = execute_model_call_with_retry(
                client=client,
                model_name=candidate,
                contents=contents,
                config=config,
                max_retries=2,   # fail fast → fall to next model sooner
                min_wait=0.5,
                max_wait=4.0,
            )
            try:
                setattr(response, "_used_model", candidate)
            except Exception:
                pass
            return response
        except Exception as e:
            err_str = str(e)
            last_err = e
            is_switchable = (
                is_transient_gemini_error(e) or
                "404" in err_str or
                "not_found" in err_str.lower() or
                "unknown model" in err_str.lower() or
                "503" in err_str or
                "overloaded" in err_str.lower()
            )
            if is_switchable and idx < len(candidates) - 1:
                next_cand = candidates[idx + 1]
                logger.warning(
                    f"Model '{candidate}' unavailable after retries ({err_str[:120]}). "
                    f"Auto-switching to fallback candidate '{next_cand}'..."
                )
                if progress_callback:
                    progress_callback(f"Model {candidate} busy/unavailable. Falling back to {next_cand}...")
                continue
            else:
                logger.error(f"Error calling Gemini with model '{candidate}' (all fallbacks exhausted): {e}")
                raise e

    if last_err:
        raise last_err


def translate_segments_to_khmer(
    segments: List[Dict],
    api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    progress_callback: Optional[Callable[[str], None]] = None,
    provider: Optional[str] = None,
    project_id: Optional[str] = None,
    style: Optional[str] = "natural",
) -> List[Dict]:
    """
    Translates a list of transcript segments into natural Khmer using TranslationService.
    Supports Multi-Provider Engine (Gemini, OpenAI, Google Cloud, Local Model) with automatic fallback.
    """
    if not segments:
        return []

    try:
        from .translation import get_translation_service
        service = get_translation_service()

        def prog_adapter(pct_or_msg: Any, maybe_msg: Optional[str] = None):
            if progress_callback:
                if isinstance(pct_or_msg, str):
                    progress_callback(pct_or_msg)
                elif maybe_msg:
                    progress_callback(maybe_msg)

        res = service.translate_subtitles_pipeline(
            segments_raw=segments,
            project_id=project_id,
            provider=provider or "gemini",
            model=model_name,
            options={"api_key": api_key, "style": style or "natural"} if api_key else {"style": style or "natural"},
            progress_callback=prog_adapter,
        )

        if res.success and res.segments:
            return [s.to_dict() for s in res.segments]

    except Exception as e:
        logger.error(f"Multi-provider translation service error, falling back to direct Gemini: {e}")

    # Direct Gemini fallback if service had unexpected error
    try:
        client = get_gemini_client(api_key)
        if progress_callback:
            progress_callback(f"Translating {len(segments)} segments to Khmer via Gemini ({model_name})...")

        payload = []
        for s in segments:
            start = round(float(s.get("start", 0.0)), 2)
            end = round(float(s.get("end", 0.0)), 2)
            dur = max(0.0, end - start)
            payload.append({
                "id": s.get("id"),
                "start": start,
                "end": end,
                "text": s.get("text", "").strip(),
                "syllable_budget": max(3, int(dur * 3.2)),
            })

        prompt = f"Please translate and adapt these dialogue segments into natural spoken Khmer for voice dubbing:\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

        from .translation.base import get_style_prompt
        style_prompt_text = get_style_prompt(style)
        fallback_system_instruction = f"{KHMER_DUBBING_SYSTEM_INSTRUCTION}\n\n{style_prompt_text}"

        response = generate_content_with_retry_and_fallback(
            client=client,
            model_name=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=fallback_system_instruction,
                temperature=0.3,
                response_mime_type="application/json"
            ),
            progress_callback=progress_callback
        )

        response_text = response.text.strip()
        translated_data = extract_and_parse_json(response_text)

        from .tts_engine import extract_emotional_tags

        trans_map = {}
        for item in translated_data:
            if "id" in item:
                raw_text = item.get("khmer_text", "")
                clean_text, tag_emo, tag_pace, _, _ = extract_emotional_tags(raw_text)
                trans_map[item["id"]] = {
                    "khmer_text": clean_text or raw_text,
                    "emotion": tag_emo or item.get("emotion", "neutral"),
                    "pacing": tag_pace or item.get("pacing", "normal"),
                }

        updated_segments = []
        for s in segments:
            s_copy = dict(s)
            seg_id = s_copy.get("id")
            if seg_id in trans_map:
                s_copy["khmer_text"] = trans_map[seg_id]["khmer_text"] or s_copy.get("text", "")
                if trans_map[seg_id].get("emotion"):
                    s_copy["emotion"] = trans_map[seg_id]["emotion"]
                if trans_map[seg_id].get("pacing"):
                    s_copy["pacing"] = trans_map[seg_id]["pacing"]
            else:
                s_copy["khmer_text"] = s_copy.get("khmer_text", "") or s_copy.get("text", "")
            updated_segments.append(s_copy)

        return updated_segments

    except Exception as e:
        logger.error(f"Direct Gemini translation error: {e}")
        updated_segments = []
        for s in segments:
            s_copy = dict(s)
            if not s_copy.get("khmer_text"):
                s_copy["khmer_text"] = s_copy.get("text", "")
            updated_segments.append(s_copy)
        return updated_segments


def translate_single_segment(
    text: str,
    duration: float,
    api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    provider: Optional[str] = None,
    tone: str = "neutral",
    style: Optional[str] = "natural",
) -> str:
    """Translates a single segment text into spoken Khmer via TranslationService with fallback."""
    effective_style = style or ("viral_shorts" if tone in ("viral_shorts", "tiktok", "shorts") else "natural")
    try:
        from .translation import get_translation_service
        service = get_translation_service()
        res = service.regenerate_segment(
            text=text,
            duration=duration,
            provider_name=provider or "gemini",
            tone=tone,
            style=effective_style,
        )
        if res.get("success") and res.get("translation"):
            return res["translation"]
    except Exception as e:
        logger.warning(f"TranslationService single segment regeneration failed: {e}")

    # Fallback to direct call
    client = get_gemini_client(api_key)
    prompt = (
        f"Translate this single dialogue line into spoken natural Khmer for dubbing.\n"
        f"Target speaking duration is approx {duration:.1f} seconds.\n"
        f"Original: \"{text}\"\n"
        f"Output only the translated Khmer text, with no quotes or explanations."
    )

    from .translation.base import get_style_prompt
    style_inst = get_style_prompt(effective_style)
    single_sys_instruction = (
        f"You are an award-winning Cambodian cinema dubbing director and master translator.\n"
        f"Output natural spoken Khmer dialogue that feels like a real human being living inside the scene.\n\n"
        f"{style_inst}"
    )

    response = generate_content_with_retry_and_fallback(
        client=client,
        model_name=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=single_sys_instruction,
            temperature=0.3
        )
    )
    return response.text.strip()

