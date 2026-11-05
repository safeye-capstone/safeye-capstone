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
    if (not definite_harness and uncertain_harness
            and analysis.get("scene_context", {}).get("category") != "NON_INDUSTRIAL"):
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
        if hazard.get("visual_review_required"):
            reason = hazard.get("visual_review_reason", "위험의 구체적 시각 근거 확인이 필요함")
        if hazard.get("context_review_required"):
            reason = "산업 작업 맥락이 불확실하여 위험 적용 여부를 검토해야 함"
        if risk_type != "COLLAPSE" and not hazard.get("confirmation_eligible", False):
            reason = "위험별 필수 관찰 근거가 충분하지 않아 추가 확인이 필요함"
        if risk_type == "COLLAPSE":
            reason = "정지 이미지의 쓰러짐 후보는 연속 프레임 자세 확인이 필요함"
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


def verify_image_candidates(image_path: str | Path, hazards: list[dict], *, verifier=None) -> list[dict]:
    """A candidate needs a separate focused observation, not repeated full-scene tags."""
    from app.rag.spatial_review import review_candidate, pending
    verify = verifier
    results = []
    cache = {}
    for original in hazards:
        hazard = deepcopy(original)
        risk = hazard.get("risk_type")
        if risk == "COLLAPSE" or not hazard.get("detected"):
            results.append(hazard)
            continue
        try:
            if risk not in cache:
                cache[risk] = verify(Path(image_path), risk) if verify else review_candidate(Path(image_path), risk, hazard)
            checked = cache[risk]
            if hazard.get("review_context", {}).get("conflicts") and not checked.get("conflicts_resolved"):
                checked = pending(checked, "상충하는 관찰이 남아 자동 확정 보류")
                checked["verification_conflicts"] = hazard["review_context"]["conflicts"]
            hazard["focused_verification"] = checked
            if checked.get("confirmation_eligible"):
                hazard["initial_worker_ids"] = hazard.get("worker_ids", [])
                hazard["initial_evidence"] = hazard.get("evidence", "")
                hazard["initial_confirmation_missing"] = hazard.get("confirmation_missing", [])
                hazard.update(worker_ids=[], evidence=checked["evidence"], confirmation_missing=[])
                hazard.update(final_decision="CONFIRMED", vlm_decision_state="CONFIRMED",
                    confidence=checked["confidence"], confirmation_eligible=True,
                    visual_evidence=checked["visual_evidence"],
                    final_decision_reason="초기 후보가 위험별 직접 관찰에서 재확인됨",
                    final_decision_method="focused_observation_v1")
                # Checker IDs belong to its own response; never bind them to initial people.
                hazard["verified_evidence"] = checked["evidence"]
            elif checked.get("conclusive"):
                hazard.update(final_decision="REJECTED", vlm_decision_state="REJECTED",
                    confirmation_eligible=False, final_decision_reason="위험별 직접 관찰에서 후보가 확인되지 않음")
            else:
                hazard.update(final_decision="REVIEW_REQUIRED", vlm_decision_state="REVIEW_REQUIRED",
                    confirmation_eligible=False, final_decision_reason="직접 관찰에 불확실성이 남아 검토 필요")
        except Exception as error:
            hazard.update(final_decision="REVIEW_REQUIRED", vlm_decision_state="REVIEW_REQUIRED",
                focused_verification={"status":"ERROR", "error":str(error)},
                final_decision_reason="위험별 관찰 검증 실패로 검토 유지")
        results.append(hazard)
    return results


def analyze_image_for_api(image_path: str | Path) -> AIAnalysisResponse:
    from app.rag.focused_observation import analyze_candidates, prepare_frame_candidates
    raw_analysis = analyze_candidates(image_path, analyze_image)
    analysis = prepare_frame_candidates(image_path, raw_analysis)
    hazards = verify_image_candidates(image_path, classify_image_hazards(raw_analysis, analysis))
    from app.review_order import attach_review_order, REVIEW_ORDER_POLICY
    hazards, review_queue = attach_review_order(hazards)
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
            "review_queue": review_queue,
            "review_order_policy": REVIEW_ORDER_POLICY,
            "hazards": hazards,
            "related_regulations": confirmed_regulations + pending_regulations,
            "confirmed_regulations": confirmed_regulations,
            "review_required_regulations": pending_regulations,
            "raw_hazards": raw_analysis.get("hazards", []),
            "scene_context": analysis.get("scene_context"),
            "language_status": raw_analysis.get("language_status", "COMPLETED"),
            "ppe_candidate_observation": analysis.get("ppe_candidate_observation"),
            "context_exclusions": [hazard for hazard in analysis.get("hazards", [])
                                   if hazard.get("applicability_status") in {"NOT_INDUSTRIAL_CONTEXT", "POSTURE_CONTRADICTION"}
                                   and hazard.get("observed_detected")],
        },
    )
