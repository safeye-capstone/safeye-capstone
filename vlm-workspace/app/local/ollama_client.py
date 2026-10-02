"""Ollama HTTP 클라이언트.
develop 브랜치의 비동기 로컬 노드용 OllamaClient와
기존 VLM 파이프라인에서 사용하는 analyze_image()를 함께 제공한다.
- FastAPI 로컬 노드: OllamaClient.chat_json()
- 기존 이미지 파이프라인: analyze_image()
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
import httpx
from app.local.config import (
    FRAME_DIR,
    VIDEO_ANALYSIS_PROMPT,
    VLM_MODEL,
    local_settings as cfg,
)
from app.local.imageops import clamp, validate_image

logger = logging.getLogger(__name__)
_NS_PER_MS = 1_000_000
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)
LEGACY_MAX_IMAGE_SIDE = 1280
LEGACY_JPEG_QUALITY = 90
LEGACY_NUM_PREDICT = 1200
RETRY_DELAY_SECONDS = 3.0
_SYNC_REQUEST_LOCK = threading.Lock()
OUTPUT_CONSTRAINTS = """
[출력 규칙]
- 반드시 하나의 유효한 JSON 객체만 반환하세요.
- JSON 외부에 설명을 작성하지 마세요.
- Markdown을 사용하지 마세요.
- 동일한 문장이나 표현을 반복해서 생성하지 마세요.
[출력 언어]
- position, observations, evidence, scene_description 등
  모든 자연어 설명은 반드시 한국어로 작성하세요.
- 자연어 설명에 영어 또는 중국어를 사용하거나
  여러 언어를 혼용하지 마세요.
- JSON key와 enum 값은 지정된 형식을 그대로 유지하세요.
- 이 규칙은 출력 언어에만 적용하며,
  기존 분석 내용과 판단 근거의 상세도를
  생략하거나 축약하지 마세요.
"""
LANGUAGE_RETRY_INSTRUCTION = """
[언어 검증 실패 - 재출력 지시]
이전 응답의 자연어 필드에 영어 또는 중국어가 포함되었습니다.
이미지에 대한 분석 기준과 판단 내용의 상세도는 그대로 유지하세요.
분석 내용을 축약하거나 단순화하지 마세요.
단, 다음 자연어 필드만 반드시 한국어로 작성하세요.
- position
- observations
- evidence
- scene_description
JSON key와 enum 값은 기존 영어 형식을 그대로 유지하세요.
예:
"position": "고소 작업발판 가장자리에서 작업 중"
잘못된 예:
"position": "WORKING_ON_HIGH_STRUCTURE"
JSON 객체 하나만 다시 반환하세요.
"""
VLM_SCHEMA = {
    "type": "object",
    "properties": {
        "workers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "worker_id": {"type": "integer"},
                    "helmet": {
                        "type": "string",
                        "enum": ["WEARING", "NOT_WEARING", "UNCERTAIN"],
                    },
                    "vest": {
                        "type": "string",
                        "enum": ["WEARING", "NOT_WEARING", "UNCERTAIN"],
                    },
                    "harness": {
                        "type": "string",
                        "enum": [
                            "CONNECTED",
                            "WORN_NOT_CONNECTED",
                            "NOT_WEARING",
                            "UNCERTAIN",
                            "NOT_APPLICABLE",
                        ],
                    },
                    "work_level": {
                        "type": "string",
                        "enum": ["GROUND", "ELEVATED", "UNCERTAIN"],
                    },
                    "position": {"type": "string"},
                    "observations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "worker_id",
                    "helmet",
                    "vest",
                    "harness",
                    "work_level",
                    "position",
                    "observations",
                ],
                "additionalProperties": False,
            },
        },
        "hazards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk_type": {
                        "type": "string",
                        "enum": [
                            "NO_HELMET",
                            "UNFASTENED_SAFETY_HARNESS",
                            "FALL_HAZARD",
                            "BLOCKED_PATH",
                        ],
                    },
                    "detected": {"type": "boolean"},
                    "confidence": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH"],
                    },
                    "proximity": {
                        "type": "string",
                        "enum": ["IMMEDIATE", "NEAR", "NOT_NEAR", "UNCERTAIN"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": [
                    "risk_type",
                    "detected",
                    "confidence",
                    "proximity",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        },
        "scene_description": {"type": "string"},
    },
    "required": ["workers", "hazards", "scene_description"],
    "additionalProperties": False,
}


class OllamaError(RuntimeError):
    """Ollama 계열 오류의 공통 부모."""


class OllamaUnreachable(OllamaError):
    """Ollama가 꺼져 있거나 연결 자체가 안 되는 상태."""


class OllamaTimeout(OllamaError):
    """연결은 됐지만 제한 시간 안에 추론이 끝나지 않은 상태."""


class OllamaBadJSON(OllamaError):
    """모델 응답이 비어 있거나 JSON으로 파싱되지 않는 상태."""


class LanguageValidationError(RuntimeError):
    """기존 파이프라인 자연어 필드가 한국어 규칙을 위반한 경우."""


@dataclass
class OllamaTiming:
    """Ollama가 응답에 실어주는 추론 시간 지표."""

    total_ms: float = 0.0
    load_ms: float = 0.0
    prompt_eval_ms: float = 0.0
    eval_ms: float = 0.0
    prompt_tokens: int = 0
    eval_tokens: int = 0

    @property
    def decode_tps(self) -> float:
        return self.eval_tokens / (self.eval_ms / 1000) if self.eval_ms else 0.0

    @property
    def ttft_ms(self) -> float:
        return self.load_ms + self.prompt_eval_ms

    @classmethod
    def from_response(cls, body: dict) -> "OllamaTiming":
        def g(key: str) -> float:
            return float(body.get(key) or 0)

        return cls(
            total_ms=g("total_duration") / _NS_PER_MS,
            load_ms=g("load_duration") / _NS_PER_MS,
            prompt_eval_ms=g("prompt_eval_duration") / _NS_PER_MS,
            eval_ms=g("eval_duration") / _NS_PER_MS,
            prompt_tokens=int(g("prompt_eval_count")),
            eval_tokens=int(g("eval_count")),
        )

    def as_dict(self) -> dict:
        data = asdict(self)
        data["decode_tps"] = round(self.decode_tps, 2)
        data["ttft_ms"] = round(self.ttft_ms, 1)
        return data


def strip_fence(text: str) -> str:
    """모델이 JSON 코드블록을 붙여도 파싱할 수 있도록 fence를 제거한다."""
    return _FENCE.sub("", text).strip()


def decode_json_object(text: str) -> dict:
    """JSON 외부 문장이 섞여 있어도 첫 번째 완전한 JSON 객체를 복구한다."""
    cleaned = strip_fence(text)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            parsed, _ = decoder.raw_decode(cleaned[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise OllamaBadJSON("모델 응답에서 유효한 JSON 객체를 찾지 못했습니다.")


def fallback_json_prompt(prompt: str) -> str:
    """엄격한 schema가 불안정한 VLM을 위해 더 단순한 JSON-전용 프롬프트로 낮춘다."""
    base = prompt.strip()
    suffix = (
        "\n유효한 JSON 객체 하나만 반환하세요. Markdown, 코드 블록, JSON 외부 설명은 "
        "사용하지 마세요. 다음 key를 각각 한 번씩 반드시 포함하세요: "
        "observed_objects, spatial_relations, uncertain, hazard_detected, "
        "hazard_type, severity, reasoning, recommended_actions, references, "
        "confidence. 값이 없으면 빈 배열을 사용하세요. 자연어 값은 한국어로 작성하세요."
    )
    return (base + suffix).strip()


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        connect_timeout: float = 3.0,
        read_timeout: float = 60.0,
        keep_alive: str | int = "30m",
        num_ctx: int = 8192,
        num_predict: int = 400,
        temperature: float = 0.1,
        think: bool | None = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.temperature = temperature
        self.think = think
        self.connect_timeout = connect_timeout
        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=10.0,
            pool=5.0,
        )
        self._request_lock = asyncio.Lock()

    def _options(self, override: dict | None = None) -> dict:
        options = {
            "temperature": self.temperature,
            "num_predict": self.num_predict,
            "num_ctx": self.num_ctx,
        }
        if override:
            options.update({k: v for k, v in override.items() if v is not None})
        return options

    async def _post(self, path: str, payload: dict, timeout: httpx.Timeout | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as error:
                    raise OllamaBadJSON("Ollama가 JSON이 아닌 HTTP 응답을 반환했습니다.") from error
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            raise OllamaUnreachable(f"Ollama unreachable: {self.base_url} ({error})") from error
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as error:
            raise OllamaTimeout(f"Ollama 요청 시간 초과: {path}") from error
        except httpx.HTTPStatusError as error:
            raise OllamaError(
                f"HTTP {error.response.status_code}: {error.response.text[:200]}"
            ) from error

    async def chat_json(
        self,
        image_bytes: bytes,
        prompt: str,
        json_schema: dict,
        *,
        model: str | None = None,
        options: dict | None = None,
    ) -> tuple[dict, OllamaTiming]:
        """이미지 1장과 프롬프트를 보내고 JSON dict와 타이밍을 받는다.
        일부 VLM 모델은 엄격한 JSON schema를 요구하는 format일 때 빈 응답을
        반환하는 경우가 있으므로, 실패 시 한 번만 일반 JSON 모드로 재시도한다.
        """
        attempts = [
            (prompt, json_schema),
            (fallback_json_prompt(prompt), "json"),
        ]
        required_keys = set(json_schema.get("required", ()))
        if not required_keys:
            required_keys = {
                "observed_objects",
                "spatial_relations",
                "uncertain",
                "hazard_detected",
                "hazard_type",
                "severity",
                "reasoning",
                "recommended_actions",
                "references",
                "confidence",
            }
        last_body: dict | None = None
        last_content = ""
        last_thinking = ""
        last_missing_keys: set[str] = set()
        for attempt_prompt, fmt in attempts:
            payload = {
                "model": model or self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": attempt_prompt,
                        "images": [base64.b64encode(image_bytes).decode()],
                    }
                ],
                "format": fmt,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": self._options(options),
            }
            if self.think is not None:
                payload["think"] = self.think
            async with self._request_lock:
                body = await self._post("/api/chat", payload)
            last_body = body
            timing = OllamaTiming.from_response(body)
            message = body.get("message") or {}
            content = message.get("content", "")
            last_content = content
            last_thinking = message.get("thinking", "")
            candidates = [content, last_thinking]
            for candidate in candidates:
                if not candidate or not candidate.strip():
                    continue
                cleaned = strip_fence(candidate)
                if cleaned.startswith("<think>"):
                    cleaned = re.sub(r"^<think>\s*", "", cleaned, flags=re.I)
                    cleaned = re.sub(r"\s*</think>\s*$", "", cleaned, flags=re.I)
                try:
                    parsed = decode_json_object(cleaned)
                    missing_keys = required_keys.difference(parsed)
                    if missing_keys:
                        last_missing_keys = missing_keys
                        continue
                    return parsed, timing
                except OllamaBadJSON:
                    continue
        if last_body is not None:
            raw_head = repr(last_content[:200].replace("\n", " "))
            thinking_head = repr(last_thinking[:200].replace("\n", " "))
            if last_missing_keys:
                missing = ", ".join(sorted(last_missing_keys))
                raise OllamaBadJSON(f"incomplete JSON / missing_keys={missing}")
            if last_content.strip():
                raise OllamaBadJSON(f"invalid JSON / raw_head={raw_head}")
            if last_thinking.strip():
                raise OllamaBadJSON(f"empty content / thinking_head={thinking_head}")
            raise OllamaBadJSON(f"empty response / raw_head={raw_head}")
        raise OllamaBadJSON("empty response")

    async def warmup(self, model: str | None = None) -> float:
        """모델을 미리 로드하고 로드 시간을 ms로 반환한다."""
        payload = {
            "model": model or self.model,
            "prompt": "",
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        body = await self._post(
            "/api/generate",
            payload,
            timeout=httpx.Timeout(
                connect=self.connect_timeout,
                read=300.0,
                write=10.0,
                pool=5.0,
            ),
        )
        return float(body.get("load_duration") or 0) / _NS_PER_MS

    async def unload(self, model: str | None = None) -> None:
        """벤치마크 중 다음 모델과 VRAM이 섞이지 않도록 모델을 내린다."""
        await self._post(
            "/api/generate",
            {"model": model or self.model, "prompt": "", "keep_alive": 0},
        )

    async def tags(self) -> list[dict]:
        """설치된 Ollama 모델 목록."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])

    async def ps(self) -> list[dict]:
        """현재 메모리에 올라간 모델 목록."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/ps")
            response.raise_for_status()
            return response.json().get("models", [])

    async def show(self, model: str | None = None) -> dict:
        return await self._post("/api/show", {"model": model or self.model})

    async def loaded_vram_mb(self, model: str | None = None) -> float:
        target = model or self.model
        for item in await self.ps():
            if item.get("name", "").startswith(target) or item.get("model", "") == target:
                return round(float(item.get("size_vram") or 0) / 1024 / 1024, 1)
        return 0.0

    async def alive(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.connect_timeout)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


def load_video_prompt() -> str:
    if not VIDEO_ANALYSIS_PROMPT.exists():
        raise FileNotFoundError(
            "영상 분석 프롬프트를 찾을 수 없습니다.\n" f"경로: {VIDEO_ANALYSIS_PROMPT}"
        )
    prompt = VIDEO_ANALYSIS_PROMPT.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("video_analysis.txt가 비어 있습니다.")
    return prompt + "\n\n" + OUTPUT_CONSTRAINTS


def remove_markdown_fence(content: str) -> str:
    return strip_fence(content)


def parse_json_response(content: str) -> dict:
    try:
        return decode_json_object(content)
    except OllamaBadJSON:
        logger.error(
            "JSON 파싱 실패 - response_tail=%r",
            content[-500:],
        )
        raise


def normalize_worker_ids(analysis: dict) -> dict:
    workers = analysis.get("workers", [])
    for worker_id, worker in enumerate(workers, start=1):
        worker["worker_id"] = worker_id
    return analysis


def validate_analysis_schema(analysis: dict) -> None:
    """기존 파이프라인이 사용하는 핵심 VLM 응답 구조를 검증한다."""
    required_top_level = {"workers", "hazards", "scene_description"}
    missing = required_top_level.difference(analysis)
    if missing:
        raise OllamaBadJSON(f"VLM JSON 필수 필드 누락: {', '.join(sorted(missing))}")

    if not isinstance(analysis["workers"], list):
        raise OllamaBadJSON("VLM JSON의 workers는 배열이어야 합니다.")
    if not isinstance(analysis["hazards"], list):
        raise OllamaBadJSON("VLM JSON의 hazards는 배열이어야 합니다.")
    if not isinstance(analysis["scene_description"], str):
        raise OllamaBadJSON("VLM JSON의 scene_description은 문자열이어야 합니다.")

    worker_required = set(VLM_SCHEMA["properties"]["workers"]["items"]["required"])
    hazard_required = set(VLM_SCHEMA["properties"]["hazards"]["items"]["required"])

    for index, worker in enumerate(analysis["workers"]):
        if not isinstance(worker, dict):
            raise OllamaBadJSON(f"workers[{index}]는 객체여야 합니다.")
        missing = worker_required.difference(worker)
        if missing:
            raise OllamaBadJSON(f"workers[{index}] 필수 필드 누락: {', '.join(sorted(missing))}")

    for index, hazard in enumerate(analysis["hazards"]):
        if not isinstance(hazard, dict):
            raise OllamaBadJSON(f"hazards[{index}]는 객체여야 합니다.")
        missing = hazard_required.difference(hazard)
        if missing:
            raise OllamaBadJSON(f"hazards[{index}] 필수 필드 누락: {', '.join(sorted(missing))}")


def collect_natural_language_fields(analysis: dict) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    scene_description = analysis.get("scene_description", "")
    if scene_description:
        fields.append(("scene_description", str(scene_description)))
    for index, worker in enumerate(analysis.get("workers", [])):
        position = worker.get("position", "")
        if position:
            fields.append((f"workers[{index}].position", str(position)))
        observations = worker.get("observations", [])
        for obs_index, observation in enumerate(observations):
            if observation:
                fields.append(
                    (
                        f"workers[{index}].observations[{obs_index}]",
                        str(observation),
                    )
                )
    for index, hazard in enumerate(analysis.get("hazards", [])):
        evidence = hazard.get("evidence", "")
        if evidence:
            fields.append((f"hazards[{index}].evidence", str(evidence)))
    return fields


def is_invalid_natural_language(text: str) -> bool:
    text = str(text).strip()
    if not text:
        return False
    if re.search(r"[\u4e00-\u9fff]", text):
        return True
    if re.search(r"\b[A-Z]{2,}(?:_[A-Z]{2,})+\b", text):
        return True
    english_words = re.findall(r"\b[A-Za-z]{2,}\b", text)
    hangul_chars = re.findall(r"[가-힣]", text)
    if len(hangul_chars) == 0 and len(english_words) >= 2:
        return True
    if len(english_words) >= 4:
        return True
    return False


def validate_korean_output(analysis: dict) -> None:
    invalid_fields: list[tuple[str, str]] = []
    for field_name, text in collect_natural_language_fields(analysis):
        if is_invalid_natural_language(text):
            invalid_fields.append((field_name, text))
    if not invalid_fields:
        return
    for field_name, text in invalid_fields:
        logger.warning(
            "출력 언어 검증 실패 - field=%s, value=%r",
            field_name,
            text[:120],
        )
    raise LanguageValidationError("자연어 필드에 영어 또는 중국어가 포함되어 있습니다.")


def prepare_image_base64(image_path: Path) -> str:
    raw = image_path.read_bytes()
    try:
        processed, meta = clamp(
            raw,
            LEGACY_MAX_IMAGE_SIDE,
            LEGACY_JPEG_QUALITY,
        )
    except Exception as error:
        raise RuntimeError(f"이미지를 읽거나 변환할 수 없습니다: {image_path}") from error
    if meta.get("resized"):
        logger.debug(
            "이미지 전처리 - image=%s, %sx%s -> %sx%s",
            image_path.name,
            meta["orig_w"],
            meta["orig_h"],
            meta["w"],
            meta["h"],
        )
    return base64.b64encode(processed).decode("utf-8")


def request_ollama(
    image_path: Path,
    image_base64: str,
    prompt: str,
    attempt: int,
) -> dict:
    repeat_penalty = 1.15 + (attempt - 1) * 0.05
    temperature = min(0.10 + (attempt - 1) * 0.05, 0.20)
    payload = {
        "model": VLM_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "format": VLM_SCHEMA,
        "stream": False,
        "think": cfg.think,
        "keep_alive": cfg.keep_alive,
        "options": {
            "num_ctx": cfg.num_ctx,
            "temperature": temperature,
            "num_predict": LEGACY_NUM_PREDICT,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": 256,
            "top_p": 0.90,
        },
    }
    timeout = httpx.Timeout(
        connect=cfg.connect_timeout,
        read=max(cfg.read_timeout, 300.0),
        write=30.0,
        pool=5.0,
    )
    request_started = time.perf_counter()
    try:
        with _SYNC_REQUEST_LOCK:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{cfg.ollama_base_url.rstrip('/')}/api/generate",
                    json=payload,
                )
                if not response.is_success:
                    logger.error(
                        "Ollama HTTP 오류 - status=%s, response=%r",
                        response.status_code,
                        response.text[:2000],
                    )
                response.raise_for_status()
                data = response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        raise OllamaUnreachable(f"Ollama unreachable: {cfg.ollama_base_url} ({error})") from error
    except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as error:
        raise OllamaTimeout("Ollama 이미지 분석 read timeout") from error
    except httpx.HTTPStatusError as error:
        raise OllamaError(
            f"HTTP {error.response.status_code}: {error.response.text[:200]}"
        ) from error
    except ValueError as error:
        raise OllamaBadJSON("Ollama HTTP 응답 자체가 JSON이 아닙니다.") from error
    logger.info(
        "Ollama 응답 - image=%s, status=%s, done=%s, reason=%s, tokens=%s, "
        "model=%s, elapsed=%.2fs",
        image_path.name,
        response.status_code,
        data.get("done"),
        data.get("done_reason"),
        data.get("eval_count"),
        data.get("model"),
        time.perf_counter() - request_started,
    )
    return data


def analyze_image(
    image_path: str | Path,
    prompt: str | None = None,
    max_retries: int = 3,
) -> str:
    if max_retries < 1:
        raise ValueError("max_retries는 1 이상이어야 합니다.")

    analysis_started = time.perf_counter()
    image_path = validate_image(image_path)
    if prompt is None:
        prompt = load_video_prompt()
    image_base64 = prepare_image_base64(image_path)
    last_error: Exception | None = None
    language_retry_required = False
    for attempt in range(1, max_retries + 1):
        try:
            request_prompt = prompt
            if language_retry_required:
                request_prompt = prompt + "\n\n" + LANGUAGE_RETRY_INSTRUCTION
                logger.info("언어 재시도 - 분석 내용은 유지하고 자연어 필드만 한국어로 재생성")
            data = request_ollama(
                image_path=image_path,
                image_base64=image_base64,
                prompt=request_prompt,
                attempt=attempt,
            )
            done = data.get("done", False)
            done_reason = data.get("done_reason")
            model = data.get("model", "")
            content = data.get("response", "")
            if not model or not content:
                thinking = data.get("thinking", "")
                if thinking:
                    raise RuntimeError("Ollama가 response 대신 thinking 응답만 반환했습니다.")
                raise RuntimeError("Ollama가 빈 응답을 반환했습니다.\n" f"전체 응답: {data}")
            if not done:
                raise RuntimeError(
                    "Ollama 추론이 정상적으로 완료되지 않았습니다.\n" f"전체 응답: {data}"
                )
            if done_reason == "length":
                raise RuntimeError("VLM 응답이 출력 길이 제한에 도달했습니다.")
            parsed = parse_json_response(content)
            parsed = normalize_worker_ids(parsed)
            validate_analysis_schema(parsed)
            validate_korean_output(parsed)
            logger.info(
                "VLM 분석 완료 - image=%s, attempt=%s, elapsed=%.2fs",
                image_path.name,
                attempt,
                time.perf_counter() - analysis_started,
            )
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except LanguageValidationError as error:
            last_error = error
            language_retry_required = True
            logger.warning(
                "VLM 언어 검증 재시도 - image=%s, attempt=%s/%s, reason=%s",
                image_path.name,
                attempt,
                max_retries,
                error,
            )
            if attempt < max_retries:
                logger.info(
                    "한국어 출력 규칙을 강화하여 %.1f초 후 다시 시도합니다.",
                    RETRY_DELAY_SECONDS,
                )
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as error:
            last_error = error
            logger.warning(
                "VLM 분석 재시도 - image=%s, attempt=%s/%s, reason=%s",
                image_path.name,
                attempt,
                max_retries,
                error,
            )
            if attempt < max_retries:
                logger.info("%.1f초 후 다시 시도합니다.", RETRY_DELAY_SECONDS)
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"{image_path.name} VLM 분석 최종 실패") from last_error


def main() -> None:
    image_path = FRAME_DIR / "frame_0000.00.jpg"
    print()
    print("=" * 60)
    print("VLM 단일 이미지 테스트")
    print("=" * 60)
    print(f"모델: {VLM_MODEL}")
    print(f"이미지: {image_path}")
    try:
        result = analyze_image(image_path)
        print()
        print("=" * 60)
        print("VLM 분석 결과")
        print("=" * 60)
        print(result)
    except Exception as error:
        print()
        print("=" * 60)
        print("VLM 분석 실패")
        print("=" * 60)
        print(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    main()
