from typing import Any


# ============================================================
# Final Decision
# ============================================================

CONFIRMED = "CONFIRMED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REJECTED = "REJECTED"


# ============================================================
# Prompt 재검증이 모두 부정했는지 확인
# ============================================================

def is_fully_rejected_by_prompts(
    hazard: dict[str, Any],
) -> bool:
    reverification_applied = bool(
        hazard.get("reverification_applied", False)
    )

    successful_votes = int(
        hazard.get("reverification_successful_votes", 0)
    )

    positive_votes = int(
        hazard.get("reverification_positive_votes", 0)
    )

    negative_votes = int(
        hazard.get("reverification_negative_votes", 0)
    )

    return (
        reverification_applied
        and successful_votes >= 2
        and positive_votes == 0
        and negative_votes == successful_votes
    )


# ============================================================
# Prompt 재검증이 모두 위험을 지지했는지 확인
# ============================================================

def is_fully_supported_by_prompts(
    hazard: dict[str, Any],
) -> bool:
    reverification_applied = bool(
        hazard.get("reverification_applied", False)
    )

    successful_votes = int(
        hazard.get("reverification_successful_votes", 0)
    )

    positive_votes = int(
        hazard.get("reverification_positive_votes", 0)
    )

    return (
        reverification_applied
        and successful_votes >= 2
        and positive_votes == successful_votes
    )


# ============================================================
# 단일 위험 Final Decision
# ============================================================

def determine_final_decision(
    hazard: dict[str, Any],
) -> tuple[str, str]:
    """
    최종 위험 판단 정책.

    ----------------------------------------------------------

    1. VLM에서 한 번도 탐지되지 않음
       → REJECTED

    2. 최소 Temporal 탐지 조건 미충족
       예: 1프레임에서만 탐지

       Prompt 0/2
       → REJECTED

       Prompt 2/2
       → REVIEW_REQUIRED

       Prompt 결과 혼재 / 실패
       → REVIEW_REQUIRED

    3. Temporal 조건 충족

       HIGH
       → CONFIRMED

       MEDIUM
       → REVIEW_REQUIRED

       LOW + Prompt 전부 부정
       → REJECTED

       그 외
       → REVIEW_REQUIRED

    ----------------------------------------------------------

    한 프레임 탐지만으로 자동 CONFIRMED하지 않는 이유:

    VLM의 순간적인 오탐 가능성이 있으므로
    Prompt 재검증이 성공하더라도
    사람 또는 추가 ROI 검증이 필요한 상태로 둔다.
    """

    detected = bool(hazard.get("detected", False))

    if not detected:
        return (
            REJECTED,
            "VLM에서 위험 후보가 탐지되지 않음",
        )

    # ========================================================
    # 정보
    # ========================================================

    meets_min_detection_count = bool(
        hazard.get("meets_min_detection_count", False)
    )

    final_label = hazard.get(
        "final_reliability_label",
        hazard.get("reliability_label", "LOW"),
    )

    prompt_rejected = is_fully_rejected_by_prompts(hazard)
    prompt_supported = is_fully_supported_by_prompts(hazard)

    # ========================================================
    # 1. 최소 Temporal 탐지 조건 미충족
    #
    # 예:
    #
    # 전체 영상에서 단 1프레임 탐지
    # ========================================================

    if not meets_min_detection_count:
        # ----------------------------------------------------
        # Prompt 재검증 2회 모두 위험 부정
        # ----------------------------------------------------

        if prompt_rejected:
            return (
                REJECTED,
                (
                    "단일 또는 소수 프레임에서 "
                    "위험 후보가 탐지되었으나 "
                    "독립적인 Prompt 재검증에서 "
                    "위험이 반복적으로 확인되지 않음"
                ),
            )

        # ----------------------------------------------------
        # Prompt 2회 모두 위험 재확인
        #
        # Temporal 근거가 부족하므로
        # 바로 CONFIRMED로 올리지는 않는다.
        # ----------------------------------------------------

        if prompt_supported:
            return (
                REVIEW_REQUIRED,
                (
                    "Temporal 최소 탐지 조건은 "
                    "충족하지 못했으나 "
                    "독립적인 Prompt 재검증에서 "
                    "위험이 반복 확인됨"
                ),
            )

        # ----------------------------------------------------
        # Prompt 결과가 섞였거나
        # 재검증 자체가 충분하지 않음
        # ----------------------------------------------------

        return (
            REVIEW_REQUIRED,
            (
                "위험이 일부 프레임에서 탐지되었으나 "
                "Temporal 근거가 부족하여 "
                "추가 확인이 필요함"
            ),
        )

    # ========================================================
    # 2. Temporal 최소 탐지 조건 충족
    # ========================================================

    if final_label == "HIGH":
        return (
            CONFIRMED,
            (
                "여러 프레임에서 위험이 반복 탐지되고 "
                "최종 신뢰도 또한 높아 "
                "위험으로 확정함"
            ),
        )

    # --------------------------------------------------------
    # MEDIUM
    # --------------------------------------------------------

    if final_label == "MEDIUM":
        return (
            REVIEW_REQUIRED,
            (
                "여러 프레임에서 위험이 탐지되었으나 "
                "최종 판단 신뢰도가 충분히 높지 않아 "
                "추가 확인이 필요함"
            ),
        )

    # ========================================================
    # 3. LOW
    # ========================================================

    if prompt_rejected:
        return (
            REJECTED,
            (
                "초기 위험 탐지는 존재했으나 "
                "Prompt 재검증에서 "
                "위험이 반복적으로 확인되지 않음"
            ),
        )

    return (
        REVIEW_REQUIRED,
        (
            "최종 신뢰도는 낮지만 "
            "위험을 완전히 배제할 근거가 "
            "충분하지 않음"
        ),
    )


# ============================================================
# 모든 위험에 Final Decision 추가
# ============================================================

def apply_final_decisions(
    hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


# ============================================================
# 실제 경고 대상으로 사용할 위험
# ============================================================

def get_actionable_hazards(
    hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    REJECTED만 제거한다.

    CONFIRMED
    REVIEW_REQUIRED

    는 모두 후속 처리 및 RAG 대상으로 유지한다.
    """

    return [
        hazard
        for hazard in hazards
        if hazard.get("final_decision")
        in {
            CONFIRMED,
            REVIEW_REQUIRED,
        }
    ]
