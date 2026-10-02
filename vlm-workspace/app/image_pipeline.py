"""기존 이미지 위험 판단을 유지하고 불확실한 후보를 검토 대기로 구분한다."""

import json
from copy import deepcopy
from pathlib import Path

from app.api_schemas import AIAnalysisResponse
from app.local.ollama_client import analyze_image
from app.rag.query_builder import (
    build_search_query,
    normalize_vlm_analysis,
    split_risk_types,
)
from app.rag.regulation_retriever import search_regulations
from app.response_builder import (
    build_action_guide,
    build_violated_regulation,
    build_vlm_description,
)
from app.severity import calculate_severity

HARNESS_RISK = "UNFASTENED_SAFETY_HARNESS"
HARNESS_VIOLATIONS = {"NOT_WEARING", "WORN_NOT_CONNECTED"}


def parse_vlm_result(raw_response: str) -> dict:
    parsed = json.loads(raw_response)
    if not isinstance(parsed, dict):
        raise ValueError("VLM 이미지 응답은 JSON 객체여야 합니다.")
    return parsed


def search_related_regulations(analysis: dict) -> list[dict]:
    """관련 법령을 검색한다. 검색 결과 자체는 위반 확정 근거가 아니다."""
    results = []
    for hazard in analysis.get("hazards", []):
        if not hazard.get("detected", False):
            continue
        query = build_search_query(hazard)
        if query:
            results.extend(search_regulations(query=query, final_top_k=3, per_collection_k=12))

    unique_results = []
    seen = set()
    for regulation in results:
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


def classify_image_hazards(raw_analysis: dict, analysis: dict) -> list[dict]:
    """LOW와 관련 상태가 불확실한 후보만 보류한다. 시간축 점수는 만들지 않는다."""
    raw_candidates = {}
    for hazard in raw_analysis.get("hazards", []):
        if not hazard.get("detected", False):
            continue
        for risk_type in split_risk_types(hazard.get("risk_type", "")):
            raw_candidates.setdefault(risk_type, []).append(hazard)

    workers = analysis.get("workers", [])
    definite_helmet = any(worker.get("helmet") == "NOT_WEARING" for worker in workers)
    uncertain_helmet = any(worker.get("helmet", "UNCERTAIN") == "UNCERTAIN" for worker in workers)
    definite_harness = any(
        worker.get("work_level") == "ELEVATED"
        and worker.get("harness") in HARNESS_VIOLATIONS
        for worker in workers
    )
    uncertain_harness = not workers or any(
        worker.get("work_level", "UNCERTAIN") == "UNCERTAIN"
        or (
            worker.get("work_level") == "ELEVATED"
            and worker.get("harness", "UNCERTAIN") == "UNCERTAIN"
        )
        for worker in workers
    )

    candidates = [dict(hazard) for hazard in analysis.get("hazards", []) if hazard.get("detected", False)]
    # 정규화에서 제거된 안전대 후보 중, 불확실해서 확정하지 못한 후보만 복원한다.
    # 지상 작업 등 명확히 적용 대상이 아닌 경우와 단순 UNCERTAIN 상태는 후보를 생성하지 않는다.
    if not definite_harness and uncertain_harness:
        for hazard in raw_candidates.get(HARNESS_RISK, []):
            candidates.append({**hazard, "risk_type": HARNESS_RISK, "detected": True})

    results = []
    for hazard in candidates:
        risk_type = hazard.get("risk_type")
        originals = raw_candidates.get(risk_type, [])
        confidence = hazard.get("confidence", "LOW")
        if confidence not in {"LOW", "MEDIUM", "HIGH"}:
            confidence = "LOW"
        # worker 보완에서 붙인 HIGH가 원래 LOW 후보의 보류 정책을 우회하지 않도록 한다.
        raw_only_low = bool(originals) and all(
            item.get("confidence", "LOW") not in {"MEDIUM", "HIGH"}
            for item in originals
        )
        reason = None
        if confidence == "LOW" or raw_only_low:
            reason = "모델 위험 판단의 신뢰도가 LOW여서 추가 확인이 필요함"
        if risk_type == "NO_HELMET" and not definite_helmet and uncertain_helmet:
            reason = "작업자의 안전모 착용 상태가 불확실하여 추가 확인이 필요함"
        if risk_type == HARNESS_RISK and not definite_harness:
            reason = "고소작업 여부 또는 안전대 착용·체결 상태가 명확하지 않음"
        decision = "REVIEW_REQUIRED" if reason else "CONFIRMED"
        results.append({
            **hazard,
            "confidence": confidence,
            "final_decision": decision,
            "vlm_decision_state": decision,
            "final_decision_reason": reason or "기존 이미지 위험 판단 조건을 충족함",
            "final_decision_method": "single_image_uncertainty_policy_v1",
            "final_consistency_score": None,
        })
    return results


def analyze_image_for_api(image_path: str | Path) -> AIAnalysisResponse:
    raw_analysis = parse_vlm_result(analyze_image(image_path))
    analysis = normalize_vlm_analysis(deepcopy(raw_analysis))
    hazards = classify_image_hazards(raw_analysis, analysis)
    confirmed = [hazard for hazard in hazards if hazard["final_decision"] == "CONFIRMED"]
    pending = [hazard for hazard in hazards if hazard["final_decision"] == "REVIEW_REQUIRED"]
    confirmed_analysis = {**analysis, "hazards": confirmed}
    pending_analysis = {**analysis, "hazards": pending}

    # 검토 후보의 법령이 확정 위험의 violated_regulation에 섞이지 않도록 검색을 구분한다.
    confirmed_regulations = search_related_regulations(confirmed_analysis) if confirmed else []
    pending_regulations = search_related_regulations(pending_analysis) if pending else []
    decision_state = "CONFIRMED" if confirmed else "REVIEW_REQUIRED" if pending else "NO_DETECTION"
    severity = calculate_severity(confirmed_analysis) if confirmed else "WARNING" if pending else "INFO"

    description = build_vlm_description(confirmed_analysis) if confirmed or not pending else ""
    if pending:
        evidence = [str(hazard.get("evidence") or "").strip() for hazard in pending]
        evidence = list(dict.fromkeys(item for item in evidence if item))
        review_text = "검토 대기: 위험 후보의 원본 이미지와 현장 상황을 추가 확인해야 합니다."
        if evidence:
            review_text += " 후보 관찰 근거: " + " / ".join(evidence[:3])
        if not confirmed:
            scene = str(analysis.get("scene_description") or "").strip()
            description = scene
        description = " ".join(item for item in (description, review_text) if item)

    action_guide = build_action_guide(confirmed_analysis, severity) if confirmed or not pending else ""
    if pending:
        action_guide = " ".join(item for item in (
            action_guide,
            "검토 대기 후보는 현장 담당자가 확인하고 필요한 안전조치를 판단해 주세요.",
        ) if item)

    return AIAnalysisResponse(
        is_danger=bool(confirmed),
        severity=severity,
        vlm_description=description,
        violated_regulation=build_violated_regulation(confirmed_regulations),
        action_guide=action_guide,
        ragMetadata={
            "vlm_decision_state": decision_state,
            "analysis_source": "single_image",
            "hazards": hazards,
            "related_regulations": confirmed_regulations + pending_regulations,
            "confirmed_regulations": confirmed_regulations,
            "review_required_regulations": pending_regulations,
            "raw_hazards": raw_analysis.get("hazards", []),
        },
    )
