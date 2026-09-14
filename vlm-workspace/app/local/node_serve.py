"""로컬 VLM 노드 서버.

Ollama는 로컬 루프백에만 두고, 외부에서는 이 FastAPI 서버만 보게 함.
이렇게 두면 모델 관리 API가 밖으로 열리지 않고,
게이트웨이는 `/v1/analyze_internal`만 호출.

실행:
    uvicorn app.local.node_serve:app --host 0.0.0.0 --port 8100
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import ValidationError

from app.prompt import build_prompt
from app.schemas import INTERNAL_JSON_SCHEMA, VLMInternal
from app.local.config import local_settings as cfg
from app.local.imageops import clamp
from app.local.ollama_client import (
    OllamaBadJSON,
    OllamaClient,
    OllamaTimeout,
    OllamaUnreachable,
)

log = logging.getLogger("local-node")
logging.basicConfig(level=logging.INFO)


class Runtime:
    """요청 사이에 공유되는 모델 클라이언트와 간단한 지표."""

    def __init__(self):
        self.client = self._build(cfg.model)
        self.sem = asyncio.Semaphore(cfg.concurrency)
        self.waiting = 0
        self.lat = deque(maxlen=200)
        self.n_ok = 0
        self.n_fail = 0
        self.n_json_retry = 0

    @staticmethod
    def _build(model: str) -> OllamaClient:
        return OllamaClient(
            base_url=cfg.ollama_base_url,
            model=model,
            connect_timeout=cfg.connect_timeout,
            read_timeout=cfg.read_timeout,
            keep_alive=cfg.keep_alive,
            num_ctx=cfg.num_ctx,
            num_predict=cfg.num_predict,
            temperature=cfg.temperature,
        )

    async def swap(self, model: str) -> None:
        old = self.client
        self.client = self._build(model)
        try:
            await old.unload()
        except Exception as e:
            log.warning("old model unload failed; continuing: %s", e)
        await self.client.warmup()

    def stats(self) -> dict:
        s = sorted(self.lat)
        return {
            "model": self.client.model,
            "requests_ok": self.n_ok,
            "requests_failed": self.n_fail,
            "json_retries": self.n_json_retry,
            "inflight_waiting": self.waiting,
            "p50_ms": round(statistics.median(s), 1) if s else None,
            "p95_ms": round(s[max(0, int(len(s) * 0.95) - 1)], 1) if s else None,
            "max_ms": round(max(s), 1) if s else None,
            "n_sampled": len(s),
        }


rt = Runtime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if cfg.warmup_on_start:
        try:
            ms = await rt.client.warmup()
            log.info("warmup complete model=%s load=%.0fms", rt.client.model, ms)
        except Exception as e:
            # 서버는 띄워둔다. /health가 false를 주면 게이트웨이가 우회할 수 있다.
            log.warning("warmup failed; server stays up: %s", e)
    yield


app = FastAPI(title="Local VLM Node", version="1.0", lifespan=lifespan)


def auth(x_local_key: str | None = Header(default=None)):
    """`LN_API_KEY`가 비어 있으면 인증 없이 받는다."""
    if cfg.api_key and x_local_key != cfg.api_key:
        raise HTTPException(401, "bad key")


@app.post("/v1/analyze_internal", response_model=VLMInternal, dependencies=[Depends(auth)])
async def analyze_internal(
    image: UploadFile = File(...),
    prompt: str = Form(""),
):
    """게이트웨이의 LocalProxyBackend가 호출하는 내부 분석 계약."""
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty image")
    if len(raw) > cfg.max_upload_bytes:
        raise HTTPException(413, f"image too large: {len(raw)}B")

    try:
        img, meta = clamp(raw, cfg.max_edge)
    except Exception:
        raise HTTPException(415, "unsupported image format")

    # 오래 기다리게 두기보다 429를 빨리 돌려 게이트웨이가 다른 경로를 고르게 한다.
    if rt.waiting >= cfg.queue_limit:
        raise HTTPException(429, f"queue full ({rt.waiting})")

    text = prompt or build_prompt()
    t0 = time.perf_counter()
    rt.waiting += 1
    try:
        async with rt.sem:
            data, timing = await _infer(img, text)
    except OllamaUnreachable as e:
        rt.n_fail += 1
        raise HTTPException(503, f"ollama unreachable: {e}")
    except OllamaTimeout as e:
        rt.n_fail += 1
        raise HTTPException(504, f"ollama timeout: {e}")
    except OllamaBadJSON as e:
        rt.n_fail += 1
        raise HTTPException(502, f"schema violation: {e}")
    except ValidationError as e:
        rt.n_fail += 1
        raise HTTPException(502, f"schema validation failed: {e.error_count()} errors")
    finally:
        rt.waiting -= 1

    ms = (time.perf_counter() - t0) * 1000
    rt.lat.append(ms)
    rt.n_ok += 1
    log.info(
        "ok %.0fms | %dx%d(%s) | prefill=%.0fms decode=%.0fms %.1ftok/s | vis_tok=%d",
        ms,
        meta["w"],
        meta["h"],
        "resized" if meta["resized"] else "as-is",
        timing.prompt_eval_ms,
        timing.eval_ms,
        timing.decode_tps,
        timing.prompt_tokens,
    )
    return data


async def _infer(img: bytes, prompt: str):
    """스키마가 깨질 때만 정해진 횟수만큼 다시 시도한다."""
    retries = max(0, cfg.json_retry)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            obj, timing = await rt.client.chat_json(img, prompt, INTERNAL_JSON_SCHEMA)
            return VLMInternal.model_validate(obj), timing
        except (OllamaBadJSON, ValidationError) as e:
            last = e
            if attempt < retries:
                rt.n_json_retry += 1
                log.warning("schema retry %d/%d: %s", attempt + 1, retries, e)
    if last:
        raise last
    raise OllamaBadJSON("inference failed without an exception")


@app.get("/health")
async def health():
    """FastAPI만 살아 있는지와 Ollama까지 살아 있는지를 나눠서 보여준다."""
    ollama = await rt.client.alive()
    return {
        "ok": ollama,
        "node": "local",
        "model": rt.client.model,
        "ollama": ollama,
        "vram_mb": await rt.client.loaded_vram_mb() if ollama else 0.0,
        "inflight_waiting": rt.waiting,
    }


@app.get("/metrics")
async def metrics():
    return rt.stats()


@app.get("/model/info")
async def model_info():
    """설치된 모델과 현재 VRAM에 올라간 모델을 확인한다."""
    installed = [
        {
            "name": m.get("name"),
            "size_gb": round(float(m.get("size", 0)) / 1e9, 2),
            "params": (m.get("details") or {}).get("parameter_size"),
            "quant": (m.get("details") or {}).get("quantization_level"),
        }
        for m in await rt.client.tags()
    ]
    return {
        "current": rt.client.model,
        "installed": installed,
        "resident": await rt.client.ps(),
    }


@app.post("/admin/warmup", dependencies=[Depends(auth)])
async def admin_warmup():
    return {"load_ms": round(await rt.client.warmup(), 1)}


@app.post("/admin/unload", dependencies=[Depends(auth)])
async def admin_unload():
    await rt.client.unload()
    return {"ok": True}


@app.post("/admin/model", dependencies=[Depends(auth)])
async def admin_model(model: str = Form(...)):
    """프로세스를 재시작하지 않고 모델을 갈아탄다."""
    await rt.swap(model)
    return {"model": rt.client.model}
