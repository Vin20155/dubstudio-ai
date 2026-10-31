import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.audio_video_processor import _compute_safe_boxblur_arg


class TestSafeBoxBlur(unittest.TestCase):
    def test_user_failing_case_thin_crop(self):
        # User error: crop height approx 26-48px on 1080p/1920p video
        # Input bh = 0.0260 on 1080p or 1920p
        # On 1920p: h = 48px, chroma h = 24px, max chroma radius = 12
        arg = _compute_safe_boxblur_arg(strength_raw=50, box_w_px=958, box_h_px=48)
        parts = arg.split(":")
        self.assertEqual(len(parts), 4, f"Expected lr:lp:cr:cp format, got {arg}")
        lr, lp, cr, cp = map(int, parts)
        self.assertLessEqual(cr, 12, "Chroma radius must be <= 12 to satisfy FFmpeg constraint")
        self.assertGreaterEqual(cr, 0, "Chroma radius must be >= 0")
        self.assertLessEqual(lr, 24, "Luma radius must be <= 24")

    def test_very_thin_crop(self):
        # 28px height (bh=0.026 on 1080p)
        arg = _compute_safe_boxblur_arg(strength_raw=50, box_w_px=800, box_h_px=28)
        lr, lp, cr, cp = map(int, arg.split(":"))
        self.assertLessEqual(cr, 6, "Chroma radius must be <= 6 for 28px height")
        self.assertGreaterEqual(cr, 0)

    def test_extreme_micro_crop(self):
        # 10px height
        arg = _compute_safe_boxblur_arg(strength_raw=50, box_w_px=100, box_h_px=10)
        lr, lp, cr, cp = map(int, arg.split(":"))
        self.assertLessEqual(cr, 2)
        self.assertGreaterEqual(cr, 0)
        self.assertLessEqual(lr, 4)

    def test_large_full_hd_canvas(self):
        # 1080x1920 canvas blur
        arg = _compute_safe_boxblur_arg(strength_raw=50, box_w_px=1080, box_h_px=1920)
        lr, lp, cr, cp = map(int, arg.split(":"))
        self.assertEqual(lr, 15)
        self.assertEqual(cr, 15)
        self.assertEqual(lp, 3)
        self.assertEqual(cp, 3)


if __name__ == "__main__":
    unittest.main()
