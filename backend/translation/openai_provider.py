"""
OpenAI Translation Provider.
Calls OpenAI Chat Completions API for natural Khmer dialogue adaptation with JSON response formatting.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from .base import (
    ErrorCode,
    TranslationError,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
    TranslationStyle,
    get_style_prompt,
)

logger = logging.getLogger("openai_provider")

OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]

OPENAI_SYSTEM_PROMPT = """
You are a master audiovisual translator and dubbing director specializing in natural spoken Khmer (ភាសាខ្មែរ) dialogue adaptation.

Your mission is to translate and adapt spoken dialogue from the source video transcript into natural, spoken Khmer suitable for AI voice dubbing:
1. Speakability & Natural Spoken Khmer: Output fluent, natural Cambodian phrasing suitable for speech dubbing. Avoid unnatural, literal word-for-word translation.
2. Timing & Syllable Economy: Dubbed audio must fit the allotted duration [start to end]. Keep sentences concise and punchy.
3. Tone & Character Emotion: Match conversational register (casual, dramatic, polite, sarcastic, humorous) according to scene context.
4. Strict JSON Output: Output a valid JSON array of objects with the exact schema:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 3.5,
    "khmer_text": "អត្ថបទភាសាខ្មែរដែលត្រូវនិយាយ",
    "tone": "neutral"
  }
]
Do not output markdown backticks or explanations. Output ONLY the raw JSON array.
"""


class OpenAIProvider(TranslationProviderInterface):
    """OpenAI GPT translation provider for natural dialogue dubbing."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def get_name(self) -> str:
        return "openai"

    def get_display_name(self) -> str:
        return "OpenAI"

    def get_description(self) -> str:
        return "Natural dialogue adaptation, tone preservation, and cinematic nuance."

    def get_supported_models(self) -> List[str]:
        return OPENAI_MODELS

    def get_default_model(self) -> str:
        return "gpt-4o-mini"

    def _get_key(self, creds: Optional[Dict[str, Any]] = None) -> str:
        if creds and creds.get("api_key"):
            return creds["api_key"]
        if creds and creds.get("openai_api_key"):
            return creds["openai_api_key"]
        return self._api_key or os.environ.get("OPENAI_API_KEY", "")

    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = self._get_key(credentials)
        if not key:
            return {
                "success": False,
                "message": "OpenAI API Key is not configured",
                "latency_ms": 0,
                "models": self.get_supported_models(),
            }

        start_time = time.time()
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": "KhmerDub-AI/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    elapsed = int((time.time() - start_time) * 1000)
                    return {
                        "success": True,
                        "message": f"Connected to OpenAI! (Latency: {elapsed}ms)",
                        "latency_ms": elapsed,
                        "models": self.get_supported_models(),
                    }
                else:
                    return {
                        "success": False,
                        "message": f"HTTP {response.status}",
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "models": self.get_supported_models(),
                    }
        except urllib.error.HTTPError as he:
            elapsed = int((time.time() - start_time) * 1000)
            err_body = he.read().decode("utf-8", errors="ignore")
            if he.code == 401:
                msg = "Invalid OpenAI API Key"
            elif he.code == 429:
                msg = "OpenAI Rate Limit or Quota Exceeded"
            else:
                msg = f"OpenAI Error {he.code}: {err_body[:100]}"
            return {
                "success": False,
                "message": msg,
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }
        except Exception as ex:
            elapsed = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "message": f"Connection error: {str(ex)[:100]}",
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }

    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "segments" in data:
                return data["segments"]
        except Exception:
            pass

        # Regex fallback
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

        raise ValueError(f"Could not parse valid translation JSON: {text[:160]}")

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
                provider="openai",
                model=self.get_default_model(),
                source_language=source_language,
                target_language=target_language,
                segments=[],
            )

        start_time = time.time()
        opts = options or {}
        model = opts.get("model") or opts.get("model_name") or self.get_default_model()
        key = opts.get("api_key") or self._get_key(opts.get("credentials"))

        if not key:
            err = TranslationError(
                code=ErrorCode.INVALID_API_KEY,
                message="OpenAI API key is missing. Please set OPENAI_API_KEY.",
                retryable=False,
                provider="openai",
            )
            return TranslationResult(
                success=False,
                provider="openai",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=err,
            )

        if progress_callback:
            progress_callback(f"Translating {len(segments)} segments via OpenAI ({model})...")

        payload = [
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "speaker": s.speaker,
                "text": s.source_text,
            }
            for s in segments
        ]

        style_instruction = get_style_prompt(opts.get("style"))
        glossary_instruction = opts.get("glossary_instruction", "")

        system_prompt = (
            OPENAI_SYSTEM_PROMPT
            + f"\nSource Language: {source_language}\nTarget Language: {target_language}\n"
            + f"{style_instruction}\n"
            + glossary_instruction
        )

        user_content = (
            f"Translate and adapt these subtitles into natural spoken Khmer:\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": float(opts.get("temperature", 0.3)),
        }

        # Response format json object if supported model
        if "gpt-4" in model:
            request_body["response_format"] = {"type": "json_object"}
            request_body["messages"][0]["content"] += (
                '\nIMPORTANT: Return a JSON object with key "segments": [{"id": ..., "khmer_text": ..., "tone": ...}]'
            )

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "KhmerDub-AI/1.0",
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                choice = res_data["choices"][0]
                content = choice["message"]["content"].strip()
                parsed = self._parse_response(content)

                trans_map = {item["id"]: item for item in parsed if "id" in item}
                updated: List[TranslationSegment] = []
                for s in segments:
                    seg_copy = TranslationSegment.from_dict(s.to_dict())
                    if s.id in trans_map:
                        item = trans_map[s.id]
                        text_val = item.get("khmer_text") or item.get("translated_text") or s.source_text
                        seg_copy.khmer_text = text_val
                        seg_copy.translated_text = text_val
                        seg_copy.tone = item.get("tone", s.tone or "neutral")
                    else:
                        if not seg_copy.khmer_text:
                            seg_copy.khmer_text = seg_copy.source_text
                            seg_copy.translated_text = seg_copy.source_text
                    seg_copy.provider = "openai"
                    updated.append(seg_copy)

                duration_ms = int((time.time() - start_time) * 1000)
                return TranslationResult(
                    success=True,
                    provider="openai",
                    model=model,
                    source_language=source_language,
                    target_language=target_language,
                    segments=updated,
                    duration_ms=duration_ms,
                )

        except urllib.error.HTTPError as he:
            duration_ms = int((time.time() - start_time) * 1000)
            err_text = he.read().decode("utf-8", errors="ignore")
            logger.error("OpenAI HTTPError %s: %s", he.code, err_text)
            if he.code == 401:
                code = ErrorCode.INVALID_API_KEY
                retryable = False
            elif he.code == 429:
                code = ErrorCode.RATE_LIMIT
                retryable = True
            elif he.code in [500, 502, 503, 504]:
                code = ErrorCode.PROVIDER_UNAVAILABLE
                retryable = True
            else:
                code = ErrorCode.INVALID_REQUEST
                retryable = False

            return TranslationResult(
                success=False,
                provider="openai",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=code,
                    message=f"OpenAI error {he.code}: {err_text[:180]}",
                    retryable=retryable,
                    provider="openai",
                ),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("OpenAI unexpected error: %s", e)
            return TranslationResult(
                success=False,
                provider="openai",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=ErrorCode.TIMEOUT if "timeout" in str(e).lower() else ErrorCode.UNKNOWN_ERROR,
                    message=str(e),
                    retryable=True,
                    provider="openai",
                ),
                duration_ms=duration_ms,
            )
