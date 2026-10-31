import unittest
from backend.tts_engine import (
    extract_emotional_tags,
    format_speech_text_for_natural_pacing,
    resolve_voice_params,
    EMOTION_SPECS,
    PACING_SPECS,
)
from fastapi.testclient import TestClient
from backend.main import app


class TestEmotionalSSMLAndVoiceToneModulation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_extract_english_emotional_tags(self):
        sample = "[Whisper] [Pacing: Slow] Don't make a sound, they are listening."
        res = extract_emotional_tags(sample)
        self.assertEqual(res["emotion"], "whisper")
        self.assertEqual(res["pacing"], "slow")
        self.assertEqual(res.emotion, "whisper")
        self.assertEqual(res.pacing, "slow")
        self.assertEqual(res["clean_text"], "Don't make a sound, they are listening.")

    def test_extract_khmer_emotional_tags(self):
        sample = "[ខ្សឹប] [យឺត] កុំនិយាយឮពេក ប្រយ័ត្នគេដឹង"
        res = extract_emotional_tags(sample)
        self.assertEqual(res["emotion"], "whisper")
        self.assertEqual(res["pacing"], "slow")
        self.assertEqual(res.clean_text, "កុំនិយាយឮពេក ប្រយ័ត្នគេដឹង")

    def test_extract_angry_and_urgent_tags(self):
        sample = "[Angry] [Pacing: Urgent] Get out of here right now!"
        res = extract_emotional_tags(sample)
        self.assertEqual(res["emotion"], "angry")
        self.assertEqual(res["pacing"], "urgent")
        self.assertEqual(res.clean_text, "Get out of here right now!")

    def test_extract_numeric_pitch_and_rate_overrides(self):
        sample = "[Pitch: +4Hz] [Rate: +15%] [Volume: +3dB] Fast high voice"
        res = extract_emotional_tags(sample)
        self.assertEqual(res["pitch_offset"], 4)
        self.assertEqual(res["rate_offset"], 15)
        self.assertEqual(res["volume_offset"], 3)
        self.assertEqual(res.clean_text, "Fast high voice")

    def test_clean_text_preserves_untagged_content(self):
        sample = "សួស្តីបងប្អូនទាំងអស់គ្នា ថ្ងៃនេះខ្ញុំមានដំណឹងល្អ"
        res = extract_emotional_tags(sample)
        self.assertIsNone(res["emotion"])
        self.assertIsNone(res["pacing"])
        self.assertEqual(res.clean_text, sample)

    def test_format_speech_text_for_natural_pacing(self):
        raw = "សួស្តី... ឈប់សិន! ទៅណា?"
        formatted = format_speech_text_for_natural_pacing(raw)
        self.assertIn("...", formatted)
        self.assertFalse(formatted.startswith(" "))

    def test_resolve_voice_params_whisper_and_slow(self):
        res = resolve_voice_params(
            base_rate="+0%",
            base_pitch="+0Hz",
            base_volume="+60%",
            emotion="whisper",
            pacing="slow"
        )
        # whisper is -4% rate, slow is -8% rate => -12%
        self.assertIn("-12%", res.rate)
        # whisper is -1Hz pitch
        self.assertIn("-1Hz", res.pitch)
        # whisper is -6% volume => +54%
        self.assertIn("+54%", res.volume)
        self.assertEqual(res.emotion, "whisper")
        self.assertEqual(res.pacing, "slow")

    def test_resolve_voice_params_angry_and_urgent(self):
        res = resolve_voice_params(
            base_rate="+0%",
            base_pitch="+0Hz",
            base_volume="+60%",
            emotion="angry",
            pacing="urgent"
        )
        # angry rate_delta=6, urgent=15 => +21%
        self.assertIn("+21%", res.rate)
        # angry pitch_delta=3 => +3Hz
        self.assertIn("+3Hz", res.pitch)
        # angry volume_delta=8 => +68%
        self.assertIn("+68%", res.volume)
        self.assertEqual(res.emotion, "angry")
        self.assertEqual(res.pacing, "urgent")

    def test_all_10_emotions_in_specs(self):
        expected_emotions = {
            "neutral", "whisper", "angry", "sad", "excited",
            "terrified", "romantic", "suspense", "sarcastic", "exhausted"
        }
        self.assertTrue(expected_emotions.issubset(set(EMOTION_SPECS.keys())))

    def test_all_pacing_options_in_specs(self):
        expected_pacing = {"normal", "fast", "slow", "urgent"}
        self.assertTrue(expected_pacing.issubset(set(PACING_SPECS.keys())))

    def test_api_detect_emotions_endpoint(self):
        payload = {
            "session_id": "test_session",
            "segments": [
                {
                    "id": 1,
                    "text": "Get out of here immediately!!",
                    "khmer_text": "[ខឹង] [លឿន] ចេញពីទីនេះភ្លាម!",
                    "speaker": "Speaker 1"
                },
                {
                    "id": 2,
                    "text": "Shh, speak quietly, don't let them hear...",
                    "khmer_text": "កុំមាត់ ខ្សឹបតិចៗ...",
                    "speaker": "Speaker 2"
                },
                {
                    "id": 3,
                    "text": "I feel so exhausted and tired today.",
                    "khmer_text": "ថ្ងៃនេះអស់កម្លាំងខ្លាំងណាស់",
                    "speaker": "Speaker 1"
                }
            ]
        }
        response = self.client.post("/api/tts/detect-emotions", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        segs = data.get("segments", [])
        self.assertEqual(len(segs), 3)

        # Segment 1 should be angry / fast or urgent
        self.assertEqual(segs[0]["emotion"], "angry")
        self.assertIn(segs[0]["pacing"], ["fast", "urgent"])
        # Bracket tag was stripped
        self.assertNotIn("[ខឹង]", segs[0]["khmer_text"])

        # Segment 2 should be whisper / slow
        self.assertEqual(segs[1]["emotion"], "whisper")
        self.assertEqual(segs[1]["pacing"], "slow")

        # Segment 3 should be exhausted
        self.assertEqual(segs[2]["emotion"], "exhausted")

    def test_api_detect_emotions_empty_payload(self):
        response = self.client.post("/api/tts/detect-emotions", json={"segments": []})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
