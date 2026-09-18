"""FastAPI 호환용 Schema import.

최종 API 응답 Schema의 실제 정의는
app.schemas에서 관리한다.
"""

from app.schemas import (
    Severity as SeverityType,
    VLMResponse as AIAnalysisResponse,
)


__all__ = [
    "SeverityType",
    "AIAnalysisResponse",
]