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
        
    def test_request_gemini_uses_configured_temperature_on_every_attempt(self):
        zero_cfg = replace(self.gemini_cfg, temperature=0.0)
        for attempt in (1, 3):
            with (
                patch.object(client_module, "cfg", zero_cfg),
                patch.object(client_module.httpx, "Client", _FakeHttpClient),
            ):
                client_module.request_gemini(
                    Path("frame.jpg"), "aW1hZ2U=", "프롬프트", attempt=attempt
                )
            config = _FakeHttpClient.request["json"]["generationConfig"]
            self.assertEqual(config["temperature"], 0.0, f"attempt={attempt}")


class _FakeAsyncResponse:
    def __init__(self, text: str):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


class _FakeAsyncHttpClient:
    request = None
    response_text = "{}"

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        type(self).request = {"url": url, **kwargs}
        return _FakeAsyncResponse(type(self).response_text)


class GeminiChatJsonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = client_module.GeminiClient(
            base_url="https://gemini.example/v1beta",
            api_key="test-key",
            model="gemini-test",
        )
        self.schema = {
            "type": "object",
            "properties": {"hazard_detected": {"type": "boolean"}},
            "required": ["hazard_detected"],
        }

    async def test_chat_json_sends_the_schema_it_validates_against(self):
        _FakeAsyncHttpClient.response_text = '{"hazard_detected": true}'
        with patch.object(client_module.httpx, "AsyncClient", _FakeAsyncHttpClient):
            parsed, _ = await self.client.chat_json(b"img", "프롬프트", self.schema)

        sent = _FakeAsyncHttpClient.request["json"]["generationConfig"]
        self.assertEqual(sent["responseJsonSchema"], self.schema)
        self.assertEqual(parsed, {"hazard_detected": True})

    async def test_chat_json_rejects_response_missing_required_keys(self):
        _FakeAsyncHttpClient.response_text = '{"other": 1}'
        with patch.object(client_module.httpx, "AsyncClient", _FakeAsyncHttpClient):
            with self.assertRaises(client_module.OllamaBadJSON):
                await self.client.chat_json(b"img", "프롬프트", self.schema)

    async def test_chat_json_accepts_internal_schema_used_by_local_node(self):
        from app.schemas import INTERNAL_JSON_SCHEMA

        _FakeAsyncHttpClient.response_text = (
            "{" + ",".join(f'"{key}": null' for key in INTERNAL_JSON_SCHEMA["required"]) + "}"
        )
        with patch.object(client_module.httpx, "AsyncClient", _FakeAsyncHttpClient):
            await self.client.chat_json(b"img", "프롬프트", INTERNAL_JSON_SCHEMA)

if __name__ == "__main__":
    unittest.main()
