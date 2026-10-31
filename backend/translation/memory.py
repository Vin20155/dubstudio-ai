"""
Translation Memory and Project Glossary engine.
Handles caching, glossary injection into prompts, and post-translation glossary verification.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from .base import TranslationSegment
from .db import (
    get_project_glossary_map,
    lookup_translation_memory,
    store_translation_memory,
)

logger = logging.getLogger("translation_memory")


class TranslationMemoryManager:
    """Manages translation memory caching and glossary enforcement."""

    @staticmethod
    def apply_translation_memory(
        segments: List[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "km",
        enabled: bool = True,
    ) -> Tuple[List[TranslationSegment], List[TranslationSegment]]:
        """
        Splits segments into:
        - to_translate: Segments not found in TM and not locked
        - cached_segments: Segments resolved from TM or already locked
        """
        if not enabled:
            to_trans = [s for s in segments if not s.locked]
            locked = [s for s in segments if s.locked]
            return to_trans, locked

        to_translate: List[TranslationSegment] = []
        resolved: List[TranslationSegment] = []

        for seg in segments:
            if seg.locked and (seg.khmer_text or seg.translated_text):
                resolved.append(seg)
                continue

            # Check TM
            cached_trans = lookup_translation_memory(seg.source_text, source_lang, target_lang)
            if cached_trans:
                seg.translated_text = cached_trans
                seg.khmer_text = cached_trans
                seg.provider = "translation_memory"
                resolved.append(seg)
            else:
                to_translate.append(seg)

        return to_translate, resolved

    @staticmethod
    def save_to_memory(
        segments: List[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "km",
        provider: str = "gemini",
        project_id: Optional[str] = None,
        enabled: bool = True,
    ):
        """Saves newly translated segments into the translation memory database."""
        if not enabled:
            return

        for seg in segments:
            text = seg.source_text.strip()
            trans = (seg.khmer_text or seg.translated_text).strip()
            if text and trans and seg.provider != "translation_memory":
                store_translation_memory(
                    source_text=text,
                    translated_text=trans,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider=provider,
                    project_id=project_id,
                )

    @staticmethod
    def build_glossary_prompt_instruction(project_id: Optional[str] = None) -> str:
        """Constructs a strict glossary instruction block to insert into AI prompts."""
        glossary_map = get_project_glossary_map(project_id)
        if not glossary_map:
            return ""

        terms_lines = [f"- \"{k}\" ➔ \"{v}\"" for k, v in glossary_map.items()]
        return (
            "\nMandatory Project Terminology Glossary:\n"
            "You MUST strictly use these exact Khmer translations for the following terms whenever they occur:\n"
            + "\n".join(terms_lines)
            + "\n"
        )

    @staticmethod
    def apply_glossary_post_processing(
        text: str,
        project_id: Optional[str] = None,
    ) -> str:
        """Post-processes translated text to ensure exact glossary term usage where applicable."""
        glossary_map = get_project_glossary_map(project_id)
        if not glossary_map:
            return text

        # Single-pass replacement using combined regex to avoid re-matching inside substituted text
        sorted_terms = sorted(glossary_map.items(), key=lambda item: len(item[0]), reverse=True)
        lookup = {src.lower(): target for src, target in sorted_terms}
        escaped_parts = [re.escape(src) for src, _ in sorted_terms]
        pattern_str = r"\b(" + "|".join(escaped_parts) + r")\b"
        pattern = re.compile(pattern_str, re.IGNORECASE)

        def replace_match(match):
            key = match.group(0).lower()
            return lookup.get(key, match.group(0))

        return pattern.sub(replace_match, text)
