"""단일 이미지의 위험 후보를 확정 경보와 구분해 전달한다."""

import json
from pathlib import Path

from app.api_schemas import AIAnalysisResponse
from app.local.ollama_client import analyze_image
from app.rag.query_builder import build_search_query, normalize_vlm_analysis
from app.rag.regulation_retriever import search_regulations
from app.response_builder import build_vlm_description


def parse_vlm_result(raw_response: str) -> dict:
    parsed = json.loads(raw_response)
    if not isinstance(parsed, dict):
        raise ValueError("VLM 이미지 응답은 JSON 객체여야 합니다.")
    return parsed


def search_related_regulations(analysis: dict) -> list[dict]:
    """탐지 후보와 관련된 참고 법령을 검색한다. 위반 확정을 의미하지 않는다."""
    all_results = []
    for hazard in analysis.get("hazards", []):
        if not hazard.get("detected", False):
            continue
        query = build_search_query(hazard)
        if not query:
            continue
        all_results.extend(search_regulations(query=query, final_top_k=3, per_collection_k=12))

    unique_results = []
    seen = set()
    for regulation in all_results:
        metadata = regulation.get("metadata") or {}
        key = (
            regulation.get("collection"),
            metadata.get("law_name"),
            metadata.get("article"),
            metadata.get("article_title"),
            regulation.get("id"),
        )
        if any(item is not None for item in key):
            if key in seen:
                continue
            seen.add(key)
        unique_results.append(regulation)
    return unique_results


def analyze_image_for_api(image_path: str | Path) -> AIAnalysisResponse:
    """한 장의 이미지에서 발견한 후보를 검토 대기로 저장한다.

    이미지에는 프레임 반복 탐지 근거가 없고 현재 VLM 응답에는 독립적인
    확정 검증 필드도 없다. 따라서 영상의 consistency 점수를 만들지 않는다.
    """
    analysis = normalize_vlm_analysis(parse_vlm_result(analyze_image(image_path)))
    detected_hazards = [
        hazard for hazard in analysis.get("hazards", [])
        if hazard.get("detected", False)
    ]
    review_required = bool(detected_hazards)
    regulations = search_related_regulations(analysis) if review_required else []
    decision_state = "REVIEW_REQUIRED" if review_required else "NO_DETECTION"

    description = build_vlm_description(analysis)
    if review_required:
        description = (
            f"{description} 단일 이미지에서 위험 후보가 탐지되었습니다. "
            "위험 확정 전 원본 이미지와 현장 상황을 추가 확인해야 합니다."
        )
        action_guide = "위험 후보를 현장 담당자가 확인하고 필요한 안전조치를 판단해 주세요."
    else:
        action_guide = "추가적인 즉시 조치는 필요하지 않으며 현장을 지속적으로 모니터링하세요."

    return AIAnalysisResponse(
        is_danger=False,
        severity="WARNING" if review_required else "INFO",
        vlm_description=description,
        violated_regulation="",
        action_guide=action_guide,
        ragMetadata={
            "vlm_decision_state": decision_state,
            "analysis_source": "single_image",
            "hazards": [
                {
                    **hazard,
                    "vlm_decision_state": decision_state,
                    "final_consistency_score": None,
                }
                for hazard in detected_hazards
            ],
            "related_regulations": regulations,
        },
    )
