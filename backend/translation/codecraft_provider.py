"""
CodeCraft API Translation Provider.
Calls CodeCraft OpenAI-compatible API gateway (https://codecraftapi.com/v1) for natural Khmer dialogue adaptation.
Provides access to frontier models including Claude 3.5 Sonnet, DeepSeek, and GPT-4o.
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

logger = logging.getLogger("codecraft_provider")

DEFAULT_CODECRAFT_BASE_URL = "https://codecraftapi.com/v1"

CODECRAFT_DEFAULT_MODELS = [
    "gemini-3-flash",
    "gemini-3.7-flash",
    "claude-3-5-sonnet-20241022",
    "claude-3-7-sonnet",
    "claude-3-5-haiku-20241022",
    "deepseek-chat",
    "deepseek-reasoner",
    "gpt-4o",
    "gpt-4o-mini",
    "qwen-2.5-coder-32b-instruct",
]

CODECRAFT_SYSTEM_PROMPT = """
You are an award-winning Cambodian cinema dubbing director and master audiovisual translator specializing in natural, authentic spoken Khmer (ភាសាខ្មែរ) dialogue adaptation for voice dubbing.

Your mission is to adapt spoken dialogue from the video transcript into natural, spoken cinema Khmer dialogue:
1. Speakability & Natural Spoken Phrasing:
   - Must sound like natural spoken Khmer in modern Cambodian media — avoid robotic or bookish translation.
   - Use colloquial conversational negatives (អត់ / មិន e.g. "អត់ដឹងទេ", "ធ្វើមិនកើតទេ"), conversational questions ("ម៉េចចឹង?", "ទៅណា?", "មែនអត់?"), and natural particles (ណា៎, ណាស់, ហ្នឹងហើយ, អីចឹង, ឯង, ខ្ញុំ).
2. Dubbing Timing & Syllable Economy:
   - Respect speaking duration and syllable budget. Keep sentences punchy and concise so dubbed speech matches video timestamps naturally.
3. Tone & Character Emotion:
   - Identify scene tone: neutral, whisper, angry, sad, excited, terrified, or romantic.
4. Strict JSON Array Output:
   - Return ONLY a valid JSON array of objects with the exact schema:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 3.5,
    "khmer_text": "អត្ថបទភាសាខ្មែរដែលត្រូវនិយាយ",
    "tone": "neutral"
  }
]
Do not include markdown codeblocks or commentary. Output ONLY the raw JSON array.
"""


class CodeCraftProvider(TranslationProviderInterface):
    """CodeCraft API gateway translation provider (OpenAI-compatible)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key if api_key is not None else os.environ.get("CODECRAFT_API_KEY", "")
        self._base_url = (base_url or os.environ.get("CODECRAFT_BASE_URL", DEFAULT_CODECRAFT_BASE_URL)).rstrip("/")

    def get_name(self) -> str:
        return "codecraft"

    def get_display_name(self) -> str:
        return "CodeCraft API"

    def get_description(self) -> str:
        return "High-performance API gateway with Claude 3.5/3.7 Sonnet, DeepSeek V3, and GPT-4o."

    def get_supported_models(self) -> List[str]:
        return CODECRAFT_DEFAULT_MODELS

    def get_default_model(self) -> str:
        return "claude-3-5-sonnet-20241022"

    def _get_key(self, creds: Optional[Dict[str, Any]] = None) -> str:
        if creds is not None:
            if "codecraft_api_key" in creds:
                return creds["codecraft_api_key"]
            if "api_key" in creds:
                return creds["api_key"]
        if self._api_key is not None:
            return self._api_key
        return os.environ.get("CODECRAFT_API_KEY", "")

    def _get_base_url(self, creds: Optional[Dict[str, Any]] = None) -> str:
        if creds:
            if creds.get("codecraft_base_url"):
                return creds["codecraft_base_url"].rstrip("/")
            if creds.get("base_url"):
                return creds["base_url"].rstrip("/")
            if creds.get("endpoint"):
                return creds["endpoint"].rstrip("/")
        return self._base_url or os.environ.get("CODECRAFT_BASE_URL", DEFAULT_CODECRAFT_BASE_URL).rstrip("/")

    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = self._get_key(credentials)
        base_url = self._get_base_url(credentials)

        if not key:
            return {
                "success": False,
                "message": "CodeCraft API Key is not configured (starts with cc_)",
                "latency_ms": 0,
                "models": self.get_supported_models(),
            }

        start_time = time.time()
        models_url = f"{base_url}/models"
        req = urllib.request.Request(
            models_url,
            headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": "KhmerDub-AI/1.0",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                elapsed = int((time.time() - start_time) * 1000)
                if response.status == 200:
                    body = json.loads(response.read().decode("utf-8"))
                    discovered_models = []
                    if isinstance(body, dict) and "data" in body and isinstance(body["data"], list):
                        discovered_models = [m["id"] for m in body["data"] if isinstance(m, dict) and "id" in m]
                    elif isinstance(body, list):
                        discovered_models = [m.get("id", m) if isinstance(m, dict) else str(m) for m in body]

                    # Filter or merge with known models
                    active_models = discovered_models if discovered_models else self.get_supported_models()

                    return {
                        "success": True,
                        "message": f"Connected to CodeCraft API! ({elapsed}ms)",
                        "latency_ms": elapsed,
                        "models": active_models,
                        "model_tested": self.get_default_model(),
                    }
                else:
                    return {
                        "success": False,
                        "message": f"HTTP {response.status}",
                        "latency_ms": elapsed,
                        "models": self.get_supported_models(),
                    }
        except urllib.error.HTTPError as he:
            elapsed = int((time.time() - start_time) * 1000)
            err_body = he.read().decode("utf-8", errors="ignore")
            if he.code == 401:
                msg = "Invalid CodeCraft API Key. Please verify your token."
            elif he.code == 403:
                msg = "CodeCraft Access Forbidden / Insufficient permissions."
            elif he.code == 429:
                msg = "CodeCraft Rate Limit or Quota Exceeded."
            else:
                msg = f"CodeCraft Error {he.code}: {err_body[:120]}"
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
                "message": f"Connection error: {str(ex)[:120]}",
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }

    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        # 1. Standard json.loads
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "segments" in data and isinstance(data["segments"], list):
                    return data["segments"]
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
        except Exception:
            pass

        # 2. Extract first JSON array from text
        match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
        if match:
            try:
                arr = json.loads(match.group(0))
                if isinstance(arr, list):
                    return arr
            except Exception:
                pass

        # 3. Regex fallback item extraction
        items = []
        pattern = r'\{\s*"id"\s*:\s*(\d+).*?"khmer_text"\s*:\s*"((?:\\.|[^"\\])*)"'
        for m in re.finditer(pattern, cleaned, re.DOTALL):
            try:
                seg_id = int(m.group(1))
                val = m.group(2).replace('\\"', '"').replace('\\n', '\n')
                items.append({"id": seg_id, "khmer_text": val})
            except Exception:
                pass

        if items:
            return items

        raise ValueError(f"Could not parse valid translation JSON: {cleaned[:160]}")

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
                provider="codecraft",
                model=self.get_default_model(),
                source_language=source_language,
                target_language=target_language,
                segments=[],
            )

        start_time = time.time()
        opts = options or {}
        model = opts.get("model") or opts.get("model_name") or self.get_default_model()
        key = opts.get("api_key") or self._get_key(opts.get("credentials"))
        base_url = self._get_base_url(opts.get("credentials"))

        if not key:
            err = TranslationError(
                code=ErrorCode.INVALID_API_KEY,
                message="CodeCraft API key is missing. Please set CODECRAFT_API_KEY.",
                retryable=False,
                provider="codecraft",
            )
            return TranslationResult(
                success=False,
                provider="codecraft",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=err,
            )

        if progress_callback:
            progress_callback(f"Translating {len(segments)} segments via CodeCraft ({model})...")

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

        style_instruction = get_style_prompt(opts.get("style"))
        glossary_instruction = opts.get("glossary_instruction", "")

        system_prompt = (
            CODECRAFT_SYSTEM_PROMPT
            + f"\nSource Language: {source_language}\nTarget Language: {target_language}\n"
            + f"{style_instruction}\n"
            + glossary_instruction
        )

        user_content = (
            f"Please translate and adapt these dialogue segments into natural spoken Khmer for voice dubbing:\n\n"
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

        # Response format json object if model is OpenAI GPT based
        if "gpt-" in model.lower():
            request_body["response_format"] = {"type": "json_object"}
            request_body["messages"][0]["content"] += (
                '\nIMPORTANT: Return a JSON object with key "segments": [{"id": ..., "khmer_text": ..., "tone": ...}]'
            )

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "KhmerDub-AI/1.0",
        }

        endpoint_url = f"{base_url}/chat/completions"
        req = urllib.request.Request(
            endpoint_url,
            data=json.dumps(request_body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=75) as resp:
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
                    seg_copy.provider = "codecraft"
                    updated.append(seg_copy)

                duration_ms = int((time.time() - start_time) * 1000)
                return TranslationResult(
                    success=True,
                    provider="codecraft",
                    model=model,
                    source_language=source_language,
                    target_language=target_language,
                    segments=updated,
                    duration_ms=duration_ms,
                )

        except urllib.error.HTTPError as he:
            duration_ms = int((time.time() - start_time) * 1000)
            err_text = he.read().decode("utf-8", errors="ignore")
            logger.error("CodeCraft HTTPError %s: %s", he.code, err_text)
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
                provider="codecraft",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=code,
                    message=f"CodeCraft API error {he.code}: {err_text[:180]}",
                    retryable=retryable,
                    provider="codecraft",
                ),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("CodeCraft unexpected error: %s", e)
            return TranslationResult(
                success=False,
                provider="codecraft",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=ErrorCode.TIMEOUT if "timeout" in str(e).lower() else ErrorCode.UNKNOWN_ERROR,
                    message=str(e),
                    retryable=True,
                    provider="codecraft",
                ),
                duration_ms=duration_ms,
            )
