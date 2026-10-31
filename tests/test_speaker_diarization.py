import os
import tempfile
import numpy as np
import pytest
import soundfile as sf
from backend.stt_engine import diarize_segments_with_audio, estimate_segment_pitch_and_centroid


@pytest.fixture
def multi_speaker_wav():
    sr = 16000
    total_len = int(8.0 * sr)
    audio = np.zeros(total_len, dtype=np.float32)

    # Segment 1: Male 0.0 - 1.8s (125 Hz)
    t1 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[0:len(t1)] = 0.8 * np.sin(2 * np.pi * 125 * t1) + 0.3 * np.sin(2 * np.pi * 250 * t1)

    # Segment 2: Male 2.0 - 3.8s (130 Hz)
    t2 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[int(2.0*sr):int(2.0*sr)+len(t2)] = 0.8 * np.sin(2 * np.pi * 130 * t2) + 0.3 * np.sin(2 * np.pi * 260 * t2)

    # Segment 3: Female 4.0 - 5.8s (220 Hz)
    t3 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[int(4.0*sr):int(4.0*sr)+len(t3)] = 0.8 * np.sin(2 * np.pi * 220 * t3) + 0.3 * np.sin(2 * np.pi * 440 * t3)

    # Segment 4: Female 6.0 - 7.8s (215 Hz)
    t4 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[int(6.0*sr):int(6.0*sr)+len(t4)] = 0.8 * np.sin(2 * np.pi * 215 * t4) + 0.3 * np.sin(2 * np.pi * 430 * t4)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = f.name
    sf.write(wav_path, audio, sr)
    yield wav_path
    if os.path.exists(wav_path):
        os.remove(wav_path)


@pytest.fixture
def single_speaker_male_wav():
    sr = 16000
    total_len = int(6.0 * sr)
    audio = np.zeros(total_len, dtype=np.float32)

    # All segments are Male (120-130 Hz)
    for start_t in [0.0, 2.0, 4.0]:
        t = np.linspace(0, 1.5, int(1.5 * sr))
        idx = int(start_t * sr)
        audio[idx:idx+len(t)] = 0.8 * np.sin(2 * np.pi * 125 * t) + 0.3 * np.sin(2 * np.pi * 250 * t)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = f.name
    sf.write(wav_path, audio, sr)
    yield wav_path
    if os.path.exists(wav_path):
        os.remove(wav_path)


def test_multi_speaker_character_clustering(multi_speaker_wav):
    segments = [
        {"id": 1, "start": 0.0, "end": 1.8, "text": "Good morning."},
        {"id": 2, "start": 2.0, "end": 3.8, "text": "How can I assist you?"},
        {"id": 3, "start": 4.0, "end": 5.8, "text": "I would like to check my order."},
        {"id": 4, "start": 6.0, "end": 7.8, "text": "Here is my receipt number."},
    ]

    diarized = diarize_segments_with_audio(multi_speaker_wav, segments)
    assert len(diarized) == 4

    # Segment 1 & 2 must be Male character (Speaker 1)
    assert diarized[0]["speaker"] == "Speaker 1"
    assert diarized[0]["voice"] == "Khmer Male 01"
    assert diarized[1]["speaker"] == "Speaker 1"
    assert diarized[1]["voice"] == "Khmer Male 01"

    # Segment 3 & 4 must be Female character (Speaker 2)
    assert diarized[2]["speaker"] == "Speaker 2"
    assert diarized[2]["voice"] == "Khmer Female 01"
    assert diarized[3]["speaker"] == "Speaker 2"
    assert diarized[3]["voice"] == "Khmer Female 01"


def test_single_speaker_no_false_alternation(single_speaker_male_wav):
    """
    A single character speaking throughout must remain Speaker 1 consistently,
    without alternating falsely across pauses.
    """
    segments = [
        {"id": 1, "start": 0.0, "end": 1.5, "text": "Sentence one."},
        {"id": 2, "start": 2.0, "end": 3.5, "text": "Sentence two?"},
        {"id": 3, "start": 4.0, "end": 5.5, "text": "Sentence three."},
    ]

    diarized = diarize_segments_with_audio(single_speaker_male_wav, segments)
    assert len(diarized) == 3

    # All segments must stay Speaker 1 (Male)
    for s in diarized:
        assert s["speaker"] == "Speaker 1"
        assert s["voice"] == "Khmer Male 01"


def test_multi_speaker_with_child():
    """
    Test character speaker clustering with adult male and young child voice.
    """
    sr = 16000
    total_len = int(6.0 * sr)
    audio = np.zeros(total_len, dtype=np.float32)

    # Segment 1: Male 0.0 - 1.8s (125 Hz)
    t1 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[0:len(t1)] = 0.8 * np.sin(2 * np.pi * 125 * t1) + 0.3 * np.sin(2 * np.pi * 250 * t1)

    # Segment 2: Child girl 3.0 - 4.8s (310 Hz)
    t2 = np.linspace(0, 1.8, int(1.8 * sr))
    audio[int(3.0 * sr):int(3.0 * sr) + len(t2)] = 0.8 * np.sin(2 * np.pi * 310 * t2) + 0.3 * np.sin(2 * np.pi * 620 * t2)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = f.name
    sf.write(wav_path, audio, sr)

    try:
        segments = [
            {"id": 1, "start": 0.0, "end": 1.8, "text": "Hello child."},
            {"id": 2, "start": 3.0, "end": 4.8, "text": "Hello sir!"},
        ]
        diarized = diarize_segments_with_audio(wav_path, segments)
        assert len(diarized) == 2
        assert diarized[0]["speaker"] == "Speaker 1"
        assert diarized[0]["voice"] == "Khmer Male 01"
        assert "3" in diarized[1]["speaker"] or "2" in diarized[1]["speaker"]
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
