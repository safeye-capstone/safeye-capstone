"""백엔드 개발용 VLM 목 서버.

실제 경량화 모델이 준비되기 전까지 Spring/백엔드가 붙을 수 있는 서버.
나중에 진짜 게이트웨이나 로컬 VLM 노드가 붙어도 URL만 바꾸면 되도록 같은 계약을 유지한다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

from app.backends.mock import FIXTURES, FailingMock, MockBackend, pick_scenario
from app.postprocess import to_response, verify
from app.schemas import VLMInternal, VLMResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mock-server")

app = FastAPI(
    title="Safety VLM Mock Server",
    version="1.0",
    description="경량화 모델이 준비되기 전까지 쓰는 Safety VLM 목 서버",
)

_API_KEY = os.getenv("LN_API_KEY", "")

_state = {
    "scenario": os.getenv("MOCK_SCENARIO") or None,
    "fail": os.getenv("MOCK_FAIL") or None,
    "fail_rate": float(os.getenv("MOCK_FAIL_RATE", "0")),
    "served": 0,
    "started_at": time.time(),
}

_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"BM")


def _looks_like_image(raw: bytes) -> bool:
    if raw.startswith(_MAGIC):
        return True
    return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"


def _auth(key: str | None) -> None:
    if _API_KEY and key != _API_KEY:
        raise HTTPException(401, "bad key")


async def _read_image(image: UploadFile) -> bytes:
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty image")
    if not _looks_like_image(raw):
        raise HTTPException(415, "unsupported image format")
    return raw


async def _sleep(delay: float | None) -> None:
    if delay is not None:
        if delay > 0:
            await asyncio.sleep(delay)
        return
    lo = float(os.getenv("MOCK_LATENCY_MIN", "8"))
    hi = float(os.getenv("MOCK_LATENCY_MAX", "20"))
    if hi > 0:
        await asyncio.sleep(random.uniform(min(lo, hi), hi))


async def _maybe_fail(mode: str | None) -> None:
    """요청 단위 또는 전역 설정으로 실패를 흉내 낸다."""
    if not mode and _state["fail_rate"] and random.random() < _state["fail_rate"]:
        mode = "error"
    if not mode:
        return
    if mode not in FailingMock.MODES:
        raise HTTPException(400, f"unknown fail mode: {mode} / {list(FailingMock.MODES)}")

    log.info("injecting failure mode=%s", mode)
    try:
        await FailingMock(mode).analyze(b"", "")
    except ConnectionError as e:
        raise HTTPException(503, f"analysis unavailable: {e}") from e
    except ValueError as e:
        raise HTTPException(502, f"analysis unavailable: {e}") from e
    except Exception as e:
        raise HTTPException(503, f"analysis unavailable: {e}") from e


def _resolve_scenario(raw: bytes, want: str | None) -> str:
    want = want or _state["scenario"]
    if want and want not in FIXTURES:
        raise HTTPException(400, f"unknown scenario: {want} / {list(FIXTURES)}")
    return want or pick_scenario(raw)


async def _internal(raw: bytes, want: str | None) -> VLMInternal:
    key = _resolve_scenario(raw, want)
    data = await MockBackend(scenario=key, latency=(0, 0)).analyze(raw, "")
    _state["served"] += 1
    log.info("served #%d scenario=%s bytes=%d", _state["served"], key, len(raw))
    return data


@app.post("/v1/analyze", response_model=VLMResponse)
async def analyze(
    image: UploadFile = File(...),
    mock_mode: str | None = Form(None),
    scenario: str | None = Form(None),
    delay: float | None = Form(None),
):
    """Spring/백엔드가 바로 붙는 응답 계약."""
    raw = await _read_image(image)
    await _maybe_fail(mock_mode)
    await _sleep(delay)

    internal = await _internal(raw, scenario)
    checked, _ = verify(internal)
    return to_response(checked)


@app.post("/v1/analyze_internal", response_model=VLMInternal)
async def analyze_internal(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    scenario: str | None = Form(None),
    fail: str | None = Form(None),
    delay: float | None = Form(None),
    x_local_key: str | None = Header(default=None),
    x_mock_scenario: str | None = Header(default=None),
    x_mock_fail: str | None = Header(default=None),
):
    """게이트웨이와 로컬 VLM 노드가 공유하는 내부 응답 계약."""
    _auth(x_local_key)
    raw = await _read_image(image)
    await _maybe_fail(fail or x_mock_fail or _state["fail"])
    await _sleep(delay)
    return await _internal(raw, scenario or x_mock_scenario)


@app.get("/")
async def index():
    return {
        "service": "safety-vlm-mock",
        "note": "경량화 모델 준비 전까지 쓰는 임시 서버입니다.",
        "endpoints": {
            "POST /v1/analyze": "Spring용 응답",
            "POST /v1/analyze_internal": "게이트웨이용 VLMInternal 응답",
            "GET /v1/scenarios": "목 응답 시나리오 목록",
            "GET /health": "상태 확인",
            "GET /docs": "Swagger UI",
        },
        "form_fields": {
            "image": "required",
            "scenario": "CRITICAL | WARNING | INFO | CRITICAL_PINCH | LOW_CONFIDENCE | EMPTY_SCENE",
            "mock_mode": list(FailingMock.MODES),
            "delay": "seconds; 0 means immediate response",
        },
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "node": "mock",
        "model": "mock",
        "ollama": True,
        "vram_mb": 0.0,
        "inflight_waiting": 0,
        "uptime_s": round(time.time() - _state["started_at"], 1),
    }


@app.get("/metrics")
async def metrics():
    return {
        "model": "mock",
        "requests_ok": _state["served"],
        "scenario_pinned": _state["scenario"],
        "fail_pinned": _state["fail"],
        "fail_rate": _state["fail_rate"],
    }


@app.get("/v1/scenarios")
async def scenarios():
    out = {}
    for key, fixture in FIXTURES.items():
        response = to_response(fixture.model_copy(deep=True))
        out[key] = {
            "is_danger": response.is_danger,
            "severity": response.severity,
            "action_guide": response.action_guide,
            "violated_regulation": response.violated_regulation,
            "vlm_description": response.vlm_description,
        }
    return out


@app.post("/admin/scenario")
async def set_scenario(
    scenario: str | None = Form(None),
    fail: str | None = Form(None),
    fail_rate: float | None = Form(None),
    x_local_key: str | None = Header(default=None),
):
    """데모 중 특정 응답이나 실패 모드를 고정할 때 쓴다."""
    _auth(x_local_key)
    if scenario is not None:
        if scenario and scenario not in FIXTURES:
            raise HTTPException(400, f"unknown scenario: {scenario}")
        _state["scenario"] = scenario or None
    if fail is not None:
        _state["fail"] = fail or None
    if fail_rate is not None:
        _state["fail_rate"] = fail_rate
    return _state


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8100")))
