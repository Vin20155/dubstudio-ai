"""
Unit and Integration Test Suite for CodeCraft API Translation Provider.
Tests CodeCraftProvider metadata, registration, response parsing, credential validation,
mock API execution, and FastAPI endpoint integration.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.translation import (
    CodeCraftProvider,
    ErrorCode,
    TranslationSegment,
    TranslationService,
    get_translation_service,
)
from backend.main import app
from fastapi.testclient import TestClient


class TestCodeCraftProvider(unittest.TestCase):
    def setUp(self):
        self.provider = CodeCraftProvider(api_key="cc_test_secret_key_12345")

    def test_provider_metadata(self):
        self.assertEqual(self.provider.get_name(), "codecraft")
        self.assertEqual(self.provider.get_display_name(), "CodeCraft API")
        self.assertIn("gemini-3-flash", self.provider.get_supported_models())
        self.assertIn("gemini-3.7-flash", self.provider.get_supported_models())
        self.assertIn("claude-3-5-sonnet-20241022", self.provider.get_supported_models())
        self.assertEqual(self.provider.get_default_model(), "claude-3-5-sonnet-20241022")

    def test_registered_in_service(self):
        service = get_translation_service()
        registered = service.get_provider("codecraft")
        self.assertIsInstance(registered, CodeCraftProvider)
        self.assertEqual(registered.get_name(), "codecraft")

        catalog = service.list_providers()
        ids = [p["id"] for p in catalog]
        self.assertIn("codecraft", ids)

    def test_connection_without_key(self):
        prov = CodeCraftProvider(api_key="")
        res = prov.test_connection()
        self.assertFalse(res["success"])
        self.assertIn("not configured", res["message"].lower())

    def test_parse_response_clean_json(self):
        sample = json.dumps([
            {"id": 1, "khmer_text": "សួស្តីពិភពលោក", "tone": "friendly"},
            {"id": 2, "khmer_text": "សុខសប្បាយជាទេ?", "tone": "neutral"},
        ])
        parsed = self.provider._parse_response(sample)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["khmer_text"], "សួស្តីពិភពលោក")

    def test_parse_response_markdown_fences(self):
        sample = "```json\n" + json.dumps([
            {"id": 1, "khmer_text": "អរគុណច្រើន"}
        ]) + "\n```"
        parsed = self.provider._parse_response(sample)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["khmer_text"], "អរគុណច្រើន")

    def test_parse_response_object_with_segments(self):
        sample = json.dumps({
            "segments": [
                {"id": 1, "khmer_text": "ទៅណា?", "tone": "casual"}
            ]
        })
        parsed = self.provider._parse_response(sample)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["khmer_text"], "ទៅណា?")

    def test_parse_response_regex_fallback(self):
        sample = 'Here is the translation: {"id": 1, "khmer_text": "ប្រយ័ត្ន!"} Done.'
        parsed = self.provider._parse_response(sample)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["khmer_text"], "ប្រយ័ត្ន!")

    @patch("urllib.request.urlopen")
    def test_connection_success_mock(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "data": [
                {"id": "claude-3-5-sonnet-20241022"},
                {"id": "deepseek-chat"},
                {"id": "gpt-4o"},
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.provider.test_connection({"codecraft_api_key": "cc_valid_token"})
        self.assertTrue(res["success"])
        self.assertIn("Connected to CodeCraft API", res["message"])
        self.assertIn("deepseek-chat", res["models"])

    @patch("urllib.request.urlopen")
    def test_translate_execution_mock(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [
                {
                    "message": {
                        "content": json.dumps([
                            {"id": 1, "khmer_text": "ជំរាបសួរលោកអ្នក", "tone": "polite"},
                            {"id": 2, "khmer_text": "សូមស្វាគមន៍", "tone": "warm"}
                        ])
                    }
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        segments = [
            TranslationSegment(id=1, start=0.0, end=2.0, source_text="Hello everyone"),
            TranslationSegment(id=2, start=2.0, end=4.0, source_text="Welcome"),
        ]

        result = self.provider.translate(
            segments=segments,
            options={"api_key": "cc_test_key", "model": "claude-3-5-sonnet-20241022"}
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider, "codecraft")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0].khmer_text, "ជំរាបសួរលោកអ្នក")
        self.assertEqual(result.segments[1].khmer_text, "សូមស្វាគមន៍")

    def test_fastapi_endpoints_integration(self):
        client = TestClient(app)

        # 1. Verify codecraft appears in translation providers catalog
        resp = client.get("/api/translation/providers")
        self.assertEqual(resp.status_code, 200)
        providers = resp.json().get("providers", [])
        codecraft_info = next((p for p in providers if p["id"] == "codecraft"), None)
        self.assertIsNotNone(codecraft_info)
        self.assertEqual(codecraft_info["name"], "CodeCraft API")

        # 2. Test saving settings with CodeCraft credentials
        settings_payload = {
            "provider": "codecraft",
            "model": "claude-3-5-sonnet-20241022",
            "fallback_provider": "gemini",
            "fallback_enabled": True,
            "credentials": {
                "codecraft_api_key": "cc_integration_test_key",
                "codecraft_base_url": "https://codecraftapi.com/v1"
            }
        }
        put_resp = client.put("/api/translation/settings", json=settings_payload)
        self.assertEqual(put_resp.status_code, 200)
        saved = put_resp.json().get("settings", {})
        self.assertEqual(saved.get("provider"), "codecraft")
        self.assertEqual(saved.get("credentials", {}).get("codecraft_api_key"), "cc_integration_test_key")


if __name__ == "__main__":
    unittest.main()
