"""
Automated Test Suite for Multi-Provider Translation Engine.
Tests Provider Abstraction, Translation Memory, Glossary Enforcement,
Fallback Switching, Database Persistence, and FastAPI Endpoints.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.translation.base import (
    ErrorCode,
    TranslationError,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
    TranslationStyle,
)
from backend.translation.db import (
    add_glossary_term,
    delete_glossary_term,
    delete_translation_memory,
    get_admin_translation_stats,
    get_project_settings,
    get_user_ai_settings,
    list_glossary_terms,
    list_translation_memory,
    log_translation_run,
    lookup_translation_memory,
    resolve_effective_settings,
    save_project_settings,
    save_user_ai_settings,
    store_translation_memory,
)
from backend.translation.memory import TranslationMemoryManager
from backend.translation.service import TranslationService
from backend.main import app


class MockWorkingProvider(TranslationProviderInterface):
    def get_name(self) -> str:
        return "mock_working"

    def get_display_name(self) -> str:
        return "Mock Working Provider"

    def get_description(self) -> str:
        return "Test provider that succeeds"

    def get_supported_models(self):
        return ["mock-v1", "mock-v2"]

    def get_default_model(self) -> str:
        return "mock-v1"

    def translate(self, segments, source_language, target_language, options=None, progress_callback=None):
        out = []
        for s in segments:
            seg_copy = TranslationSegment.from_dict(s.to_dict())
            seg_copy.khmer_text = f"ប្រែ: {s.source_text}"
            seg_copy.translated_text = seg_copy.khmer_text
            out.append(seg_copy)
        return TranslationResult(
            success=True,
            provider="mock_working",
            model="mock-v1",
            source_language=source_language,
            target_language=target_language,
            segments=out,
        )

    def test_connection(self, credentials=None):
        return {"success": True, "provider": "mock_working", "latency_ms": 12, "model_tested": "mock-v1"}


class MockFailingProvider(TranslationProviderInterface):
    def get_name(self) -> str:
        return "mock_failing"

    def get_display_name(self) -> str:
        return "Mock Failing Provider"

    def get_description(self) -> str:
        return "Test provider that fails with 429 rate limit"

    def get_supported_models(self):
        return ["fail-model"]

    def get_default_model(self) -> str:
        return "fail-model"

    def translate(self, segments, source_language, target_language, options=None, progress_callback=None):
        return TranslationResult(
            success=False,
            provider="mock_failing",
            model="fail-model",
            source_language=source_language,
            target_language=target_language,
            segments=segments,
            error=TranslationError(
                code=ErrorCode.RATE_LIMIT,
                message="Simulated quota exceeded 429",
                provider="mock_failing",
                retryable=True,
            ),
        )

    def test_connection(self, credentials=None):
        return {"success": False, "provider": "mock_failing", "message": "Rate limit"}


def test_provider_registration_and_catalog():
    print("Testing provider catalog and registration...")
    service = TranslationService()
    providers = service.list_providers()
    provider_ids = [p["id"] for p in providers]

    assert "gemini" in provider_ids, "Gemini provider missing"
    assert "openai" in provider_ids, "OpenAI provider missing"
    assert "google_cloud" in provider_ids, "Google Cloud provider missing"
    assert "local_model" in provider_ids, "Local model provider missing"

    gemini_p = service.get_provider("gemini")
    assert gemini_p.get_name() == "gemini"
    assert "flash" in gemini_p.get_default_model()
    print("Provider catalog tests passed!")


def test_translation_memory_and_glossary_db():
    print("Testing Translation Memory and Glossary persistence...")
    proj_id = "test_project_alpha"

    # Test TM
    store_translation_memory(
        source_text="Hello world",
        translated_text="សួស្តីពិភពលោក",
        source_lang="en",
        target_lang="km",
        provider="gemini",
        project_id=proj_id,
    )

    found = lookup_translation_memory("Hello world", source_lang="en", target_lang="km")
    assert found == "សួស្តីពិភពលោក", f"Expected 'សួស្តីពិភពលោក', got '{found}'"

    # Test Glossary
    g_item = add_glossary_term(
        project_id=proj_id,
        source_term="AI Dubbing",
        target_term="ការបញ្ចូលសំឡេង AI",
        notes="Official brand term",
    )
    assert g_item["id"] is not None

    terms = list_glossary_terms(proj_id)
    assert any(t["source_term"] == "AI Dubbing" for t in terms)

    # Prompt instruction check
    instruction = TranslationMemoryManager.build_glossary_prompt_instruction(proj_id)
    assert "AI Dubbing" in instruction
    assert "ការបញ្ចូលសំឡេង AI" in instruction

    # Post processing check
    sample_raw = "This is an AI Dubbing video"
    post_proc = TranslationMemoryManager.apply_glossary_post_processing(sample_raw, proj_id)
    assert "ការបញ្ចូលសំឡេង AI" in post_proc

    # Clean up glossary term
    delete_glossary_term(g_item["id"])
    print("Translation Memory and Glossary DB tests passed!")


def test_user_and_project_settings():
    print("Testing user and project AI translation settings...")
    user_id = "test_user_42"
    proj_id = "test_proj_42"

    # User level
    save_user_ai_settings(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        fallback_provider="gemini",
        fallback_enabled=True,
    )
    u_settings = get_user_ai_settings(user_id)
    assert u_settings["provider"] == "openai"
    assert u_settings["model"] == "gpt-4o"

    # Project override
    save_project_settings(
        project_id=proj_id,
        provider="google_cloud",
        model="nmt",
    )
    p_settings = get_project_settings(proj_id)
    assert p_settings["provider"] == "google_cloud"

    # Effective resolution
    effective = resolve_effective_settings(proj_id, user_id)
    assert effective["provider"] == "google_cloud", "Project override should take precedence"

    effective_user_only = resolve_effective_settings(None, user_id)
    assert effective_user_only["provider"] == "openai", "Should fall back to user settings"
    print("User and Project settings tests passed!")


def test_provider_fallback_routing():
    print("Testing intelligent fallback switching...")
    service = TranslationService()

    # Register mock providers
    service.register_provider(MockFailingProvider())
    service.register_provider(MockWorkingProvider())

    segments = [
        TranslationSegment(id=1, start=0.0, end=2.0, source_text="Good morning!"),
        TranslationSegment(id=2, start=2.5, end=4.5, source_text="How are you?"),
    ]

    # Translate with primary=mock_failing, fallback=mock_working
    result = service.translate_batch(
        segments=segments,
        source_lang="en",
        target_lang="km",
        provider_name="mock_failing",
        options={
            "enable_fallback": True,
            "fallback_provider": "mock_working",
            "use_translation_memory": False,
            "use_glossary": False,
        },
    )

    assert result.success is True, "Fallback should have succeeded"
    assert result.provider == "mock_working", f"Provider should have switched to mock_working, got {result.provider}"
    assert len(result.segments) == 2
    assert "ប្រែ: Good morning!" in result.segments[0].khmer_text
    print("Intelligent fallback switching tests passed!")


def test_row_locking_preservation():
    print("Testing row locking protection...")
    service = TranslationService()
    service.register_provider(MockWorkingProvider())

    segments_raw = [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "Preserve me!", "khmer_text": "អត្ថបទចាក់សោរ", "locked": True},
        {"id": 2, "start": 2.5, "end": 4.5, "text": "Translate me!", "khmer_text": "", "locked": False},
    ]

    result = service.translate_subtitles_pipeline(
        segments_raw=segments_raw,
        provider="mock_working",
        options={"use_translation_memory": False},
    )

    assert result.success is True
    assert len(result.segments) == 2

    seg1 = next(s for s in result.segments if s.id == 1)
    seg2 = next(s for s in result.segments if s.id == 2)

    assert seg1.khmer_text == "អត្ថបទចាក់សោរ", "Locked segment khmer_text must NOT be overwritten"
    assert seg1.locked is True, "Locked segment must remain locked"
    assert "ប្រែ: Translate me!" in seg2.khmer_text, "Unlocked segment must be translated"
    print("Row locking preservation tests passed!")


def test_fastapi_translation_routes():
    print("Testing FastAPI Multi-Provider Translation routes...")
    routes = [route.path for route in app.routes]
    expected_new_routes = [
        "/api/translation/providers",
        "/api/translation/settings",
        "/api/translation/test-provider",
        "/api/projects/{project_id}/translate",
        "/api/projects/{project_id}/translation-status",
        "/api/projects/{project_id}/translation/cancel",
        "/api/projects/{project_id}/translation-memory",
        "/api/translation-memory/{item_id}",
        "/api/projects/{project_id}/glossary",
        "/api/projects/{project_id}/glossary/{item_id}",
        "/api/subtitles/{segment_id}/regenerate",
        "/api/admin/translation/stats",
    ]

    for r in expected_new_routes:
        assert r in routes, f"Missing route: {r}"
    print(f"All {len(expected_new_routes)} new translation routes are correctly registered in FastAPI!")


def test_repeated_job_creation_upsert():
    print("Testing repeated translation job creation upsert...")
    from backend.translation.db import create_translation_job, get_translation_job

    test_job_id = "test_repeat_job_999"
    # First run
    job1 = create_translation_job(
        job_id=test_job_id,
        project_id="proj_repeat",
        provider="gemini",
        model="gemini-3.5-flash",
        total_segments=10,
    )
    assert job1["id"] == test_job_id
    assert job1["status"] == "processing"

    # Second run (same job ID as when user re-clicks Translate Subtitles)
    job2 = create_translation_job(
        job_id=test_job_id,
        project_id="proj_repeat",
        provider="openai",
        model="gpt-4o-mini",
        total_segments=15,
    )
    assert job2["id"] == test_job_id
    assert job2["provider"] == "openai"
    assert job2["total_segments"] == 15
    print("Repeated translation job upsert passed without UNIQUE constraint error!")


if __name__ == "__main__":
    print("\n========================================================")
    print("   RUNNING MULTI-PROVIDER TRANSLATION TEST SUITE")
    print("========================================================\n")
    test_provider_registration_and_catalog()
    test_translation_memory_and_glossary_db()
    test_user_and_project_settings()
    test_provider_fallback_routing()
    test_row_locking_preservation()
    test_repeated_job_creation_upsert()
    test_fastapi_translation_routes()
    print("\n>>> ALL MULTI-PROVIDER TRANSLATION TESTS PASSED PERFECTLY! <<<\n")

