"""
Multi-Provider Translation Package
"""

from .base import (
    ErrorCode,
    TranslationError,
    TranslationOption,
    TranslationProviderInterface,
    TranslationResult,
    TranslationSegment,
    TranslationStyle,
)
from .service import TranslationService, get_translation_service
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleCloudProvider
from .local_provider import LocalModelProvider
from .codecraft_provider import CodeCraftProvider
from .db import (
    add_glossary_term,
    delete_glossary_term,
    delete_translation_memory,
    get_admin_translation_stats,
    get_project_settings,
    get_translation_job,
    get_user_ai_settings,
    list_glossary_terms,
    list_translation_memory,
    save_project_settings,
    save_user_ai_settings,
    store_translation_memory,
    update_translation_job,
)
from .batch_manager import BatchTranslationManager, get_batch_manager

__all__ = [
    "ErrorCode",
    "TranslationError",
    "TranslationOption",
    "TranslationProviderInterface",
    "TranslationResult",
    "TranslationSegment",
    "TranslationStyle",
    "TranslationService",
    "get_translation_service",
    "BatchTranslationManager",
    "get_batch_manager",
    "GeminiProvider",
    "OpenAIProvider",
    "GoogleCloudProvider",
    "LocalModelProvider",
    "CodeCraftProvider",
    "add_glossary_term",
    "delete_glossary_term",
    "delete_translation_memory",
    "get_admin_translation_stats",
    "get_project_settings",
    "get_translation_job",
    "get_user_ai_settings",
    "list_glossary_terms",
    "list_translation_memory",
    "save_project_settings",
    "save_user_ai_settings",
    "store_translation_memory",
    "update_translation_job",
]

