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
        and int(hazard.get("reverification_unique_frames", 0)) >= 2
        and successful_votes >= 2
        and positive_votes == 0
        and negative_votes == successful_votes
    )


def is_fully_supported_by_prompts(hazard: dict[str, Any]) -> bool:
    reverification_applied = bool(hazard.get("reverification_applied", False))
    successful_votes = int(hazard.get("reverification_successful_votes", 0))
    positive_votes = int(hazard.get("reverification_positive_votes", 0))
    return (reverification_applied and int(hazard.get("reverification_unique_frames", 0)) >= 2
            and successful_votes >= 2 and positive_votes == successful_votes)


def determine_final_decision(hazard: dict[str, Any]) -> tuple[str, str]:
    """최소 탐지 조건과 재검증 결과에 따라 최종 판단한다."""
    if not bool(hazard.get("detected", False)):
        return REJECTED, "VLM에서 위험 후보가 탐지되지 않음"

    if hazard.get("risk_type") == "COLLAPSE":
        return REVIEW_REQUIRED, "정지 이미지의 쓰러짐 후보는 연속 프레임 자세 확인이 필요함"

    if hazard.get("observation_conflict_required"):
        return REVIEW_REQUIRED, "관찰 충돌 또는 동일 인물 대응 확인이 남아 자동 확정 보류"

    # Explicit observations from two different frames may resolve a LOW initial
    # candidate. The original self-confidence score remains audit metadata.
    if (hazard.get("confirmation_ready") and hazard.get("focused_confirmation_ready", False)):
        return CONFIRMED, "같은 시간 구간의 서로 다른 프레임에서 위험별 직접 관찰 조건이 재확인됨"

    if hazard.get("context_review_required"):
        return REVIEW_REQUIRED, "산업 작업 맥락이 불확실하여 위험 적용 여부를 검토해야 함"

    if hazard.get("visual_review_required"):
        return REVIEW_REQUIRED, "추락할 높이·개구부·가장자리 등의 구체적인 시각 근거가 부족하여 확인이 필요함"

    meets_min_detection_count = bool(hazard.get("meets_min_detection_count", False))
    final_label = hazard.get("final_reliability_label", hazard.get("reliability_label", "LOW"))
    prompt_rejected = is_fully_rejected_by_prompts(hazard)
    prompt_supported = is_fully_supported_by_prompts(hazard)

    if not meets_min_detection_count:
        if prompt_rejected:
            return (
                REJECTED,
                "단일 또는 소수 프레임에서 위험 후보가 탐지되었으나 "
                "서로 다른 프레임의 재검증에서 위험이 반복적으로 확인되지 않음",
            )
        if prompt_supported:
            return (
                REVIEW_REQUIRED,
                "Temporal 최소 탐지 조건은 충족하지 못했으나 "
                "서로 다른 프레임의 재검증에서 위험이 반복 확인됨",
            )
        return (
            REVIEW_REQUIRED,
            "위험이 일부 프레임에서 탐지되었으나 Temporal 근거가 부족하여 추가 확인이 필요함",
        )

    if final_label == "HIGH":
        if not hazard.get("confirmation_ready", False):
            count = hazard.get("confirmation_detection_count", 0)
            required = hazard.get("required_count", 2)
            return REVIEW_REQUIRED, f"필수 관찰 근거를 만족한 프레임이 부족하거나 같은 시간 구간에 모이지 않음({count}/{required}); 점수·재검증 동의만으로 확정하지 않음"
        return CONFIRMED, "여러 프레임에서 위험이 반복 탐지되고 최종 신뢰도 또한 높아 위험으로 확정함"
    if final_label == "MEDIUM":
        return REVIEW_REQUIRED, "여러 프레임에서 위험이 탐지되었으나 최종 판단 신뢰도가 충분히 높지 않아 추가 확인이 필요함"
    if prompt_rejected:
        return REJECTED, "초기 위험 탐지는 존재했으나 프레임 재검증에서 위험이 반복적으로 확인되지 않음"
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
                "final_decision_method": "temporal_focused_observation_v3",
            }
        )
    return results


def get_actionable_hazards(hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """기각을 제외하고 확정 및 재검토 후보를 후속 처리에 유지한다."""
    return [
        hazard for hazard in hazards
        if hazard.get("final_decision") in {CONFIRMED, REVIEW_REQUIRED}
    ]
