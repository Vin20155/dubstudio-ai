import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.audio_video_processor import generate_ass, hex_to_ass_color
from backend.config import TEMP_DIR


def test_generate_ass_tiktok_presets():
    """Test ASS generation with TikTok viral styles (karaoke highlight, pill box, font fallback)."""
    sample_segments = [
        {
            "id": 1,
            "start": 1.25,
            "end": 3.75,
            "text": "Hello everyone, welcome to the show!",
            "khmer_text": "សួស្តីអ្នកទាំងអស់គ្នា សូមស្វាគមន៍មកកាន់កម្មវិធីរបស់យើង",
        },
        {
            "id": 2,
            "start": 4.10,
            "end": 6.80,
            "text": "This is an exciting moment.",
            "khmer_text": "នេះជាពេលវេលាដ៏រំភើបមួយដែលមិនអាចបំភ្លេចបាន",
        },
    ]

    out_ass_pill = str(TEMP_DIR / "test_tiktok_pill.ass")
    out_ass_karaoke = str(TEMP_DIR / "test_tiktok_karaoke.ass")

    # 1. Test TikTok Pill Box Style
    style_pill = {
        "fontFamily": "Kantumruy Pro",
        "fontSize": 32,
        "textColor": "#FFFFFF",
        "bgStyle": "rounded",
        "bgColor": "#000000",
        "bgOpacity": 85,
        "bgPadding": 12,
        "positionPreset": "bottom-center",
        "strokeEnabled": False,
        "shadowEnabled": False,
    }
    ok_pill = generate_ass(sample_segments, out_ass_pill, style=style_pill)
    assert ok_pill, "Failed to generate TikTok Pill ASS file"
    assert os.path.exists(out_ass_pill), "Output ASS file was not created"

    with open(out_ass_pill, "r", encoding="utf-8") as f:
        content_pill = f.read()

    assert "[Script Info]" in content_pill
    assert "PlayResX: 1920" in content_pill
    assert "PlayResY: 1080" in content_pill
    # Must use BorderStyle 3 for bounding box fill
    assert ",3," in content_pill, "BorderStyle 3 (Opaque Box) not found in Pill style"
    assert "Kantumruy Pro" in content_pill
    assert "សួស្តីអ្នកទាំងអស់គ្នា" in content_pill

    # 2. Test TikTok Karaoke / Pop Highlighting Style
    style_karaoke = {
        "fontFamily": "Khmer OS Battambang",
        "fontSize": 34,
        "textColor": "#FFFFFF",
        "strokeEnabled": True,
        "strokeColor": "#000000",
        "strokeWidth": 4,
        "shadowEnabled": True,
        "shadowColor": "#000000",
        "shadowBlur": 8,
        "bgStyle": "none",
        "wordAnim": "karaoke",
        "karaokeColor": "#FACC15",
        "positionPreset": "bottom-center",
    }
    ok_karaoke = generate_ass(sample_segments, out_ass_karaoke, style=style_karaoke)
    assert ok_karaoke, "Failed to generate TikTok Karaoke ASS file"
    assert os.path.exists(out_ass_karaoke), "Output Karaoke ASS file was not created"

    with open(out_ass_karaoke, "r", encoding="utf-8") as f:
        content_karaoke = f.read()

    assert r"{\k" in content_karaoke, "Karaoke progressive fill tag \\k was not rendered"
    assert "Khmer OS Battambang" in content_karaoke

    print("All Animated Hardsub (.ass) unit tests PASSED successfully!")


if __name__ == "__main__":
    test_generate_ass_tiktok_presets()
