"""로컬 VLM 노드 전용 설정.

게이트웨이 설정과 섞이지 않도록 `LN_` 접두어만 읽음. 예를 들면
`LN_MODEL=qwen2.5vl:7b-q4_K_M`처럼 `.env.local`에 적어두면 됨.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


# vlm-workspace/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
FRAME_DIR = DATA_DIR / "frames"
PROMPTS_DIR = BASE_DIR / "prompts"
IMAGE_ANALYSIS_PROMPT = PROMPTS_DIR / "image_analysis.txt"


def _load_env_file(path: str = ".env.local") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(key: str, default: str) -> str:
    return os.getenv(f"LN_{key}", default)


def _int_env(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _bool_env(key: str, default: bool) -> bool:
    value = _env(key, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


_load_env_file()


@dataclass(frozen=True)
class LocalSettings:
    # VLM 공급자 선택. 기존 Ollama 환경과 Gemini API 간 전환에만 사용한다.
    vlm_provider: str = _env("VLM_PROVIDER", "ollama").strip().lower()

    # Ollama 설정
    ollama_base_url: str = _env("OLLAMA_BASE_URL", "http://166.104.223.60:11434")
    model: str = _env("MODEL", "qwen2.5vl:7b-q4_K_M")
    keep_alive: str = _env("KEEP_ALIVE", "30m")
    num_ctx: int = _int_env("NUM_CTX", 8192)
    num_predict: int = _int_env("NUM_PREDICT", 400)
    temperature: float = _float_env("TEMPERATURE", 0.1)
    think: bool = _bool_env("THINK", False)

    # Gemini API 설정. API 키는 반드시 .env.local 또는 배포 환경변수로만 제공한다.
    gemini_base_url: str = _env(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    gemini_api_key: str = _env("GEMINI_API_KEY", "")
    gemini_model: str = _env("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_max_output_tokens: int = _int_env("GEMINI_MAX_OUTPUT_TOKENS", 1200)
    gemini_response_mime_type: str = _env(
        "GEMINI_RESPONSE_MIME_TYPE",
        "application/json",
    )

    connect_timeout: float = _float_env("CONNECT_TIMEOUT", 3.0)
    read_timeout: float = _float_env("READ_TIMEOUT", 60.0)

    concurrency: int = _int_env("CONCURRENCY", 1)
    queue_limit: int = _int_env("QUEUE_LIMIT", 4)
    max_edge: int = _int_env("MAX_EDGE", 1024)
    max_upload_bytes: int = _int_env("MAX_UPLOAD_BYTES", 12 * 1024 * 1024)

    frame_interval_sec: float = _float_env("FRAME_INTERVAL_SEC", 2.0)

    host: str = _env("HOST", "0.0.0.0")
    port: int = _int_env("PORT", 8100)
    api_key: str = _env("API_KEY", "")
    warmup_on_start: bool = _bool_env("WARMUP_ON_START", True)

    json_retry: int = _int_env("JSON_RETRY", 1)
    retry_delay_sec: float = _float_env("RETRY_DELAY_SEC", 3.0)
    retry_backoff_max_sec: float = _float_env("RETRY_BACKOFF_MAX_SEC", 30.0)

    bench_models: str = _env(
        "BENCH_MODELS",
        "qwen3-vl:8b-q4_K_M,qwen3-vl:8b-q8_0,qwen3-vl:4b-q4_K_M",
    )
    bench_edges: str = _env("BENCH_EDGES", "672,896,1024,1280")

local_settings = LocalSettings()

VLM_MODEL = local_settings.model
FRAME_INTERVAL_SEC = local_settings.frame_interval_sec
