"""
Master Translation Service for Multi-Provider Video Dubbing.
Orchestrates providers, context-aware batching, translation memory, glossaries,
automatic fallback routing, retry with exponential backoff, and job progress tracking.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import (
    ErrorCode,
    TranslationError,
    TranslationOption,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
)
from .db import (
    create_translation_job,
    get_translation_job,
    log_translation_run,
    resolve_effective_settings,
    update_translation_job,
)
from .gemini_provider import GeminiProvider
from .google_provider import GoogleCloudProvider
from .local_provider import LocalModelProvider
from .codecraft_provider import CodeCraftProvider
from .memory import TranslationMemoryManager
from .openai_provider import OpenAIProvider

logger = logging.getLogger("translation_service")


class TranslationService:
    """
    Central orchestration service for all subtitle translation operations.
    The rest of the application interacts strictly with this service.
    """

    def __init__(self):
        self._providers: Dict[str, TranslationProviderInterface] = {}
        self._cancelled_jobs: set = set()

        # Register standard providers
        self.register_provider(GeminiProvider())
        self.register_provider(OpenAIProvider())
        self.register_provider(GoogleCloudProvider())
        self.register_provider(LocalModelProvider())
        self.register_provider(CodeCraftProvider())

    def register_provider(self, provider: TranslationProviderInterface):
        self._providers[provider.get_name()] = provider
        logger.info("Registered translation provider: %s (%s)", provider.get_name(), provider.get_display_name())

    def get_provider(self, name: Optional[str]) -> TranslationProviderInterface:
        provider_name = (name or "gemini").lower().strip()
        if provider_name in self._providers:
            return self._providers[provider_name]
        logger.warning("Provider '%s' not recognized, falling back to Gemini", provider_name)
        return self._providers["gemini"]

    def list_providers(self) -> List[Dict[str, Any]]:
        """Returns catalog of all registered providers with metadata and supported models."""
        result = []
        for name, provider in self._providers.items():
            result.append({
                "id": name,
                "name": provider.get_display_name(),
                "description": provider.get_description(),
                "default_model": provider.get_default_model(),
                "models": provider.get_supported_models(),
            })
        return result

    def test_provider_connection(
        self,
        provider_name: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Tests connectivity for a specific provider."""
        provider = self.get_provider(provider_name)
        return provider.test_connection(credentials)

    def cancel_job(self, job_id: str):
        """Marks a translation job as cancelled."""
        self._cancelled_jobs.add(job_id)
        update_translation_job(job_id, status="cancelled", error_message="Cancelled by user")

    def is_job_cancelled(self, job_id: Optional[str]) -> bool:
        return bool(job_id and job_id in self._cancelled_jobs)

    def _build_context_prompt(self, prev_segments: List[TranslationSegment], next_segments: List[TranslationSegment]) -> str:
        """Constructs dialogue context window for surrounding scenes."""
        parts = []
        if prev_segments:
            prev_lines = [f'- "{s.source_text}"' for s in prev_segments[-3:] if s.source_text]
            if prev_lines:
                parts.append("Previous conversation dialogue:\n" + "\n".join(prev_lines))

        if next_segments:
            next_lines = [f'- "{s.source_text}"' for s in next_segments[:3] if s.source_text]
            if next_lines:
                parts.append("Upcoming conversation dialogue:\n" + "\n".join(next_lines))

        if parts:
            return "\n\nScene Context for natural continuity:\n" + "\n\n".join(parts) + "\n"
        return ""

    def _execute_provider_with_retry(
        self,
        provider: TranslationProviderInterface,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
        options: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
        max_retries: int = 2,
    ) -> TranslationResult:
        """Executes translation with exponential backoff on retriable errors."""
        last_result = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                delay = 1.0 * (2 ** (attempt - 1))
                msg = f"Rate limit or temporary error on {provider.get_name()}. Retrying in {delay:.1f}s (Attempt {attempt + 1}/{max_retries + 1})..."
                logger.warning(msg)
                if progress_callback:
                    progress_callback(msg)
                time.sleep(delay)

            result = provider.translate(
                segments=segments,
                source_language=source_lang,
                target_language=target_lang,
                options=options,
                progress_callback=progress_callback,
            )

            if result.success:
                return result

            last_result = result
            if not result.error or not result.error.retryable:
                # Not retryable (e.g. invalid API key or bad request)
                break

        return last_result or TranslationResult(
            success=False,
            provider=provider.get_name(),
            model=options.get("model", ""),
            source_language=source_lang,
            target_language=target_lang,
            segments=segments,
            error=TranslationError(
                code=ErrorCode.UNKNOWN_ERROR,
                message="Translation failed after retries",
                provider=provider.get_name(),
            ),
        )

    def translate_batch(
        self,
        segments: List[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "km",
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        user_id: str = "default_user",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TranslationResult:
        """
        Translates a single batch of segments, handling TM lookup, glossary injection,
        primary execution, automatic fallback, and logging.
        """
        opts = options or {}
        provider = self.get_provider(provider_name)
        fallback_name = opts.get("fallback_provider", "openai")
        fallback_enabled = opts.get("enable_fallback", True)

        # 1. Check Translation Memory
        use_tm = opts.get("use_translation_memory", True)
        to_translate, cached_segs = TranslationMemoryManager.apply_translation_memory(
            segments=segments,
            source_lang=source_lang,
            target_lang=target_lang,
            enabled=use_tm,
        )

        if not to_translate:
            # Everything found in TM or locked!
            return TranslationResult(
                success=True,
                provider=provider.get_name(),
                model=model or provider.get_default_model(),
                source_language=source_lang,
                target_language=target_lang,
                segments=cached_segs,
                cached_count=len(cached_segs),
            )

        # 2. Prepare glossary instruction if enabled
        use_glossary = opts.get("use_glossary", True)
        glossary_instruction = (
            TranslationMemoryManager.build_glossary_prompt_instruction(project_id)
            if use_glossary
            else ""
        )

        batch_options = {
            **opts,
            "model": model or provider.get_default_model(),
            "glossary_instruction": glossary_instruction,
        }

        # 3. Call Primary Provider with Retry
        t0 = time.time()
        result = self._execute_provider_with_retry(
            provider=provider,
            segments=to_translate,
            source_lang=source_lang,
            target_lang=target_lang,
            options=batch_options,
            progress_callback=progress_callback,
        )

        # 4. If primary provider failed and fallback is enabled on retriable errors:
        used_fallback = False
        if not result.success and fallback_enabled and fallback_name and fallback_name != provider.get_name():
            fb_provider = self.get_provider(fallback_name)
            fb_msg = (
                f"Primary provider '{provider.get_name()}' unavailable ({result.error.code.value if result.error else 'Error'}). "
                f"Automatically switching to fallback provider '{fb_provider.get_name()}'..."
            )
            logger.warning(fb_msg)
            if progress_callback:
                progress_callback(fb_msg)

            fb_options = {
                **batch_options,
                "model": fb_provider.get_default_model(),
            }
            fb_result = self._execute_provider_with_retry(
                provider=fb_provider,
                segments=to_translate,
                source_lang=source_lang,
                target_lang=target_lang,
                options=fb_options,
                progress_callback=progress_callback,
            )
            if fb_result.success:
                result = fb_result
                used_fallback = True

        duration_ms = int((time.time() - t0) * 1000)

        # 5. Log translation attempt
        status_str = "completed" if result.success else "failed"
        err_code_str = result.error.code.value if result.error else None
        log_translation_run(
            provider=result.provider,
            model=result.model,
            status=status_str,
            duration_ms=duration_ms,
            segments_count=len(segments),
            source_language=source_lang,
            target_language=target_lang,
            error_code=err_code_str,
            project_id=project_id,
            user_id=user_id,
        )

        if not result.success:
            return result

        # 6. Post-process glossary terms & save to TM
        merged_map = {s.id: s for s in result.segments}
        for cs in cached_segs:
            merged_map[cs.id] = cs

        final_segments = []
        for orig in segments:
            seg = merged_map.get(orig.id, orig)
            if use_glossary and seg.khmer_text:
                seg.khmer_text = TranslationMemoryManager.apply_glossary_post_processing(seg.khmer_text, project_id)
                seg.translated_text = seg.khmer_text
            final_segments.append(seg)

        # Save translated segments to TM
        TranslationMemoryManager.save_to_memory(
            segments=result.segments,
            source_lang=source_lang,
            target_lang=target_lang,
            provider=result.provider,
            project_id=project_id,
            enabled=use_tm,
        )

        result.segments = final_segments
        result.cached_count = len(cached_segs)
        return result

    def translate_subtitles_pipeline(
        self,
        segments_raw: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        user_id: str = "default_user",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        batch_size: int = 35,
    ) -> TranslationResult:
        """
        Complete pipeline for large transcripts: splits into context-aware batches,
        updates job progress, allows cancellation, and normalizes output.
        """
        if not segments_raw:
            return TranslationResult(
                success=True,
                provider=provider or "gemini",
                model=model or "gemini-3.5-flash",
                source_language=source_language or "en",
                target_language=target_language or "km",
                segments=[],
            )

        # Resolve effective settings (Project -> User -> Default)
        effective = resolve_effective_settings(project_id, user_id)
        active_provider = provider or effective["provider"]
        active_model = model or effective["model"]
        source_lang = source_language or effective["source_language"]
        target_lang = target_language or effective["target_language"]
        effective_creds = effective.get("credentials") or {}
        merged_options = {
            **effective["options"],
            **(options or {}),
        }
        if "credentials" not in merged_options and effective_creds:
            merged_options["credentials"] = effective_creds
        if "api_key" not in merged_options:
            user_key = (
                merged_options.get("gemini_api_key")
                or effective_creds.get("gemini_api_key")
                or effective_creds.get("api_key")
                or os.environ.get("GEMINI_API_KEY")
            )
            if user_key:
                merged_options["api_key"] = user_key

        # Parse normalized TranslationSegments
        segments: List[TranslationSegment] = [TranslationSegment.from_dict(s) for s in segments_raw]
        total_segments = len(segments)

        # Initialize job in DB if job_id is supplied
        if job_id:
            self._cancelled_jobs.discard(job_id)
            create_translation_job(
                job_id=job_id,
                project_id=project_id,
                provider=active_provider,
                model=active_model,
                total_segments=total_segments,
                user_id=user_id,
            )

        def update_progress(pct: int, msg: str, seg_idx: Optional[int] = None, seg_text: Optional[str] = None):
            if progress_callback:
                progress_callback(pct, msg)
            if job_id:
                update_translation_job(
                    job_id=job_id,
                    progress=pct,
                    status_message=msg,
                    current_segment_idx=seg_idx,
                    current_segment_text=seg_text,
                )

        update_progress(5, f"Starting translation with {active_provider.title()} ({active_model})...")

        all_translated: List[TranslationSegment] = []
        num_batches = (total_segments + batch_size - 1) // batch_size

        batch_tasks = []
        for b_idx in range(num_batches):
            start_idx = b_idx * batch_size
            end_idx = min(start_idx + batch_size, total_segments)
            batch_segs = segments[start_idx:end_idx]

            # Context window
            prev_context = segments[max(0, start_idx - 3):start_idx]
            next_context = segments[end_idx:min(total_segments, end_idx + 3)]
            context_instruction = (
                self._build_context_prompt(prev_context, next_context)
                if merged_options.get("use_context", True)
                else ""
            )

            batch_opts = {
                **merged_options,
                "custom_instructions": context_instruction,
            }
            batch_tasks.append((b_idx, batch_segs, batch_opts, start_idx, end_idx))

        results_by_index: List[Optional[TranslationResult]] = [None] * num_batches
        first_error_result: Optional[TranslationResult] = None

        if num_batches == 1:
            b_idx, batch_segs, batch_opts, start_idx, end_idx = batch_tasks[0]
            first_seg_text = batch_segs[0].source_text[:80] if batch_segs else ""
            update_progress(
                20,
                f"Translating {total_segments} segment{'s' if total_segments > 1 else ''} via {active_provider.title()} ({active_model})...",
                seg_idx=1,
                seg_text=first_seg_text,
            )
            res = self.translate_batch(
                segments=batch_segs,
                source_lang=source_lang,
                target_lang=target_lang,
                provider_name=active_provider,
                model=active_model,
                options=batch_opts,
                project_id=project_id,
                user_id=user_id,
                progress_callback=lambda m: update_progress(50, m),
            )
            if not res.success:
                logger.error("Translation batch 0 failed: %s", res.error)
                if job_id:
                    update_translation_job(
                        job_id=job_id,
                        status="failed",
                        error_message=res.error.message if res.error else "Translation failed",
                        status_message="Translation failed.",
                    )
                return res
            results_by_index[0] = res
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            max_workers = min(4, num_batches)
            completed_batches = 0

            def _worker(task_info):
                idx, b_segs, b_opts, s_idx, e_idx = task_info
                if self.is_job_cancelled(job_id):
                    return idx, TranslationResult(
                        success=False,
                        provider=active_provider,
                        model=active_model,
                        source_language=source_lang,
                        target_language=target_lang,
                        segments=b_segs,
                        error=TranslationError(code=ErrorCode.UNKNOWN_ERROR, message="Translation cancelled by user"),
                    )
                b_res = self.translate_batch(
                    segments=b_segs,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider_name=active_provider,
                    model=active_model,
                    options=b_opts,
                    project_id=project_id,
                    user_id=user_id,
                )
                return idx, b_res

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_worker, t): t[0] for t in batch_tasks}
                for fut in as_completed(future_map):
                    idx, b_res = fut.result()
                    results_by_index[idx] = b_res
                    completed_batches += 1
                    _, b_segs_done, _, s_idx_done, e_idx_done = batch_tasks[idx]
                    pct = int(10 + (completed_batches / num_batches) * 85)
                    seg_range_msg = f"Segments {s_idx_done + 1}–{e_idx_done} done"
                    first_done_text = b_segs_done[0].source_text[:80] if b_segs_done else ""
                    update_progress(
                        pct,
                        f"Batch {completed_batches}/{num_batches} complete ({seg_range_msg}) via {active_provider.title()}...",
                        seg_idx=s_idx_done + 1,
                        seg_text=first_done_text,
                    )
                    if not b_res.success and not first_error_result:
                        first_error_result = b_res

            if first_error_result:
                logger.error("Parallel translation batch failed: %s", first_error_result.error)
                if job_id:
                    update_translation_job(
                        job_id=job_id,
                        status="failed",
                        error_message=first_error_result.error.message if first_error_result.error else "Batch failed",
                    )
                return first_error_result

        for res in results_by_index:
            if res and res.segments:
                all_translated.extend(res.segments)

        update_progress(100, f"Translation completed successfully! ({total_segments} segments)")
        if job_id:
            update_translation_job(
                job_id=job_id,
                status="completed",
                completed_segments=total_segments,
                progress=100,
                segments_data=[s.to_dict() for s in all_translated],
            )

        return TranslationResult(
            success=True,
            provider=active_provider,
            model=active_model,
            source_language=source_lang,
            target_language=target_lang,
            segments=all_translated,
        )

    def regenerate_segment(
        self,
        text: str,
        duration: float = 3.0,
        provider_name: Optional[str] = None,
        style: str = "natural",
        tone: str = "neutral",
        context: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Regenerates a single segment translation with fine-grained tone and style controls."""
        dummy_seg = TranslationSegment(
            id=1,
            start=0.0,
            end=duration,
            source_text=text,
            tone=tone,
        )

        res = self.translate_batch(
            segments=[dummy_seg],
            source_lang="en",
            target_lang="km",
            provider_name=provider_name or "gemini",
            options={
                "style": style,
                "use_translation_memory": False,  # Force new generation
                "custom_instructions": f"Dialogue Tone: {tone}. {context or ''}",
            },
            project_id=project_id,
        )

        if res.success and res.segments:
            return {
                "success": True,
                "translation": res.segments[0].khmer_text,
                "khmer_text": res.segments[0].khmer_text,
                "provider": res.provider,
                "tone": res.segments[0].tone,
            }

        return {
            "success": False,
            "error": res.error.to_dict() if res.error else {"message": "Regeneration failed"},
        }


# Global singleton instance
_translation_service_instance: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    global _translation_service_instance
    if _translation_service_instance is None:
        _translation_service_instance = TranslationService()
    return _translation_service_instance
