import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.audio_video_processor import mix_audio_with_video, get_media_info
from backend.config import UPLOADS_DIR, TEMP_DIR


def run_test():
    test_blur_pipeline()


def test_blur_pipeline():
    sample_video = str(UPLOADS_DIR / "d34d7bbdc5d5_original.webm")
    if not os.path.exists(sample_video):
        for f in os.listdir(UPLOADS_DIR):
            if f.endswith((".mp4", ".webm", ".mkv")):
                sample_video = str(UPLOADS_DIR / f)
                break
    if not os.path.exists(sample_video):
        sample_video = str(TEMP_DIR / "synthetic_test_video.mp4")
        os.system(f'ffmpeg -y -f lavfi -i "testsrc=duration=3:size=1280x720:rate=30" -f lavfi -i "sine=frequency=1000:duration=3" -c:v libx264 -c:a aac {sample_video}')

    # Extract or create dummy audio for test
    dummy_audio = str(TEMP_DIR / "test_dummy_audio.wav")
    out_video_blur = str(TEMP_DIR / "test_blur_output.mp4")
    out_video_916 = str(TEMP_DIR / "test_916_canvas.mp4")

    # Generate a 3-second sine wave audio for test if needed
    os.system(f'ffmpeg -y -f lavfi -i "sine=frequency=1000:duration=3" -c:a pcm_s16le {dummy_audio}')

    print(f"Testing 1: Subtitle Blur Masking on {sample_video}...")
    ok_blur = mix_audio_with_video(
        video_path=sample_video,
        dub_audio_path=dummy_audio,
        output_video_path=out_video_blur,
        mode="replace",
        blur_subtitles=True,
        subtitle_blur_box={"x": 0.0, "y": 0.80, "w": 1.0, "h": 0.16, "strength": 25},
    )
    print("Subtitle blur test result:", ok_blur)
    if ok_blur and os.path.exists(out_video_blur):
        info = get_media_info(out_video_blur)
        print("Blur output media info:", info)
        assert info.get("has_video") == True, "Missing video stream in blur output"

    print("\nTesting 2: 9:16 Vertical Blurred Canvas on {sample_video}...")
    ok_916 = mix_audio_with_video(
        video_path=sample_video,
        dub_audio_path=dummy_audio,
        output_video_path=out_video_916,
        mode="replace",
        blur_subtitles=True,
        subtitle_blur_box={"x": 0.0, "y": 0.80, "w": 1.0, "h": 0.16, "strength": 20},
        aspect_ratio_mode="9:16",
        canvas_blur_strength=30,
    )
    print("9:16 Canvas test result:", ok_916)
    if ok_916 and os.path.exists(out_video_916):
        info_916 = get_media_info(out_video_916)
        print("9:16 Canvas output media info:", info_916)
        assert info_916.get("width") == 1080 and info_916.get("height") == 1920, f"Expected 1080x1920, got {info_916.get('width')}x{info_916.get('height')}"

    print("\nAll Video Blur & Canvas Processing tests PASSED successfully!")

if __name__ == "__main__":
    run_test()
