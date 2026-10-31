"""
Custom Local Model Translation Provider.
Connects to an external or self-hosted local translation server (e.g. FastAPI / vLLM / Ollama wrapper).
"""

import json
import logging
import os
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
)

logger = logging.getLogger("local_provider")


class LocalModelProvider(TranslationProviderInterface):
    """Custom Local Model translation provider communicating via standard HTTP."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._endpoint_url = endpoint_url or os.environ.get("LOCAL_TRANSLATION_URL", "http://127.0.0.1:8001")
        self._model_name = model_name or os.environ.get("LOCAL_TRANSLATION_MODEL", "custom-khmer-model")

    def get_name(self) -> str:
        return "local_model"

    def get_display_name(self) -> str:
        return "Custom Local Model"

    def get_description(self) -> str:
        return "Run private translation on your own server or GPU cluster."

    def get_supported_models(self) -> List[str]:
        return [self._model_name, "nllb-200-distilled", "seamless-m4t", "custom-khmer-model"]

    def get_default_model(self) -> str:
        return self._model_name

    def _get_url(self, creds: Optional[Dict[str, Any]] = None) -> str:
        if creds and creds.get("endpoint_url"):
            return creds["endpoint_url"].rstrip("/")
        return self._endpoint_url.rstrip("/")

    def test_connection(self, credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base_url = self._get_url(credentials)
        start_time = time.time()

        # Try health endpoint first, fallback to POST /translate with dummy payload
        try:
            req = urllib.request.Request(f"{base_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                elapsed = int((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "message": f"Local translation server is online! ({elapsed}ms)",
                    "latency_ms": elapsed,
                    "models": self.get_supported_models(),
                }
        except Exception:
            pass

        # Try POST /translate ping
        try:
            ping_payload = {
                "source_language": "en",
                "target_language": "km",
                "segments": [{"id": 1, "start": 0.0, "end": 1.0, "text": "Hello"}],
            }
            req = urllib.request.Request(
                f"{base_url}/translate",
                data=json.dumps(ping_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                elapsed = int((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "message": f"Local model responding to /translate! ({elapsed}ms)",
                    "latency_ms": elapsed,
                    "models": self.get_supported_models(),
                }
        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "message": f"Cannot connect to {base_url} ({str(e)[:100]})",
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
                provider="local_model",
                model=self.get_default_model(),
                source_language=source_language,
                target_language=target_language,
                segments=[],
            )

        start_time = time.time()
        opts = options or {}
        model = opts.get("model") or opts.get("model_name") or self.get_default_model()
        base_url = self._get_url(opts.get("credentials"))

        if progress_callback:
            progress_callback(f"Translating {len(segments)} segments via Local Model at {base_url}...")

        payload = {
            "source_language": source_language,
            "target_language": target_language,
            "model": model,
            "options": opts,
            "segments": [
                {
                    "id": s.id,
                    "start": s.start,
                    "end": s.end,
                    "speaker": s.speaker,
                    "text": s.source_text,
                }
                for s in segments
            ],
        }

        url = f"{base_url}/translate"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                returned_segs = data.get("segments", [])
                trans_map = {}
                for it in returned_segs:
                    s_id = it.get("id")
                    t_val = it.get("translated_text") or it.get("khmer_text") or it.get("text")
                    trans_map[s_id] = (t_val, it.get("tone", "neutral"))

                updated: List[TranslationSegment] = []
                for s in segments:
                    seg_copy = TranslationSegment.from_dict(s.to_dict())
                    if s.id in trans_map:
                        t_val, tone = trans_map[s.id]
                        seg_copy.khmer_text = t_val
                        seg_copy.translated_text = t_val
                        seg_copy.tone = tone
                    else:
                        if not seg_copy.khmer_text:
                            seg_copy.khmer_text = seg_copy.source_text
                            seg_copy.translated_text = seg_copy.source_text
                    seg_copy.provider = "local_model"
                    updated.append(seg_copy)

                duration_ms = int((time.time() - start_time) * 1000)
                return TranslationResult(
                    success=True,
                    provider="local_model",
                    model=model,
                    source_language=source_language,
                    target_language=target_language,
                    segments=updated,
                    duration_ms=duration_ms,
                )

        except urllib.error.HTTPError as he:
            duration_ms = int((time.time() - start_time) * 1000)
            return TranslationResult(
                success=False,
                provider="local_model",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Local translation server HTTP error {he.code}",
                    retryable=True,
                    provider="local_model",
                ),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return TranslationResult(
                success=False,
                provider="local_model",
                model=model,
                source_language=source_language,
                target_language=target_language,
                segments=segments,
                error=TranslationError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Local server connection failed: {str(e)}",
                    retryable=True,
                    provider="local_model",
                ),
                duration_ms=duration_ms,
            )
