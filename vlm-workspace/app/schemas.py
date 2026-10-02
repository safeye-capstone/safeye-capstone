"""VLM 분석 결과가 오가는 공통 스키마.

VLMInternal은 모델의 내부 분석 결과, VLMResponse는 백엔드 전달 응답이다.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["CRITICAL", "WARNING", "INFO"]

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


class ObservedObject(BaseModel):
    name: str
    attributes: list[str] = Field(default_factory=list)
    location: str = ""


class VLMInternal(BaseModel):
    observed_objects: list[ObservedObject] = Field(default_factory=list)
    spatial_relations: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    hazard_detected: bool = False
    hazard_type: str = "없음"
    severity: Severity = "INFO"
    reasoning: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class VLMResponse(BaseModel):
    is_danger: bool
    severity: Severity
    action_guide: str
    vlm_description: str
    violated_regulation: str
    ragMetadata: dict[str, Any] | None = Field(
        default=None,
        description="전체 및 위험별 최종 판단 상태, 일관성 점수, RAG 관련 부가 정보",
    )


# Ollama format 또는 OpenAI response_format에 사용하는 내부 응답 스키마.
INTERNAL_JSON_SCHEMA = VLMInternal.model_json_schema()
INTERNAL_JSON_SCHEMA["required"] = list(VLMInternal.model_fields)
INTERNAL_JSON_SCHEMA["$defs"]["ObservedObject"]["required"] = [
    "name",
    "attributes",
    "location",
]
