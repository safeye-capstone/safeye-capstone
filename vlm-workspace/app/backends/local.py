"""게이트웨이에서 로컬 VLM을 호출하기 위한 백엔드 어댑터.

`LocalBackend`는 게이트웨이와 Ollama가 같은 장비에 있을 때 직접 호출.
`LocalProxyBackend`는 Tailscale 같은 사설망 너머의 로컬 FastAPI 노드를 호출.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.config import settings
from app.local.config import local_settings as local_cfg
from app.schemas import INTERNAL_JSON_SCHEMA, VLMInternal
from app.local.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaTimeout,
    OllamaUnreachable,
    create_vlm_client,
)

log = logging.getLogger(__name__)

_LOCAL_KEY = os.getenv("LN_API_KEY", "")


class LocalBackend:
    """게이트웨이와 Ollama가 같은 장비에 있을 때 쓰는 직접 호출 백엔드."""

    name = "local"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.local_model
        if local_cfg.vlm_provider == "gemini":
            self.client = create_vlm_client()
        else:
            self.client = OllamaClient(
                base_url=self.base_url,
                model=self.model,
                connect_timeout=settings.local_connect_timeout,
                read_timeout=settings.local_read_timeout,
                num_predict=settings.max_output_tokens,
                temperature=settings.temperature,
            )

    async def analyze(self, image_bytes: bytes, prompt: str) -> VLMInternal:
        obj, timing = await self.client.chat_json(
            image_bytes,
            prompt,
            INTERNAL_JSON_SCHEMA,
        )
        log.info(
            "local prefill=%.0fms decode=%.0fms %.1ftok/s vis_tok=%d",
            timing.prompt_eval_ms,
            timing.eval_ms,
            timing.decode_tps,
            timing.prompt_tokens,
        )
        return VLMInternal.model_validate(obj)

    async def health(self) -> bool:
        return await self.client.alive()


class LocalProxyBackend(LocalBackend):
    """게이트웨이가 로컬 FastAPI 노드의 `/v1/analyze_internal`을 호출하는 백엔드."""

    name = "local"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        super().__init__(base_url or settings.local_base_url, model)

    def _headers(self) -> dict:
        return {"X-Local-Key": _LOCAL_KEY} if _LOCAL_KEY else {}

    async def analyze(self, image_bytes: bytes, prompt: str) -> VLMInternal:
        try:
            async with httpx.AsyncClient(timeout=self.client.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/analyze_internal",
                    files={"image": ("img.jpg", image_bytes, "image/jpeg")},
                    data={"prompt": prompt},
                    headers=self._headers(),
                )
                response.raise_for_status()
                return VLMInternal.model_validate(response.json())
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaUnreachable(f"local node unreachable: {self.base_url}") from e
        except httpx.ReadTimeout as e:
            raise OllamaTimeout("local node read timeout") from e
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 429:
                raise OllamaError("local node queue is full") from e
            raise OllamaError(f"local node HTTP {code}: {e.response.text[:200]}") from e

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=settings.local_connect_timeout
            ) as client:
                response = await client.get(f"{self.base_url}/health", headers=self._headers())
                return response.status_code == 200 and bool(response.json().get("ok"))
        except Exception:
            return False
