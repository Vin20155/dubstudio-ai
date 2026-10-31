"""
Batch Translation Manager for Multi-Project Concurrent/Queue Translation.

Handles:
- Worker Pool with configurable concurrency (default: 2) to prevent API rate-limit violations
- Project-level queueing, progress tracking, and persistence
- Rate limit backoff & error recovery
- Disk persistence for batch status in `PROCESSED_DIR / '_batches'`
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import PROCESSED_DIR
from .service import get_translation_service

logger = logging.getLogger("batch_translation_manager")


class BatchTranslationManager:
    _BATCHES_DIR = PROCESSED_DIR / "_batches"

    def __init__(self):
        self._BATCHES_DIR.mkdir(parents=True, exist_ok=True)
        self._batches: Dict[str, Dict[str, Any]] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._cancelled_batches: set = set()
        self._active_batch_id: Optional[str] = None
        self._load_cached_batches()

    def _path(self, batch_id: str) -> Path:
        return self._BATCHES_DIR / f"{batch_id}.json"

    def _save_batch(self, batch_id: str):
        try:
            data = self._batches.get(batch_id)
            if data:
                with open(self._path(batch_id), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Failed to persist batch {batch_id}: {e}")

    def _load_cached_batches(self):
        if not self._BATCHES_DIR.exists():
            return
        for p in self._BATCHES_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    b = json.load(f)
                    bid = b.get("batch_id")
                    if bid:
                        self._batches[bid] = b
                        if b.get("status") in ("running", "pending"):
                            # If app restarted while batch was running, mark it interrupted
                            b["status"] = "interrupted"
                            self._save_batch(bid)
            except Exception:
                pass

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        if batch_id in self._batches:
            return self._batches[batch_id]
        p = self._path(batch_id)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    b = json.load(f)
                    self._batches[batch_id] = b
                    return b
            except Exception:
                pass
        return None

    def get_active_batch(self) -> Optional[Dict[str, Any]]:
        if self._active_batch_id and self._active_batch_id in self._batches:
            b = self._batches[self._active_batch_id]
            if b.get("status") in ("running", "pending"):
                return b
        # Fallback to most recent batch if any
        if self._batches:
            sorted_batches = sorted(
                self._batches.values(),
                key=lambda x: x.get("created_at", 0),
                reverse=True,
            )
            return sorted_batches[0]
        return None

    def create_batch(
        self,
        project_ids: List[str],
        sessions_store: Any,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        source_language: str = "en",
        target_language: str = "km",
        style: str = "natural",
        options: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        concurrency: int = 2,
    ) -> Dict[str, Any]:
        """Initialize a new batch job."""
        batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        opts = dict(options or {})
        concurrency = max(1, min(concurrency, 4))  # Bound between 1 and 4

        projects_dict: Dict[str, Dict[str, Any]] = {}
        for pid in project_ids:
            session = sessions_store.get(pid, {})
            segs = session.get("segments") or []
            filename = session.get("original_filename") or f"{pid}.mp4"
            dur = (session.get("media_info") or {}).get("duration", 0.0)

            projects_dict[pid] = {
                "project_id": pid,
                "name": filename,
                "duration": round(float(dur), 2),
                "total_segments": len(segs),
                "completed_segments": 0,
                "current_segment_idx": 0,
                "status": "queued",  # queued, translating, completed, failed, skipped
                "progress": 0,
                "status_message": "Waiting in queue...",
                "error": None,
                "started_at": None,
                "finished_at": None,
            }

        batch_data = {
            "batch_id": batch_id,
            "status": "pending",  # pending, running, completed, cancelled, partial_error, failed
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "provider": provider or "gemini",
            "model": model,
            "source_language": source_language,
            "target_language": target_language,
            "style": style,
            "concurrency": concurrency,
            "options": opts,
            "api_key": api_key,
            "credentials": credentials,
            "total_projects": len(project_ids),
            "completed_projects": 0,
            "failed_projects": 0,
            "overall_progress": 0,
            "projects": projects_dict,
        }

        self._batches[batch_id] = batch_data
        self._active_batch_id = batch_id
        self._save_batch(batch_id)
        return batch_data

    def start_batch_execution(self, batch_id: str, sessions_store: Any):
        """Launches the async worker pipeline for the batch."""
        if batch_id in self._running_tasks and not self._running_tasks[batch_id].done():
            logger.info(f"Batch {batch_id} is already running.")
            return

        task = asyncio.create_task(self._run_batch_worker(batch_id, sessions_store))
        self._running_tasks[batch_id] = task

    async def _run_batch_worker(self, batch_id: str, sessions_store: Any):
        batch = self.get_batch(batch_id)
        if not batch:
            return

        batch["status"] = "running"
        batch["started_at"] = time.time()
        self._save_batch(batch_id)

        concurrency = batch.get("concurrency", 2)
        semaphore = asyncio.Semaphore(concurrency)
        service = get_translation_service()

        async def _process_single_project(pid: str):
            if batch_id in self._cancelled_batches:
                p_item = batch["projects"].get(pid)
                if p_item and p_item["status"] == "queued":
                    p_item["status"] = "cancelled"
                    p_item["status_message"] = "Cancelled by user"
                return

            async with semaphore:
                if batch_id in self._cancelled_batches:
                    return

                p_item = batch["projects"].get(pid)
                if not p_item or p_item.get("status") in ("completed", "cancelled"):
                    return

                p_item["status"] = "translating"
                p_item["started_at"] = time.time()
                p_item["status_message"] = f"Starting translation via {batch.get('provider', 'Gemini')}..."
                p_item["progress"] = 5
                self._update_overall_progress(batch)
                self._save_batch(batch_id)

                session = sessions_store.get(pid)
                if not session:
                    p_item["status"] = "failed"
                    p_item["error"] = "Project session not found on disk"
                    p_item["status_message"] = "Project session missing"
                    p_item["finished_at"] = time.time()
                    batch["failed_projects"] += 1
                    self._update_overall_progress(batch)
                    self._save_batch(batch_id)
                    return

                segments = session.get("segments") or []
                if not segments:
                    p_item["status"] = "skipped"
                    p_item["progress"] = 100
                    p_item["status_message"] = "No subtitles to translate"
                    p_item["finished_at"] = time.time()
                    batch["completed_projects"] += 1
                    self._update_overall_progress(batch)
                    self._save_batch(batch_id)
                    return

                skip_already = batch.get("options", {}).get("skip_already_translated", False)
                if skip_already:
                    # Check if all segments are already translated
                    untranslated = [s for s in segments if not (s.get("khmer_text") and str(s.get("khmer_text")).strip())]
                    if not untranslated:
                        p_item["status"] = "completed"
                        p_item["progress"] = 100
                        p_item["completed_segments"] = len(segments)
                        p_item["status_message"] = "Already translated"
                        p_item["finished_at"] = time.time()
                        batch["completed_projects"] += 1
                        self._update_overall_progress(batch)
                        self._save_batch(batch_id)
                        return

                req_options = {**(batch.get("options") or {})}
                req_options["style"] = batch.get("style", "natural")
                if batch.get("api_key"):
                    req_options["api_key"] = batch["api_key"]
                if batch.get("credentials"):
                    req_options["credentials"] = batch["credentials"]

                job_id = f"batch_{batch_id}_{pid}"

                def _progress_cb(pct: int, msg: str):
                    p_item["progress"] = max(5, min(pct, 98))
                    p_item["status_message"] = msg
                    # Attempt to extract segment numbers if msg contains e.g. "Translating batch 1/3 (segments 1-35)..."
                    self._update_overall_progress(batch)

                # Execute translation in thread with retry for 429 Rate Limits
                max_retries = 3
                retry_delay = 5.0
                last_error = None
                translated_result = None

                for attempt in range(max_retries):
                    if batch_id in self._cancelled_batches:
                        p_item["status"] = "cancelled"
                        p_item["status_message"] = "Cancelled"
                        return

                    try:
                        res = await asyncio.to_thread(
                            service.translate_subtitles_pipeline,
                            segments_raw=segments,
                            project_id=pid,
                            provider=batch.get("provider"),
                            model=batch.get("model"),
                            source_language=batch.get("source_language", "en"),
                            target_language=batch.get("target_language", "km"),
                            options=req_options,
                            job_id=job_id,
                            progress_callback=_progress_cb,
                        )

                        if res.success:
                            translated_result = res
                            break
                        else:
                            err_msg = res.error.message if res.error else "Translation failed"
                            last_error = err_msg
                            # Check if it's a rate limit error
                            if "429" in err_msg or "quota" in err_msg.lower() or "resourceexhausted" in err_msg.lower():
                                p_item["status_message"] = f"Rate limit encountered. Retrying in {int(retry_delay)}s (Attempt {attempt + 1}/{max_retries})..."
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                break
                    except Exception as exc:
                        last_error = str(exc)
                        if "429" in last_error or "quota" in last_error.lower():
                            p_item["status_message"] = f"Rate limit encountered. Retrying in {int(retry_delay)}s..."
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            break

                p_item["finished_at"] = time.time()

                if translated_result and translated_result.success:
                    # Update session data and write to disk
                    new_segments = [s.to_dict() for s in translated_result.segments]
                    session["segments"] = new_segments
                    sessions_store[pid] = session

                    p_item["status"] = "completed"
                    p_item["progress"] = 100
                    p_item["completed_segments"] = len(new_segments)
                    p_item["status_message"] = f"Completed ({len(new_segments)} segments)"
                    batch["completed_projects"] += 1
                else:
                    p_item["status"] = "failed"
                    p_item["error"] = last_error or "Translation failed"
                    p_item["status_message"] = f"Failed: {p_item['error'][:60]}"
                    batch["failed_projects"] += 1

                self._update_overall_progress(batch)
                self._save_batch(batch_id)

        try:
            tasks = [_process_single_project(pid) for pid in batch["projects"].keys()]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Batch {batch_id} execution error: {e}", exc_info=True)

        batch["finished_at"] = time.time()
        if batch_id in self._cancelled_batches:
            batch["status"] = "cancelled"
        elif batch["failed_projects"] == 0:
            batch["status"] = "completed"
        elif batch["completed_projects"] > 0:
            batch["status"] = "partial_error"
        else:
            batch["status"] = "failed"

        self._update_overall_progress(batch)
        self._save_batch(batch_id)
        logger.info(f"Batch {batch_id} finished with status {batch['status']}.")

    def _update_overall_progress(self, batch: Dict[str, Any]):
        """Calculate overall batch percentage from projects."""
        projects = batch.get("projects", {})
        total = len(projects)
        if total == 0:
            batch["overall_progress"] = 100
            return

        total_progress = sum(p.get("progress", 0) for p in projects.values())
        batch["overall_progress"] = max(0, min(100, int(total_progress / total)))

    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch job."""
        if batch_id not in self._batches:
            return False

        self._cancelled_batches.add(batch_id)
        batch = self._batches[batch_id]
        batch["status"] = "cancelled"
        batch["finished_at"] = time.time()

        for pid, p_item in batch.get("projects", {}).items():
            if p_item.get("status") in ("queued", "translating"):
                p_item["status"] = "cancelled"
                p_item["status_message"] = "Cancelled"

        if batch_id in self._running_tasks:
            task = self._running_tasks[batch_id]
            if not task.done():
                task.cancel()

        self._save_batch(batch_id)
        return True

    def retry_failed(self, batch_id: str, sessions_store: Any) -> Optional[Dict[str, Any]]:
        """Retry only the failed projects in an existing batch."""
        batch = self.get_batch(batch_id)
        if not batch:
            return None

        failed_pids = [
            pid for pid, p in batch.get("projects", {}).items()
            if p.get("status") in ("failed", "cancelled", "interrupted")
        ]

        if not failed_pids:
            return batch

        # Reset failed projects to queued
        for pid in failed_pids:
            batch["projects"][pid]["status"] = "queued"
            batch["projects"][pid]["progress"] = 0
            batch["projects"][pid]["error"] = None
            batch["projects"][pid]["status_message"] = "Queued for retry..."

        batch["failed_projects"] = 0
        batch["status"] = "running"
        self._cancelled_batches.discard(batch_id)
        self._update_overall_progress(batch)
        self._save_batch(batch_id)

        self.start_batch_execution(batch_id, sessions_store)
        return batch


# Global Singleton
_batch_manager_instance: Optional[BatchTranslationManager] = None


def get_batch_manager() -> BatchTranslationManager:
    global _batch_manager_instance
    if _batch_manager_instance is None:
        _batch_manager_instance = BatchTranslationManager()
    return _batch_manager_instance
