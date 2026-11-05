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
from copy import deepcopy
from pathlib import Path
import httpx
from collections import Counter
from app.rag.confirmation_evidence import VISUAL_EVIDENCE_CODES
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
VLM_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_context": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["INDUSTRIAL", "NON_INDUSTRIAL", "UNCERTAIN"]},
                "evidence": {"type": "string", "minLength": 1},
            },
            "required": ["category", "evidence"],
            "additionalProperties": False,
        },
        "workers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "worker_id": {"type": "integer"},
                    "posture": {
                        "type": "string", "enum": ["UPRIGHT", "SITTING", "SQUATTING", "KNEELING",
                                                    "BENT_OVER", "LYING_OR_ROLLING", "LOSING_BALANCE", "UNCERTAIN"]},
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
                    "posture",
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
                            "COLLAPSE",
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
    "required": ["scene_context", "workers", "hazards", "scene_description"],
    "additionalProperties": False,
}


# Describe natural-language fields; validate and repair independently of inference decisions.
for text_schema in [
    VLM_SCHEMA["properties"]["scene_context"]["properties"]["evidence"],
    VLM_SCHEMA["properties"]["scene_description"],
    VLM_SCHEMA["properties"]["workers"]["items"]["properties"]["position"],
    VLM_SCHEMA["properties"]["workers"]["items"]["properties"]["observations"]["items"],
    VLM_SCHEMA["properties"]["hazards"]["items"]["properties"]["evidence"],
]:
    text_schema["description"] = "한국어 설명. 영어 단어나 중국어 문자를 사용하지 마세요."


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
        temperature: float = 0.0,
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
    counts = Counter(worker.get("worker_id") for worker in workers)
    mapping = {worker.get("worker_id"): index for index, worker in enumerate(workers, start=1)
               if counts[worker.get("worker_id")] == 1}
    for worker_id, worker in enumerate(workers, start=1):
        worker["worker_id"] = worker_id
    for hazard in analysis.get("hazards", []):
        if "worker_ids" in hazard:
            # Unresolved or duplicated source IDs must not silently bind to another person.
            hazard["worker_ids"] = [mapping.get(source_id, 0) for source_id in hazard["worker_ids"]]
    return analysis


def validate_analysis_schema(analysis: dict) -> None:
    """기존 파이프라인이 사용하는 핵심 VLM 응답 구조를 검증한다."""
    required_top_level = {"scene_context", "workers", "hazards", "scene_description"}
    missing = required_top_level.difference(analysis)
    if missing:
        raise OllamaBadJSON(f"VLM JSON 필수 필드 누락: {', '.join(sorted(missing))}")

    if not isinstance(analysis["workers"], list):
        raise OllamaBadJSON("VLM JSON의 workers는 배열이어야 합니다.")
    if not isinstance(analysis["hazards"], list):
        raise OllamaBadJSON("VLM JSON의 hazards는 배열이어야 합니다.")
    if not isinstance(analysis["scene_description"], str):
        raise OllamaBadJSON("VLM JSON의 scene_description은 문자열이어야 합니다.")

    context = analysis["scene_context"]
    if (not isinstance(context, dict) or context.get("category") not in
            {"INDUSTRIAL", "NON_INDUSTRIAL", "UNCERTAIN"} or not isinstance(context.get("evidence"), str) or not context["evidence"].strip()):
        raise OllamaBadJSON("scene_context의 category와 evidence가 필요합니다.")
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
    context_evidence = analysis.get("scene_context", {}).get("evidence", "")
    if context_evidence:
        fields.append(("scene_context.evidence", str(context_evidence)))
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
    # Reject foreign alphabetic text, including single Latin letters and kana.
    return any(character.isalpha() and not (
        "가" <= character <= "힣" or "\u1100" <= character <= "\u11ff"
        or "\u3130" <= character <= "\u318f") for character in text)


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
    image_base64: str | list[str] | None,
    prompt: str,
    attempt: int,
    schema: dict | None = None,
) -> dict:
    repeat_penalty = 1.15
    temperature = cfg.temperature
    payload = {
        "model": VLM_MODEL,
        "prompt": prompt,
        "format": VLM_SCHEMA if schema is None else schema,
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
    if image_base64:
        payload["images"] = image_base64 if isinstance(image_base64, list) else [image_base64]
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


def localize_enum_mentions(text: str) -> str:
    # Only explanatory text is changed; structured enum fields are never touched.
    labels = {
        "LYING_OR_ROLLING": "바닥에 누움 또는 구름", "LOSING_BALANCE": "균형 상실",
        "SQUATTING": "쪼그려 앉음", "KNEELING": "무릎을 꿇음", "BENT_OVER": "허리를 숙임",
        "UPRIGHT": "직립", "SITTING": "앉음", "GROUND": "지상", "ELEVATED": "높은 작업 위치",
        "NON_INDUSTRIAL": "비산업 활동", "INDUSTRIAL": "산업 작업", "UNCERTAIN": "불확실",
        "NOT_APPLICABLE": "적용 대상 아님", "WORN_NOT_CONNECTED": "착용했으나 미체결",
        "NOT_WEARING": "미착용", "WEARING": "착용", "CONNECTED": "체결됨",
        "COLLAPSE": "쓰러짐 후보", "FALL_HAZARD": "추락 위험", "NO_HELMET": "안전모 미착용",
        "UNFASTENED_SAFETY_HARNESS": "안전대 미착용 또는 미체결", "BLOCKED_PATH": "통행로 장애",
    }
    labels.update({
        "HEAD_VISIBLE": "머리 부분 확인", "HELMET_ABSENT": "안전모 미착용 확인",
        "ELEVATED_SUPPORT_VISIBLE": "높은 작업 지지면 확인", "HARNESS_ABSENT": "안전대 미착용 확인",
        "ANCHOR_DISCONNECTED": "안전고리 미체결 확인", "EDGE_OR_OPENING_VISIBLE": "가장자리 또는 개구부 확인",
        "PERSON_EXPOSED": "작업자 노출 확인", "PROTECTION_MISSING": "방호 부족 확인",
        "PASSAGE_VISIBLE": "통행 경로 확인", "PASSAGE_BLOCKED": "통행 경로 차단 확인",
    })
    return re.sub(r"\b(?:" + "|".join(sorted(labels, key=len, reverse=True)) + r")\b",
                  lambda match: labels[match.group()], text)


def repair_analysis_language(analysis: dict, max_attempts: int = 2) -> dict:
    """Translate invalid text fields only. Never re-infer or replace decisions."""
    invalid = [(path, text) for path, text in collect_natural_language_fields(analysis)
               if is_invalid_natural_language(text)]
    if not invalid:
        return analysis
    keys = [f"field_{index}" for index in range(len(invalid))]
    original_texts = {key: localize_enum_mentions(text) for key, (_, text) in zip(keys, invalid)}
    completed = {}
    last_error = None
    for attempt in range(1, max_attempts + 1):
        pending = {key: text for key, text in original_texts.items() if key not in completed}
        schema = {"type": "object", "properties": {
            key: {"type": "string", "description": "원문을 한국어로 번역한 문장"} for key in pending},
            "required": list(pending), "additionalProperties": False}
        prompt = ("당신은 영어를 한국어로 옮기는 번역기입니다. JSON의 key는 그대로 두고 value만 번역하세요. "
                  "의미·부정·불확실성을 보존하고 사실이나 판단을 추가하지 마세요. "
                  "영문 단어와 약자도 한글로 옮기세요. 예: squatting=쪼그려 앉음, "
                  "lying on the ground=바닥에 누워 있음, roller compactor=노면 다짐 장비. "
                  "입력과 같은 key를 빠짐없이 가진 JSON만 반환하세요.\n"
                  + json.dumps(pending, ensure_ascii=False))
        if attempt > 1:
            prompt += "\n이 항목들은 이전 번역에서 누락되거나 영문이 남았습니다. 각 값을 완전한 한국어로 번역하세요."
        try:
            data = request_ollama(Path("language_repair"), None, prompt, attempt, schema=schema)
            if not data.get("done") or data.get("done_reason") == "length":
                raise LanguageValidationError("번역 응답이 완결되지 않았습니다.")
            translated_fields = parse_json_response(data.get("response", ""))
            for key in pending:
                text = translated_fields.get(key)
                if isinstance(text, str):
                    text = localize_enum_mentions(text)
                if isinstance(text, str) and text.strip() and not is_invalid_natural_language(text):
                    completed[key] = text
            if len(completed) != len(keys):
                raise LanguageValidationError("번역에서 누락되거나 언어 검증에 실패한 항목이 있습니다.")
            result = deepcopy(analysis)
            for key, (path, _) in zip(keys, invalid):
                parts = re.findall(r"[A-Za-z_]+|\d+", path)
                target = result
                for part in parts[:-1]:
                    target = target[int(part)] if isinstance(target, list) else target[part]
                last_key = int(parts[-1]) if isinstance(target, list) else parts[-1]
                target[last_key] = completed[key]
            validate_korean_output(result)
            logger.info("언어 필드만 번역 완료 - fields=%s, attempt=%s", len(invalid), attempt)
            return result
        except Exception as error:
            last_error = error
            logger.warning("언어 필드 번역 실패 - attempt=%s/%s remaining=%s",
                           attempt, max_attempts, len(keys)-len(completed))
    raise LanguageValidationError("언어 필드 번역에 실패했습니다. 이미지 판단을 다시 생성하지 않습니다.") from last_error


class AnalysisLanguageError(RuntimeError):
    """Valid structured observations exist, but their explanation could not be localized."""
    def __init__(self, message, analysis):
        super().__init__(message)
        self.analysis = deepcopy(analysis)


def analyze_image(image_path: str | Path, prompt: str | None = None, max_retries: int = 3) -> str:
    if max_retries < 1:
        raise ValueError("max_retries는 1 이상이어야 합니다.")
    started = time.perf_counter()
    image_path = validate_image(image_path)
    prompt = load_video_prompt() if prompt is None else prompt
    image_base64 = prepare_image_base64(image_path)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            data = request_ollama(image_path, image_base64, prompt, attempt)
            if not data.get("model") or not data.get("response"):
                raise OllamaBadJSON("Ollama가 정상 response를 반환하지 않았습니다.")
            if not data.get("done") or data.get("done_reason") == "length":
                raise OllamaBadJSON("VLM 응답이 완결되지 않았습니다.")
            parsed = normalize_worker_ids(parse_json_response(data["response"]))
            validate_analysis_schema(parsed)
            try:
                validate_korean_output(parsed)
            except LanguageValidationError:
                parsed = repair_analysis_language(parsed, max_attempts=min(2, max_retries))
            logger.info("VLM 분석 완료 - image=%s, attempt=%s, elapsed=%.2fs",
                        image_path.name, attempt, time.perf_counter()-started)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except LanguageValidationError as error:
            raise AnalysisLanguageError(f"{image_path.name} 언어 검증 실패; 원래 판단은 재생성하지 않음", parsed) from error
        except Exception as error:
            last_error = error
            logger.warning("VLM 분석 재시도 - image=%s, attempt=%s/%s, reason=%s",
                           image_path.name, attempt, max_retries, error)
            if attempt < max_retries:
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
