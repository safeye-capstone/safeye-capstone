from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from app.local import ollama_client as client_module


class _FakeResponse:
    status_code = 200
    is_success = True
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"scene_description":"정상"}'}]
                }
            }]
        }


class _FakeHttpClient:
    request = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        type(self).request = {"url": url, **kwargs}
        return _FakeResponse()


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        self.gemini_cfg = replace(
            client_module.cfg,
            vlm_provider="gemini",
            gemini_api_key="test-key",
            gemini_base_url="https://gemini.example/v1beta",
            gemini_model="gemini-test",
            gemini_max_output_tokens=321,
        )

    def test_provider_factory_selects_gemini(self):
        with patch.object(client_module, "cfg", self.gemini_cfg):
            provider = client_module.create_image_vlm_provider()
        self.assertIsInstance(provider, client_module.GeminiImageProvider)

    def test_request_gemini_normalizes_response_to_existing_contract(self):
        with (
            patch.object(client_module, "cfg", self.gemini_cfg),
            patch.object(client_module.httpx, "Client", _FakeHttpClient),
        ):
            response = client_module.request_gemini(
                Path("frame.jpg"),
                "aW1hZ2U=",
                "이미지를 분석하세요.",
                attempt=1,
            )

        self.assertEqual(response["model"], "gemini-test")
        self.assertEqual(response["response"], '{"scene_description":"정상"}')
        self.assertTrue(response["done"])
        self.assertEqual(
            _FakeHttpClient.request["url"],
            "https://gemini.example/v1beta/models/gemini-test:generateContent",
        )
        self.assertEqual(
            _FakeHttpClient.request["headers"],
            {"x-goog-api-key": "test-key"},
        )
        config = _FakeHttpClient.request["json"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["maxOutputTokens"], 321)
        self.assertEqual(config["responseJsonSchema"], client_module.VLM_SCHEMA)


if __name__ == "__main__":
    unittest.main()
