"""VLM 분석 결과가 오가는 공통 스키마.

VLMInternal:
    모델과 내부 백엔드 사이에서 사용하는 상세 분석 결과.

VLMResponse:
    FastAPI / Spring Backend에 전달하는 최종 5필드 응답.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ============================================================
# 공통 타입
# ============================================================

Severity = Literal[
    "CRITICAL",
    "WARNING",
    "INFO",
]


HAZARD_TYPES = [
    "떨어짐",
    "넘어짐",
    "부딪힘",
    "맞음",
    "끼임",
    "베임",
    "감전",
    "화재",
    "질식중독",
    "무너짐",
    "없음",
]


# ============================================================
# 내부 VLM 분석 Schema
# ============================================================

class ObservedObject(BaseModel):
    name: str

    attributes: list[str] = Field(
        default_factory=list
    )

    location: str = ""


class VLMInternal(BaseModel):
    observed_objects: list[ObservedObject] = Field(
        default_factory=list
    )

    spatial_relations: list[str] = Field(
        default_factory=list
    )

    uncertain: list[str] = Field(
        default_factory=list
    )

    hazard_detected: bool = False

    hazard_type: str = "없음"

    severity: Severity = "INFO"

    reasoning: str = ""

    recommended_actions: list[str] = Field(
        default_factory=list
    )

    references: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )


# ============================================================
# 최종 API 5필드 Schema
# ============================================================

class VLMResponse(BaseModel):
    is_danger: bool

    severity: Severity

    vlm_description: str

    violated_regulation: str

    action_guide: str


# ============================================================
# 내부 Ollama JSON Schema
# ============================================================

INTERNAL_JSON_SCHEMA = (
    VLMInternal.model_json_schema()
)

INTERNAL_JSON_SCHEMA[
    "required"
] = list(
    VLMInternal.model_fields
)

INTERNAL_JSON_SCHEMA[
    "$defs"
][
    "ObservedObject"
][
    "required"
] = [
    "name",
    "attributes",
    "location",
]