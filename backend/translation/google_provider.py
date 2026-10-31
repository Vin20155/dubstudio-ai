"""
Google Cloud Translation Provider.
Uses Google Cloud Translation REST API (v2) for fast, professional neural machine translation.
"""

import html
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from .base import (
    ErrorCode,
    TranslationError,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
)

logger = logging.getLogger("google_provider")

GOOGLE_CLOUD_MODELS = [
    "nmt",
    "base",
]


class GoogleCloudProvider(TranslationProviderInterface):
    """Google Cloud Translation API v2 Provider."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")

    def get_name(self) -> str:
        return "google_cloud"

    def get_display_name(self) -> str:
        return "Google Cloud Translation"

    def get_description(self) -> str:
        return "Fast professional translation backed by Google Cloud Neural Translation."

    def get_supported_models(self) -> List[str]:
        return GOOGLE_CLOUD_MODELS

    def get_default_model(self) -> str:
        return "nmt"

    def _get_key(self, creds: Optional[Dict[str, Any]] = None) -> str:
        if creds and creds.get("api_key"):
            return creds["api_key"]
        if creds and creds.get("google_api_key"):
            return creds["google_api_key"]
        return self._api_key or os.environ.get("GOOGLE_CLOUD_API_KEY") or os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")

    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = self._get_key(credentials)
        if not key:
            return {
                "success": False,
                "message": "Google Cloud Translation API Key is not configured",
                "latency_ms": 0,
                "models": self.get_supported_models(),
            }

        start_time = time.time()
        url = f"https://translation.googleapis.com/language/translate/v2?key={urllib.parse.quote(key)}"
        payload = {
            "q": "Hello",
            "target": "km",
            "source": "en",
            "format": "text",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                translated = data["data"]["translations"][0]["translatedText"]
                elapsed = int((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "message": f"Connected to Google Cloud! Sample: '{translated}' ({elapsed}ms)",
                    "latency_ms": elapsed,
                    "models": self.get_supported_models(),
                }
        except urllib.error.HTTPError as he:
            elapsed = int((time.time() - start_time) * 1000)
            err_body = he.read().decode("utf-8", errors="ignore")
            if he.code in [400, 401, 403]:
                msg = f"Invalid API Key or API not enabled ({he.code})"
            else:
                msg = f"Google Cloud error {he.code}: {err_body[:100]}"
            return {
                "success": False,
                "message": msg,
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }
        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "message": f"Connection error: {str(e)[:100]}",
                "latency_ms": elapsed,
                "models": self.get_supported_models(),
            }

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
                provider="google_cloud",
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
                message="Google Cloud API key is missing. Set GOOGLE_TRANSLATE_API_KEY.",
                retryable=False,
                provider="google_cloud",
            )
            return TranslationResult(
                success=False,
                provider="google_cloud",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=err,
            )

        if progress_callback:
            progress_callback(f"Translating {len(segments)} segments via Google Cloud ({model})...")

        texts = [s.source_text for s in segments]
        url = f"https://translation.googleapis.com/language/translate/v2?key={urllib.parse.quote(key)}"

        payload = {
            "q": texts,
            "target": target_language,
            "source": source_language if source_language != "auto" else None,
            "format": "text",
            "model": model,
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                translations = data.get("data", {}).get("translations", [])

                updated: List[TranslationSegment] = []
                for i, seg in enumerate(segments):
                    seg_copy = TranslationSegment.from_dict(seg.to_dict())
                    if i < len(translations):
                        raw_text = translations[i].get("translatedText", "")
                        clean_text = html.unescape(raw_text).strip()
                        seg_copy.khmer_text = clean_text
                        seg_copy.translated_text = clean_text
                    else:
                        seg_copy.khmer_text = seg.source_text
                        seg_copy.translated_text = seg.source_text

                    seg_copy.provider = "google_cloud"
                    updated.append(seg_copy)

                duration_ms = int((time.time() - start_time) * 1000)
                return TranslationResult(
                    success=True,
                    provider="google_cloud",
                    model=model,
                    source_language=source_language,
                    target_language=target_language,
                    segments=updated,
                    duration_ms=duration_ms,
                )

        except urllib.error.HTTPError as he:
            duration_ms = int((time.time() - start_time) * 1000)
            err_text = he.read().decode("utf-8", errors="ignore")
            logger.error("Google Cloud HTTPError %s: %s", he.code, err_text)
            if he.code in [400, 401, 403]:
                code = ErrorCode.INVALID_API_KEY
                retryable = False
            elif he.code == 429:
                code = ErrorCode.RATE_LIMIT
                retryable = True
            else:
                code = ErrorCode.PROVIDER_UNAVAILABLE
                retryable = True

            return TranslationResult(
                success=False,
                provider="google_cloud",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=code,
                    message=f"Google Cloud Error ({he.code}): {err_text[:180]}",
                    retryable=retryable,
                    provider="google_cloud",
                ),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return TranslationResult(
                success=False,
                provider="google_cloud",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=ErrorCode.TIMEOUT if "timeout" in str(e).lower() else ErrorCode.UNKNOWN_ERROR,
                    message=str(e),
                    retryable=True,
                    provider="google_cloud",
                ),
                duration_ms=duration_ms,
            )
