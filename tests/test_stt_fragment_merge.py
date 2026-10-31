import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.stt_engine import merge_dialogue_fragments, split_words_into_dialogue_segments


class DummyWord:
    def __init__(self, word: str, start: float, end: float):
        self.word = word
        self.start = start
        self.end = end


def test_merge_exact_user_scenario():
    """
    Tests the exact scenario shown in the user's screenshot:
    Row 1: 00:24.89 - 00:25.85 "what I"
    Row 2: 00:26.73 - 00:29.59 "need to go to the bathroom"
    The 0.88s pause inside the sentence must NOT keep them separated.
    They must merge into: "what I need to go to the bathroom" [24.89 - 29.59]
    """
    segments = [
        {"id": 1, "start": 24.89, "end": 25.85, "text": "what I", "speaker": "Speaker 1"},
        {"id": 2, "start": 26.73, "end": 29.59, "text": "need to go to the bathroom", "speaker": "Speaker 1"},
    ]

    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 1
    assert merged[0]["id"] == 1
    assert merged[0]["start"] == 24.89
    assert merged[0]["end"] == 29.59
    assert merged[0]["text"] == "what I need to go to the bathroom"
    assert merged[0]["speaker"] == "Speaker 1"


def test_merge_dangling_connectors():
    """
    Incomplete sentences ending in prepositions/conjunctions/pronouns
    must merge with the following continuation.
    """
    segments = [
        {"id": 1, "start": 1.0, "end": 2.2, "text": "I think that", "speaker": "Speaker 1"},
        {"id": 2, "start": 2.8, "end": 4.5, "text": "we should leave right now.", "speaker": "Speaker 1"},
    ]
    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 1
    assert merged[0]["text"] == "I think that we should leave right now."
    assert merged[0]["start"] == 1.0
    assert merged[0]["end"] == 4.5


def test_preserve_question_boundaries():
    """
    Complete questions ending in '?' must NOT be merged across dialogues.
    """
    segments = [
        {"id": 1, "start": 1.0, "end": 2.5, "text": "Where are you going?", "speaker": "Speaker 1"},
        {"id": 2, "start": 3.0, "end": 4.5, "text": "I am going to the market.", "speaker": "Speaker 1"},
    ]
    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 2
    assert merged[0]["text"] == "Where are you going?"
    assert merged[1]["text"] == "I am going to the market."


def test_preserve_speaker_turns():
    """
    Utterances from different speakers must never be merged.
    """
    segments = [
        {"id": 1, "start": 1.0, "end": 2.0, "text": "what I", "speaker": "Speaker 1"},
        {"id": 2, "start": 2.5, "end": 4.0, "text": "need to tell you is secret.", "speaker": "Speaker 2"},
    ]
    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 2
    assert merged[0]["speaker"] == "Speaker 1"
    assert merged[1]["speaker"] == "Speaker 2"


def test_split_words_into_dialogue_segments_user_case():
    """
    Word-level segmentation should not split at a 0.88s hesitation mid-sentence
    when words form an incomplete phrase ('what I' -> 'need to go to the bathroom').
    """
    words = [
        DummyWord("what", 24.89, 25.30),
        DummyWord("I", 25.35, 25.85),
        # 0.88s pause here
        DummyWord("need", 26.73, 27.20),
        DummyWord("to", 27.25, 27.45),
        DummyWord("go", 27.50, 27.80),
        DummyWord("to", 27.85, 28.05),
        DummyWord("the", 28.10, 28.30),
        DummyWord("bathroom.", 28.35, 29.59),
    ]

    segments = split_words_into_dialogue_segments(words, detected_lang="en")
    assert len(segments) == 1
    assert segments[0]["start"] == 24.89
    assert segments[0]["end"] == 29.59
    assert "what I need to go to the bathroom." in segments[0]["text"]


def test_merge_khmer_sentence_flow():
    """
    Test Khmer dialogue without Latin punctuation merges properly.
    """
    segments = [
        {"id": 1, "start": 10.0, "end": 11.2, "text": "ខ្ញុំគិតថា", "speaker": "Speaker 1", "language": "km"},
        {"id": 2, "start": 11.8, "end": 13.5, "text": "យើងគួរតែទៅឥឡូវនេះ។", "speaker": "Speaker 1", "language": "km"},
    ]
    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 1
    assert "ខ្ញុំគិតថា យើងគួរតែទៅឥឡូវនេះ។" in merged[0]["text"]


def test_short_character_words_not_dropped():
    """
    Quick one-word character shouts (<0.25s) like 'No!', 'Stop!'
    must not be dropped by finish_segment and must receive valid display duration.
    """
    words = [
        DummyWord("No!", 5.00, 5.18),  # 0.18s utterance
    ]
    segments = split_words_into_dialogue_segments(words, detected_lang="en")
    assert len(segments) == 1
    assert segments[0]["text"] == "No!"
    assert segments[0]["start"] == 5.00
    assert segments[0]["end"] >= 5.35  # Padded to at least 0.35s


def test_short_questions_not_merged_into_next_line():
    """
    Short 3-word questions ('What is that?') must never be treated as dangling
    and must not be merged into the next sentence.
    """
    segments = [
        {"id": 1, "start": 1.0, "end": 2.2, "text": "What is that?", "speaker": "Speaker 1"},
        {"id": 2, "start": 2.8, "end": 4.5, "text": "It is a new car.", "speaker": "Speaker 1"},
    ]
    merged = merge_dialogue_fragments(segments)
    assert len(merged) == 2
    assert merged[0]["text"] == "What is that?"
    assert merged[1]["text"] == "It is a new car."


def test_filler_filter_preserves_real_words():
    """
    Articles like 'A', and character words like 'mama', 'mom', 'oh' must never be filtered out.
    Only pure laughter/screaming noise should be filtered.
    """
    from backend.stt_engine import is_filler_or_hallucination

    # Real words that must NOT be filtered
    assert not is_filler_or_hallucination("A doctor")
    assert not is_filler_or_hallucination("A")
    assert not is_filler_or_hallucination("mama")
    assert not is_filler_or_hallucination("mom")
    assert not is_filler_or_hallucination("oh no")
    assert not is_filler_or_hallucination("hmm")
    assert not is_filler_or_hallucination("shh")
    assert not is_filler_or_hallucination("ឈប់")
    assert not is_filler_or_hallucination("បាទ")

    assert is_filler_or_hallucination("hahaha")
    assert is_filler_or_hallucination("hehehe")
    assert is_filler_or_hallucination("ahhhhh")
    print("All filler filter tests passed!")


def test_exclamation_split_and_isolation():
    """
    Exclamations (ឧទាន !) like 'Stop!', 'Wait!', 'ឈប់សិន!' must never be glued
    to subsequent sentences, and compound sentences must be cleanly split.
    """
    from backend.stt_engine import split_compound_dialogue_segment

    # Compound segment containing an exclamation and question
    compound_seg = {
        "id": 1,
        "start": 5.0,
        "end": 8.0,
        "text": "Stop! Who is there?",
        "speaker": "Speaker 1"
    }
    split_res = split_compound_dialogue_segment(compound_seg)
    assert len(split_res) == 2
    assert split_res[0]["text"] == "Stop!"
    assert split_res[1]["text"] == "Who is there?"
    assert split_res[0]["end"] <= split_res[1]["start"]

    # Khmer compound exclamation
    km_compound = {
        "id": 2,
        "start": 10.0,
        "end": 14.0,
        "text": "ឈប់សិន! ទៅណា?",
        "speaker": "Speaker 1"
    }
    km_split = split_compound_dialogue_segment(km_compound)
    assert len(km_split) == 2
    assert km_split[0]["text"] == "ឈប់សិន!"
    assert km_split[1]["text"] == "ទៅណា?"

    # Exclamatory dialogue lines must never merge
    segs = [
        {"id": 1, "start": 1.0, "end": 2.0, "text": "Wait!", "speaker": "Speaker 1"},
        {"id": 2, "start": 2.2, "end": 3.5, "text": "I hear something.", "speaker": "Speaker 1"}
    ]
    merged = merge_dialogue_fragments(segs)
    assert len(merged) == 2
    assert merged[0]["text"] == "Wait!"
    assert merged[1]["text"] == "I hear something."


def test_khmer_khan_boundary_isolation():
    """
    Sentences ending with Khmer Khan (ខណ្ឌ ។ ឬ ៕) must NEVER merge with following sentences.
    """
    segs = [
        {"id": 1, "start": 1.0, "end": 2.5, "text": "ខ្ញុំបានមកដល់ហើយ។", "speaker": "Speaker 1", "language": "km"},
        {"id": 2, "start": 2.8, "end": 4.5, "text": "តើអ្នកនៅឯណា?", "speaker": "Speaker 1", "language": "km"}
    ]
    merged = merge_dialogue_fragments(segs)
    assert len(merged) == 2
    assert merged[0]["text"] == "ខ្ញុំបានមកដល់ហើយ។"
    assert merged[1]["text"] == "តើអ្នកនៅឯណា?"


def test_different_speakers_never_overlap():
    """
    Segments from different speakers must never collide or overlap in time.
    """
    segs = [
        {"id": 1, "start": 1.0, "end": 2.6, "text": "Hello there.", "speaker": "Speaker 1"},
        {"id": 2, "start": 2.5, "end": 4.0, "text": "Hi, how are you?", "speaker": "Speaker 2"}
    ]
    merged = merge_dialogue_fragments(segs)
    assert len(merged) == 2
    assert merged[0]["speaker"] == "Speaker 1"
    assert merged[1]["speaker"] == "Speaker 2"
    # First segment's end must be trimmed to avoid collision
    assert merged[0]["end"] <= merged[1]["start"]


if __name__ == "__main__":
    test_merge_exact_user_scenario()
    test_merge_dangling_connectors()
    test_preserve_question_boundaries()
    test_preserve_speaker_turns()
    test_split_words_into_dialogue_segments_user_case()
    test_merge_khmer_sentence_flow()
    test_short_character_words_not_dropped()
    test_short_questions_not_merged_into_next_line()
    test_filler_filter_preserves_real_words()
    test_exclamation_split_and_isolation()
    test_khmer_khan_boundary_isolation()
    test_different_speakers_never_overlap()
    print("=== ALL STT FRAGMENT MERGE & VERBATIM TESTS PASSED! ===")

