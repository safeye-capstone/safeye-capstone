from typing import Any


# ============================================================
# Threshold
# ============================================================

HIGH_THRESHOLD = 0.80
MEDIUM_THRESHOLD = 0.60


# ============================================================
# Weight
#
# 현재는 Ground Truth 학습 기반 calibration이 아니므로
# heuristic weight이다.
# ============================================================

TEMPORAL_WEIGHT = 0.50
MODEL_CONFIDENCE_WEIGHT = 0.30
CONSECUTIVE_WEIGHT = 0.20


# ============================================================
# Utility
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """
    값을 지정 범위 안으로 제한한다.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ============================================================
# VLM confidence 평균 정규화
#
# Aggregator:
#
# LOW    = 1
# MEDIUM = 2
# HIGH   = 3
#
# → 0 ~ 1
# ============================================================

def normalize_model_confidence(
    average_score: float,
) -> float:

    if average_score <= 0:

        return 0.0

    normalized = (
        average_score
        / 3.0
    )

    return round(
        clamp(
            normalized
        ),
        3,
    )


# ============================================================
# 연속 탐지 점수
#
# 1프레임 → 0.333
# 2프레임 → 0.667
# 3프레임 이상 → 1.0
# ============================================================

def calculate_consecutive_support(
    max_consecutive_count: int,
    target_count: int = 3,
) -> float:

    if max_consecutive_count <= 0:

        return 0.0

    score = (
        max_consecutive_count
        / target_count
    )

    return round(
        clamp(
            score
        ),
        3,
    )


# ============================================================
# Consistency Score
# ============================================================

def calculate_consistency_score(
    temporal_support: float,
    model_confidence_score: float,
    consecutive_support: float,
) -> float:
    """
    현재 단계에서는 실제 정답 확률이 아니다.

    프레임 간 일관성과 VLM 판단을 결합한
    heuristic consistency score이다.
    """

    score = (
        TEMPORAL_WEIGHT
        * temporal_support

        +

        MODEL_CONFIDENCE_WEIGHT
        * model_confidence_score

        +

        CONSECUTIVE_WEIGHT
        * consecutive_support
    )

    return round(
        clamp(
            score
        ),
        3,
    )


# ============================================================
# Score → Label
# ============================================================

def score_to_label(
    score: float,
) -> str:

    if score >= HIGH_THRESHOLD:

        return "HIGH"

    if score >= MEDIUM_THRESHOLD:

        return "MEDIUM"

    return "LOW"


# ============================================================
# 전체 Confidence 재평가
# ============================================================

def apply_confidence_recalibration(
    aggregated_hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Aggregator 결과를 기반으로
    1차 신뢰도 재평가를 수행한다.

    핵심 정책:

    - 최소 탐지 프레임 조건을 충족하지 못하면
      반드시 재검증

    - 최소 조건을 충족해도
      reliability가 HIGH가 아니면 재검증

    - 단순히 LOW라는 이유로 위험 후보를 삭제하지 않는다.
    """

    recalibrated_results = []

    for hazard in aggregated_hazards:

        # ----------------------------------------------------
        # 위험 후보 여부
        # ----------------------------------------------------

        detected = bool(
            hazard.get(
                "detected",
                False,
            )
        )

        temporal_support = float(
            hazard.get(
                "temporal_support",
                0.0,
            )
        )

        average_model_score = float(
            hazard.get(
                "average_model_confidence_score",
                1.0,
            )
        )

        max_consecutive_count = int(
            hazard.get(
                "max_consecutive_detection_count",
                0,
            )
        )

        meets_min_detection_count = bool(
            hazard.get(
                "meets_min_detection_count",
                False,
            )
        )

        # ====================================================
        # Model Confidence 정규화
        # ====================================================

        normalized_model_confidence = (
            normalize_model_confidence(
                average_model_score
            )
        )

        # ====================================================
        # Consecutive Support
        # ====================================================

        consecutive_support = (
            calculate_consecutive_support(
                max_consecutive_count
            )
        )

        # ====================================================
        # Consistency Score
        # ====================================================

        consistency_score = (
            calculate_consistency_score(
                temporal_support=(
                    temporal_support
                ),
                model_confidence_score=(
                    normalized_model_confidence
                ),
                consecutive_support=(
                    consecutive_support
                ),
            )
        )

        reliability_label = (
            score_to_label(
                consistency_score
            )
        )

        # ====================================================
        # 재검증 판단
        #
        # 핵심 변경:
        #
        # 1프레임 탐지
        # → meets_min_detection_count=False
        # → 무조건 재검증
        # ====================================================

        if not detected:

            needs_reverification = False

            reverification_reason = (
                "NO_DETECTION"
            )

        elif not meets_min_detection_count:

            needs_reverification = True

            reverification_reason = (
                "MIN_DETECTION_COUNT_NOT_MET"
            )

        elif reliability_label != "HIGH":

            needs_reverification = True

            reverification_reason = (
                "RELIABILITY_BELOW_HIGH"
            )

        else:

            needs_reverification = False

            reverification_reason = (
                "HIGH_RELIABILITY"
            )

        # ====================================================
        # 결과
        # ====================================================

        recalibrated_results.append(
            {
                **hazard,

                "normalized_model_confidence":
                    normalized_model_confidence,

                "consecutive_support":
                    consecutive_support,

                "consistency_score":
                    consistency_score,

                "reliability_label":
                    reliability_label,

                "needs_reverification":
                    needs_reverification,

                "reverification_reason":
                    reverification_reason,

                "confidence_method":
                    "heuristic_temporal_v2",
            }
        )

    return recalibrated_results