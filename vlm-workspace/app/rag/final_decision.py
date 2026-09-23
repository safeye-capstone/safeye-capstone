from typing import Any

CONFIRMED = "CONFIRMED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REJECTED = "REJECTED"


def is_fully_rejected_by_prompts(hazard: dict[str, Any]) -> bool:
    reverification_applied = bool(hazard.get("reverification_applied", False))
    successful_votes = int(hazard.get("reverification_successful_votes", 0))
    positive_votes = int(hazard.get("reverification_positive_votes", 0))
    negative_votes = int(hazard.get("reverification_negative_votes", 0))
    return (
        reverification_applied
        and successful_votes >= 2
        and positive_votes == 0
        and negative_votes == successful_votes
    )


def is_fully_supported_by_prompts(hazard: dict[str, Any]) -> bool:
    reverification_applied = bool(hazard.get("reverification_applied", False))
    successful_votes = int(hazard.get("reverification_successful_votes", 0))
    positive_votes = int(hazard.get("reverification_positive_votes", 0))
    return reverification_applied and successful_votes >= 2 and positive_votes == successful_votes


def determine_final_decision(hazard: dict[str, Any]) -> tuple[str, str]:
    """최소 탐지 조건과 재검증 결과에 따라 최종 판단한다."""
    if not bool(hazard.get("detected", False)):
        return REJECTED, "VLM에서 위험 후보가 탐지되지 않음"

    meets_min_detection_count = bool(hazard.get("meets_min_detection_count", False))
    final_label = hazard.get("final_reliability_label", hazard.get("reliability_label", "LOW"))
    prompt_rejected = is_fully_rejected_by_prompts(hazard)
    prompt_supported = is_fully_supported_by_prompts(hazard)

    if not meets_min_detection_count:
        if prompt_rejected:
            return (
                REJECTED,
                "단일 또는 소수 프레임에서 위험 후보가 탐지되었으나 "
                "독립적인 Prompt 재검증에서 위험이 반복적으로 확인되지 않음",
            )
        if prompt_supported:
            return (
                REVIEW_REQUIRED,
                "Temporal 최소 탐지 조건은 충족하지 못했으나 "
                "독립적인 Prompt 재검증에서 위험이 반복 확인됨",
            )
        return (
            REVIEW_REQUIRED,
            "위험이 일부 프레임에서 탐지되었으나 Temporal 근거가 부족하여 추가 확인이 필요함",
        )

    if final_label == "HIGH":
        return CONFIRMED, "여러 프레임에서 위험이 반복 탐지되고 최종 신뢰도 또한 높아 위험으로 확정함"
    if final_label == "MEDIUM":
        return REVIEW_REQUIRED, "여러 프레임에서 위험이 탐지되었으나 최종 판단 신뢰도가 충분히 높지 않아 추가 확인이 필요함"
    if prompt_rejected:
        return REJECTED, "초기 위험 탐지는 존재했으나 Prompt 재검증에서 위험이 반복적으로 확인되지 않음"
    return REVIEW_REQUIRED, "최종 신뢰도는 낮지만 위험을 완전히 배제할 근거가 충분하지 않음"


def apply_final_decisions(hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for hazard in hazards:
        decision, reason = determine_final_decision(hazard)
        results.append(
            {
                **hazard,
                "final_decision": decision,
                "final_decision_reason": reason,
                "final_decision_method": "temporal_prompt_policy_v2",
            }
        )
    return results


def get_actionable_hazards(hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """기각을 제외하고 확정 및 재검토 후보를 후속 처리에 유지한다."""
    return [
        hazard for hazard in hazards
        if hazard.get("final_decision") in {CONFIRMED, REVIEW_REQUIRED}
    ]
