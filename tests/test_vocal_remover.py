import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import TEMP_DIR
from backend.tts_engine import synthesize_segment
from backend.audio_video_processor import get_audio_duration, mix_audio_with_video
from backend.vocal_remover import remove_vocals_dsp, extract_clean_bgm

def test_vocal_remover():
    print("Testing Vocal Remover & BGM Isolation...")

    # 1. Generate test speech
    test_audio = str(TEMP_DIR / "sample_speech.mp3")
    res = synthesize_segment("Hello, this is a test dialogue to verify vocal separation and BGM extraction.", voice="km-KH-PisethNeural", output_path=test_audio)
    assert res and os.path.exists(test_audio), "Sample speech synthesis failed"

    # 2. Test fast DSP vocal reduction
    dsp_out = str(TEMP_DIR / "sample_bgm_dsp.wav")
    ok_dsp = remove_vocals_dsp(test_audio, dsp_out)
    assert ok_dsp and os.path.exists(dsp_out), "DSP vocal removal failed"
    dur_dsp = get_audio_duration(dsp_out)
    print(f"DSP BGM extracted successfully! Duration: {dur_dsp:.2f}s")

    # 3. Test extract_clean_bgm with fast_dsp fallback
    clean_bgm = str(TEMP_DIR / "sample_clean_bgm.wav")
    ok_clean = extract_clean_bgm(test_audio, clean_bgm, method="fast_dsp")
    assert ok_clean and os.path.exists(clean_bgm), "Clean BGM extraction failed"
    print("Clean BGM extraction (DSP) test passed!")

    # 4. Test extract_clean_bgm with ai_bs_roformer primary method
    sota_bgm = str(TEMP_DIR / "sample_sota_bgm.wav")
    ok_sota = extract_clean_bgm(test_audio, sota_bgm, method="ai_bs_roformer")
    assert ok_sota and os.path.exists(sota_bgm), "BS-RoFormer BGM extraction cascade failed"
    print("Clean BGM extraction (BS-RoFormer AI cascade) test passed!")

    print("=== VOCAL REMOVER TESTS PASSED ===")

if __name__ == "__main__":
    test_vocal_remover()
