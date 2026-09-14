"""Spring 백엔드에 /v1/analyze 계약을 제공하는 게이트웨이.

로컬 VLM 노드(`app.local.serve`, Tailscale 같은 사설망 너머에 떠 있음)를
`LocalProxyBackend`로 우선 호출하고, 노드가 죽어 있거나 응답이 없으면
mock 백엔드로 자동 폴백한다. Spring은 이 서버의 URL만 `vlm.server.url`로
바라보면 되고, 로컬 노드 주소가 바뀌어도 `LOCAL_BASE_URL` 환경변수만
바꾸면 된다 (mock 서버와 동일한 응답 계약을 유지하기 때문).

실행:
    uvicorn app.local.serve:app --host 0.0.0.0 --port 8100

주요 환경변수:
    LOCAL_BASE_URL          로컬 VLM 노드 주소. 예) http://100.x.x.x:8100 (Tailscale)
    LN_API_KEY              로컬 노드가 X-Local-Key 인증을 요구할 때 함께 설정
    GATEWAY_FALLBACK_ENABLED  "false"로 두면 로컬 노드 실패 시 폴백 없이 503 반환 (기본 true)
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.backends.local import LocalProxyBackend
from app.backends.mock import MockBackend, pick_scenario
from app.local.ollama_client import OllamaError, OllamaTimeout, OllamaUnreachable
from app.postprocess import to_response, verify
from app.prompt import build_prompt
from app.schemas import VLMResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gateway")

app = FastAPI(
    title="Safety VLM Gateway",
    version="1.0",
    description="Spring 백엔드용 /v1/analyze를 제공하고, 로컬 VLM 노드가 죽으면 mock으로 폴백한다.",
)

_FALLBACK_ENABLED = os.getenv("GATEWAY_FALLBACK_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# 로컬 노드(사설망 너머)를 부르는 어댑터. base_url은 LOCAL_BASE_URL 환경변수로 설정.
_primary = LocalProxyBackend()

_state = {"served": 0, "fallback_served": 0, "started_at": time.time()}

_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"BM")


def _looks_like_image(raw: bytes) -> bool:
    if raw.startswith(_MAGIC):
        return True
    return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"


async def _read_image(image: UploadFile) -> bytes:
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty image")
    if not _looks_like_image(raw):
        raise HTTPException(415, "unsupported image format")
    return raw


@app.post("/v1/analyze", response_model=VLMResponse)
async def analyze(
    image: UploadFile = File(...),
    delay: float | None = Form(None),  # Spring은 항상 0을 보내지만 mock 서버와 계약을 맞추기 위해 받아둠
):
    """Spring 백엔드가 호출하는 계약. 로컬 VLM 노드를 우선 호출하고, 실패 시 mock으로 폴백한다."""
    raw = await _read_image(image)
    prompt = build_prompt()

    used = "local"
    try:
        internal = await _primary.analyze(raw, prompt)
    except (OllamaUnreachable, OllamaTimeout, OllamaError) as e:
        if not _FALLBACK_ENABLED:
            log.error("로컬 VLM 노드 실패, 폴백 비활성화 상태라 그대로 에러 반환: %s", e)
            raise HTTPException(503, f"local vlm node unavailable: {e}") from e

        log.warning("로컬 VLM 노드 실패, mock으로 폴백: %s", e)
        used = "mock-fallback"
        _state["fallback_served"] += 1
        scenario = pick_scenario(raw)
        internal = await MockBackend(scenario=scenario, latency=(0, 0)).analyze(raw, prompt)

    checked, hallucinated = verify(internal)
    if hallucinated:
        log.warning("[%s] 관찰되지 않은 물체가 reasoning에 등장: %s", used, hallucinated)

    _state["served"] += 1
    log.info(
        "served #%d via=%s hazard=%s severity=%s",
        _state["served"],
        used,
        checked.hazard_detected,
        checked.severity,
    )
    return to_response(checked)


@app.get("/health")
async def health():
    """게이트웨이 자체 상태와 로컬 노드 도달 가능 여부를 나눠서 보여준다."""
    local_ok = await _primary.health()
    return {
        # 폴백이 켜져 있으면 로컬 노드가 죽어도 게이트웨이는 계속 200을 반환한다.
        "ok": True,
        "node": "gateway",
        "local_base_url": _primary.base_url,
        "local_node_reachable": local_ok,
        "fallback_enabled": _FALLBACK_ENABLED,
        "requests_ok": _state["served"],
        "fallback_served": _state["fallback_served"],
        "uptime_s": round(time.time() - _state["started_at"], 1),
    }


@app.get("/")
async def index():
    return {
        "service": "safety-vlm-gateway",
        "note": "로컬 VLM 노드를 우선 호출하고, 실패하면 mock으로 자동 폴백합니다.",
        "local_base_url": _primary.base_url,
        "fallback_enabled": _FALLBACK_ENABLED,
        "endpoints": {
            "POST /v1/analyze": "Spring용 응답 (로컬 노드 우선, 실패 시 mock 폴백)",
            "GET /health": "게이트웨이 및 로컬 노드 상태",
            "GET /docs": "Swagger UI",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8100")))
