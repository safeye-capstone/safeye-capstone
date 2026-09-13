"""게이트웨이 쪽 로컬 백엔드 어댑터가 기대하는 최소 설정.

현재 VLM 묶음만 따로 실행하거나 import할 때
끊기지 않도록 둔 호환용 설정임.
"""

from dataclasses import dataclass
import os


def _float_env(
    key: str,
    default: float,
) -> float:
    try:
        return float(
            os.getenv(
                key,
                default,
            )
        )
    except ValueError:
        return default


def _int_env(
    key: str,
    default: int,
) -> int:
    try:
        return int(
            os.getenv(
                key,
                default,
            )
        )
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL",
        os.getenv(
            "LN_OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ),
    )

    local_base_url: str = os.getenv(
        "LOCAL_BASE_URL",
        "http://127.0.0.1:8100",
    )

    local_model: str = os.getenv(
        "LOCAL_MODEL",
        os.getenv(
            "LN_MODEL",
            os.getenv(
                "LLM_MODEL",
                "qwen2.5vl:7b-q4_K_M",
            ),
        ),
    ),
    

    local_connect_timeout: float = _float_env(
        "LOCAL_CONNECT_TIMEOUT",
        3.0,
    )

    local_read_timeout: float = _float_env(
        "LOCAL_READ_TIMEOUT",
        60.0,
    )

    max_output_tokens: int = _int_env(
        "MAX_OUTPUT_TOKENS",
        400,
    )

    temperature: float = _float_env(
        "TEMPERATURE",
        0.1,
    )


settings = Settings()