"""로컬 VLM 노드 전용 설정.

게이트웨이 설정과 섞이지 않도록 `LN_` 접두어만 읽음.

예:
LN_MODEL=qwen3-vl:8b-instruct
LN_NUM_CTX=8192
LN_FRAME_INTERVAL_SEC=2.0
LN_THINK=false

`.env.local`에 위와 같이 설정할 수 있음.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


# ============================================================
# Project Paths
# ============================================================

# vlm-workspace/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"

VIDEO_DIR = DATA_DIR / "videos"
FRAME_DIR = DATA_DIR / "frames"

PROMPTS_DIR = BASE_DIR / "prompts"

VIDEO_ANALYSIS_PROMPT = PROMPTS_DIR / "video_analysis.txt"


# ============================================================
# Environment Loader
# ============================================================

def _load_env_file(path: str = ".env.local") -> None:
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


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
    return [
        x.strip()
        for x in s.split(",")
        if x.strip()
    ]


_load_env_file()


# ============================================================
# Local VLM Settings
# ============================================================

@dataclass(frozen=True)
class LocalSettings:

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    ollama_base_url: str = _env(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    # 기본 VLM
    #
    # Qwen2.5-VL 3B:
    #   지상 작업자를 고소 작업자로 오인하는 사례가 발생
    #
    # Qwen3-VL 일반 모델:
    #   thinking 필드에 JSON이 들어가고 response가 비는 문제 발생
    #
    # 따라서 실제 테스트에서 안정적으로 동작한
    # Qwen2.5-VL 7B Q4를 기본 모델로 사용
    model: str = _env(
    "MODEL",
    "qwen2.5vl:7b-q4_K_M",
    )

    keep_alive: str = _env(
        "KEEP_ALIVE",
        "30m",
    )

    # 긴 video_analysis.txt 프롬프트가
    # 기본 4096 context를 초과할 수 있어 8192 사용
    num_ctx: int = _int_env(
        "NUM_CTX",
        8192,
    )

    num_predict: int = _int_env(
        "NUM_PREDICT",
        400,
    )

    temperature: float = _float_env(
        "TEMPERATURE",
        0.1,
    )

    # Qwen3-VL thinking 비활성화
    #
    # 구조화된 JSON이 thinking 쪽으로 들어가고
    # response가 비는 문제를 방지하기 위해 기본값 False
    think: bool = _bool_env(
        "THINK",
        False,
    )

    # --------------------------------------------------------
    # HTTP Timeout
    # --------------------------------------------------------

    connect_timeout: float = _float_env(
        "CONNECT_TIMEOUT",
        3.0,
    )

    read_timeout: float = _float_env(
        "READ_TIMEOUT",
        60.0,
    )

    # --------------------------------------------------------
    # Request / Queue
    # --------------------------------------------------------

    concurrency: int = _int_env(
        "CONCURRENCY",
        1,
    )

    queue_limit: int = _int_env(
        "QUEUE_LIMIT",
        4,
    )

    # --------------------------------------------------------
    # Image Processing
    # --------------------------------------------------------

    max_edge: int = _int_env(
        "MAX_EDGE",
        1024,
    )

    max_upload_bytes: int = _int_env(
        "MAX_UPLOAD_BYTES",
        12 * 1024 * 1024,
    )

    # --------------------------------------------------------
    # Video Processing
    # --------------------------------------------------------

    frame_interval_sec: float = _float_env(
        "FRAME_INTERVAL_SEC",
        2.0,
    )

    # --------------------------------------------------------
    # Local FastAPI Node
    # --------------------------------------------------------

    host: str = _env(
        "HOST",
        "0.0.0.0",
    )

    port: int = _int_env(
        "PORT",
        8100,
    )

    api_key: str = _env(
        "API_KEY",
        "",
    )

    warmup_on_start: bool = _bool_env(
        "WARMUP_ON_START",
        True,
    )

    # --------------------------------------------------------
    # JSON Response Retry
    # --------------------------------------------------------

    json_retry: int = _int_env(
        "JSON_RETRY",
        1,
    )

    # --------------------------------------------------------
    # Benchmark
    # --------------------------------------------------------

    bench_models: str = _env(
        "BENCH_MODELS",
        (
            "qwen3-vl:8b-instruct,"
            "qwen3-vl:8b-q4_K_M,"
            "qwen3-vl:8b-q8_0,"
            "qwen3-vl:4b-q4_K_M"
        ),
    )

    bench_edges: str = _env(
        "BENCH_EDGES",
        "672,896,1024,1280",
    )

    @property
    def bench_model_list(self) -> list[str]:
        return _csv(
            self.bench_models
        )

    @property
    def bench_edge_list(self) -> list[int]:
        return [
            int(x)
            for x in _csv(self.bench_edges)
        ]


local_settings = LocalSettings()


# ============================================================
# Backward Compatibility
# ============================================================
#
# 기존 코드에서 아래와 같이 import하는 부분을 유지하기 위한 alias.
#
# from app.local.config import VLM_MODEL
# from app.local.config import FRAME_INTERVAL_SEC
#
# ============================================================

VLM_MODEL = local_settings.model

FRAME_INTERVAL_SEC = local_settings.frame_interval_sec