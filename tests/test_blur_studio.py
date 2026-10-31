import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.audio_video_processor import mix_audio_with_video, get_media_info
from backend.config import UPLOADS_DIR, TEMP_DIR


def run_test():
    test_blur_studio()


def test_blur_studio():
    sample_video = str(UPLOADS_DIR / "d34d7bbdc5d5_original.webm")
    if not os.path.exists(sample_video):
        print(f"Sample video not found at {sample_video}, searching uploads directory...")
        for f in os.listdir(UPLOADS_DIR):
            if f.endswith((".mp4", ".webm", ".mkv")):
                sample_video = str(UPLOADS_DIR / f)
                break

    if not os.path.exists(sample_video):
        print("No sample video found in uploads, generating dummy 3s video with lavfi...")
        sample_video = str(TEMP_DIR / "synthetic_test_video.mp4")
        os.system(f'ffmpeg -y -f lavfi -i "testsrc=duration=3:size=1280x720:rate=30" -f lavfi -i "sine=frequency=1000:duration=3" -c:v libx264 -c:a aac {sample_video}')

    dummy_audio = str(TEMP_DIR / "test_studio_audio.wav")
    os.system(f'ffmpeg -y -f lavfi -i "sine=frequency=800:duration=3" -c:a pcm_s16le {dummy_audio}')

    out_video_multiblur = str(TEMP_DIR / "test_multiblur_output.mp4")

    print(f"Testing Multi-Object Blur on {sample_video}...")
    blur_objects = [
        {
            "id": "face_1",
            "name": "Face Blur",
            "enabled": True,
            "blurType": "gaussian",
            "shape": "ellipse",
            "x": 0.25,
            "y": 0.15,
            "width": 0.30,
            "height": 0.35,
            "strength": 60,
            "startTime": 0.0,
            "endTime": 2.5,
        },
        {
            "id": "mosaic_watermark",
            "name": "Mosaic Watermark",
            "enabled": True,
            "blurType": "pixelate",
            "shape": "rectangle",
            "x": 0.70,
            "y": 0.05,
            "width": 0.25,
            "height": 0.15,
            "strength": 75,
            "startTime": 0.5,
            "endTime": 3.0,
        }
    ]

    ok = mix_audio_with_video(
        video_path=sample_video,
        dub_audio_path=dummy_audio,
        output_video_path=out_video_multiblur,
        mode="replace",
        blur_objects=blur_objects,
    )

    print("Multi-object blur execution result:", ok)
    assert ok is True, "mix_audio_with_video returned False"
    assert os.path.exists(out_video_multiblur), "Output video file was not created"

    info = get_media_info(out_video_multiblur)
    print("Multi-blur output media info:", info)
    assert info.get("has_video") is True, "Missing video stream"
    assert info.get("has_audio") is True, "Missing audio stream"

    print("\nSUCCESS: Multi-object blur & mosaic pipeline validated!")

if __name__ == "__main__":
    run_test()
