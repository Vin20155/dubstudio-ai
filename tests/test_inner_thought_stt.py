import sys
from pathlib import Path
from types import SimpleNamespace

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.stt_engine import (
    split_words_into_dialogue_segments,
    merge_dialogue_fragments,
    get_stt_initial_prompt,
)


def test_inner_thought_synthesized_words_preserved():
    """
    Simulates Whisper producing an inner thought with heavy reverb where
    word timestamps had to be synthesized. Verifies that split_words_into_dialogue_segments
    captures the entire sentence cleanly.
    """
    start_time = 14.5
    end_time = 18.2
    text = "តើខ្ញុំគួរតែសារភាពប្រាប់នាងឥឡូវនេះទេ?"
    words_list = text.split()
    
    words_collected = []
    w_dur = (end_time - start_time) / len(words_list)
    for i, w in enumerate(words_list):
        w_st = round(start_time + i * w_dur, 2)
        w_et = round(w_st + w_dur, 2)
        words_collected.append(
            SimpleNamespace(word=w, start=w_st, end=w_et, probability=1.0)
        )

    segments = split_words_into_dialogue_segments(words_collected, detected_lang="km")
    assert len(segments) >= 1
    full_transcribed = " ".join(s["text"] for s in segments)
    for w in words_list:
        assert w in full_transcribed


def test_initial_prompt_contains_inner_monologue_directives():
    """
    Verifies that initial prompts for Khmer, English, Chinese, and Japanese
    explicitly instruct the model to capture inner thoughts (ការនិយាយក្នុងចិត្ត / គិតក្នុងចិត្ត).
    """
    km_prompt = get_stt_initial_prompt("km")
    assert "និយាយក្នុងចិត្ត" in km_prompt or "គិតក្នុងចិត្ត" in km_prompt

    en_prompt = get_stt_initial_prompt("en")
    assert "inner thoughts" in en_prompt or "internal monologue" in en_prompt

    zh_prompt = get_stt_initial_prompt("zh")
    assert "内心独白" in zh_prompt or "心声" in zh_prompt

    ja_prompt = get_stt_initial_prompt("ja")
    assert "心の声" in ja_prompt or "モノローグ" in ja_prompt
