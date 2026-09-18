import json
from pathlib import Path

from app.api_schemas import AIAnalysisResponse
from app.local.ollama_client import analyze_image
from app.rag.query_builder import (
    build_search_query,
    normalize_vlm_analysis,
)
from app.rag.regulation_retriever import search_regulations
from app.response_builder import (
    build_action_guide,
    build_violated_regulation,
    build_vlm_description,
)
from app.severity import calculate_severity


def parse_vlm_result(raw_response: str) -> dict:
    return json.loads(raw_response)


def search_related_regulations(
    analysis: dict,
) -> list[dict]:
    all_results = []

    for hazard in analysis.get("hazards", []):
        if not hazard.get("detected", False):
            continue

        query = build_search_query(hazard)

        if not query:
            continue

        results = search_regulations(
            query=query,
            final_top_k=3,
            per_collection_k=12,
        )

        all_results.extend(results)

    # --------------------------------------------------------
    # 법령 + 조문 기준 중복 제거
    # --------------------------------------------------------

    unique_results = []
    seen = set()

    for result in all_results:
        metadata = result.get("metadata", {})

        key = (
            metadata.get("law_name"),
            metadata.get("article"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(result)

    return unique_results


def analyze_image_for_api(
    image_path: str | Path,
) -> AIAnalysisResponse:
    # --------------------------------------------------------
    # 1. VLM
    # --------------------------------------------------------

    raw_response = analyze_image(image_path)
    analysis = parse_vlm_result(raw_response)

    # --------------------------------------------------------
    # 2. 위험 정규화
    # --------------------------------------------------------

    analysis = normalize_vlm_analysis(analysis)

    # --------------------------------------------------------
    # 3. 위험 여부
    # --------------------------------------------------------

    detected_hazards = [
        hazard
        for hazard in analysis.get("hazards", [])
        if hazard.get("detected", False)
    ]

    is_danger = bool(detected_hazards)

    # --------------------------------------------------------
    # 4. severity 규칙 기반 산정
    # --------------------------------------------------------

    severity = calculate_severity(analysis)

    # --------------------------------------------------------
    # 5. RAG
    # --------------------------------------------------------

    regulations = (
        search_related_regulations(analysis)
        if is_danger
        else []
    )

    # --------------------------------------------------------
    # 6. API 5필드 구성
    # --------------------------------------------------------

    return AIAnalysisResponse(
        is_danger=is_danger,
        severity=severity,
        vlm_description=build_vlm_description(analysis),
        violated_regulation=build_violated_regulation(regulations),
        action_guide=build_action_guide(
            analysis,
            severity,
        ),
    )