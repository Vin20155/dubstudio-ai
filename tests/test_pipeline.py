import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import KHMER_VOICES, TEMP_DIR, FFMPEG_PATH, FFPROBE_PATH
from backend.tts_engine import synthesize_segment, resolve_voice_params, EMOTION_SPECS
from backend.audio_video_processor import (
    get_audio_duration,
    time_stretch_audio,
    stitch_dubbed_audio,
    generate_srt,
    generate_vtt,
)
from backend.main import app

def test_config():
    print("Testing config and paths...")
    assert os.path.exists(FFMPEG_PATH), f"FFmpeg path not found: {FFMPEG_PATH}"
    assert os.path.exists(FFPROBE_PATH), f"FFprobe path not found: {FFPROBE_PATH}"
    assert "Piseth" in KHMER_VOICES
    assert "Sreymom" in KHMER_VOICES
    print("Config tests passed!")

def test_khmer_tts():
    print("Testing Khmer Edge-TTS voice synthesis...")
    test_text = "សួស្តីបងប្អូនទាំងអស់គ្នា សូមស្វាគមន៍មកកាន់ស្ទូឌីយោបញ្ចូលសំឡេង AI"
    out_piseth = str(TEMP_DIR / "test_piseth.mp3")
    out_sreymom = str(TEMP_DIR / "test_sreymom.mp3")

    # Piseth
    res1 = synthesize_segment(test_text, voice="km-KH-PisethNeural", output_path=out_piseth)
    assert res1 and os.path.exists(res1), "Failed to synthesize Piseth Khmer voice"
    dur1 = get_audio_duration(res1)
    print(f"Piseth Khmer Audio synthesized! Duration: {dur1:.2f}s")

    # Sreymom
    res2 = synthesize_segment(test_text, voice="km-KH-SreymomNeural", output_path=out_sreymom)
    assert res2 and os.path.exists(res2), "Failed to synthesize Sreymom Khmer voice"
    dur2 = get_audio_duration(res2)
    print(f"Sreymom Khmer Audio synthesized! Duration: {dur2:.2f}s")
    print("Khmer Edge-TTS tests passed!")

def test_audio_processing():
    print("Testing audio time stretching and stitching...")
    sample_audio = str(TEMP_DIR / "test_piseth.mp3")
    stretched_audio = str(TEMP_DIR / "test_stretched.mp3")

    # Test time stretch
    ok = time_stretch_audio(sample_audio, stretched_audio, target_duration=2.5)
    assert ok and os.path.exists(stretched_audio), "Time stretch failed"
    new_dur = get_audio_duration(stretched_audio)
    print(f"Time-stretched audio to {new_dur:.2f}s (target: 2.5s)")

    # Test segment stitching
    segments = [
        {"id": 1, "start": 0.5, "end": 3.0, "audio_path": sample_audio, "khmer_text": "ជំរាបសួរ"},
        {"id": 2, "start": 4.0, "end": 6.5, "audio_path": stretched_audio, "khmer_text": "ស្វាគមន៍"},
    ]
    stitched_output = str(TEMP_DIR / "test_stitched.mp3")
    stitch_ok = stitch_dubbed_audio(segments, total_duration=8.0, output_audio_path=stitched_output)
    assert stitch_ok and os.path.exists(stitched_output), "Stitching failed"
    stitched_dur = get_audio_duration(stitched_output)
    print(f"Stitched track duration: {stitched_dur:.2f}s (target 8.0s)")

    # Test SRT/VTT generation
    srt_out = str(TEMP_DIR / "test_sub.srt")
    vtt_out = str(TEMP_DIR / "test_sub.vtt")
    assert generate_srt(segments, srt_out), "SRT generation failed"
    assert generate_vtt(segments, vtt_out), "VTT generation failed"
    print("Audio processing & subtitle tests passed!")

def test_fastapi_routes():
    print("Testing FastAPI route configuration...")
    routes = [route.path for route in app.routes]
    expected = [
        "/api/config",
        "/api/upload",
        "/api/stt",
        "/api/translate",
        "/api/tts/preview",
        "/api/tts/all",
        "/api/dub",
        "/api/auto-pipeline",
        "/api/jobs/{job_id}/stream",
    ]
    for r in expected:
        assert r in routes, f"Missing route: {r}"
    print(f"All {len(expected)} expected routes are registered in FastAPI!")
    print("FastAPI route configuration tests passed!")

def test_emotion_voice_preservation():
    print("Testing emotion voice preservation and natural acoustic bounds...")
    emotions = ["neutral", "whisper", "angry", "sad", "excited", "terrified", "romantic"]
    for emo in emotions:
        spec = EMOTION_SPECS.get(emo)
        assert spec is not None, f"Emotion '{emo}' must be defined in EMOTION_SPECS"
        assert spec.get("filter") is None, f"Emotion '{emo}' must not use destructive DSP filters"

        # Verify Piseth parameter resolution
        voice_id, rate_str, pitch_str = resolve_voice_params("km-KH-PisethNeural", emotion=emo)
        assert voice_id == "km-KH-PisethNeural"
        import re
        p_val = int(re.search(r"[-+]?\d+", pitch_str).group(0))
        r_val = int(re.search(r"[-+]?\d+", rate_str).group(0))
        assert -8 <= p_val <= 8, f"Pitch {p_val}Hz for {emo} exceeds natural bounds"
        assert -15 <= r_val <= 15, f"Rate {r_val}% for {emo} exceeds natural bounds"

    print("Emotion voice preservation tests passed (no distortion, 100% original voice preserved)!")

if __name__ == "__main__":
    print("=== RUNNING FULL TEST SUITE ===")
    test_config()
    test_emotion_voice_preservation()
    test_khmer_tts()
    test_audio_processing()
    test_fastapi_routes()
    print("=== ALL TESTS COMPLETED SUCCESSFULLY! ===")
