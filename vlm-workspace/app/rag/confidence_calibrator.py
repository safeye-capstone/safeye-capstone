from typing import Any


HIGH_THRESHOLD = 0.80
MEDIUM_THRESHOLD = 0.60

# Ground Truth 학습 기반 calibration이 아닌 heuristic weight
TEMPORAL_WEIGHT = 0.50
MODEL_CONFIDENCE_WEIGHT = 0.30
CONSECUTIVE_WEIGHT = 0.20


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """값을 지정 범위 안으로 제한한다."""
    return max(minimum, min(maximum, value))


def normalize_model_confidence(average_score: float) -> float:
    """Aggregator의 LOW=1, MEDIUM=2, HIGH=3 점수를 0~1로 정규화한다."""
    if average_score <= 0:
        return 0.0

    return round(clamp(average_score / 3.0), 3)


def calculate_consecutive_support(
    max_consecutive_count: int,
    total_frame_count: int,
    target_count: int = 3,
) -> float:
    """
    연속 탐지 점수를 계산한다.

    전체 프레임이 target_count보다 적으면
    실제 전체 프레임 수를 기준으로 정규화한다.
    """
    if max_consecutive_count <= 0 or total_frame_count <= 0 or target_count <= 0:
        return 0.0

    effective_target_count = min(target_count, total_frame_count)
    score = max_consecutive_count / effective_target_count

    return round(clamp(score), 3)


def calculate_consistency_score(
    temporal_support: float,
    model_confidence_score: float,
    consecutive_support: float,
) -> float:
    """
    Temporal consistency와 VLM confidence를 결합한
    heuristic consistency score를 계산한다.
    """
    score = (
        TEMPORAL_WEIGHT * temporal_support
        + MODEL_CONFIDENCE_WEIGHT * model_confidence_score
        + CONSECUTIVE_WEIGHT * consecutive_support
    )

    return round(clamp(score), 3)


def score_to_label(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"

    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"

    return "LOW"


def apply_confidence_recalibration(
    aggregated_hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Aggregator 결과를 기반으로 1차 신뢰도를 재평가한다.

    - 최소 탐지 프레임 조건 미충족 시 재검증
    - 최소 조건을 충족해도 HIGH가 아니면 재검증
    - LOW라는 이유만으로 위험 후보를 삭제하지 않음
    """
    recalibrated_results = []

    for hazard in aggregated_hazards:
        detected = bool(hazard.get("detected", False))
        temporal_support = float(hazard.get("temporal_support", 0.0))
        average_model_score = float(
            hazard.get("average_model_confidence_score", 1.0)
        )
        max_consecutive_count = int(
            hazard.get("max_consecutive_detection_count", 0)
        )
        total_frame_count = int(hazard.get("total_frame_count", 0))
        meets_min_detection_count = bool(
            hazard.get("meets_min_detection_count", False)
        )

        normalized_model_confidence = normalize_model_confidence(
            average_model_score
        )

        consecutive_support = calculate_consecutive_support(
            max_consecutive_count=max_consecutive_count,
            total_frame_count=total_frame_count,
        )

        consistency_score = calculate_consistency_score(
            temporal_support=temporal_support,
            model_confidence_score=normalized_model_confidence,
            consecutive_support=consecutive_support,
        )

        reliability_label = score_to_label(consistency_score)

        if not detected:
            needs_reverification = False
            reverification_reason = "NO_DETECTION"
        elif not meets_min_detection_count:
            needs_reverification = True
            reverification_reason = "MIN_DETECTION_COUNT_NOT_MET"
        elif reliability_label != "HIGH":
            needs_reverification = True
            reverification_reason = "RELIABILITY_BELOW_HIGH"
        else:
            needs_reverification = False
            reverification_reason = "HIGH_RELIABILITY"

        recalibrated_results.append(
            {
                **hazard,
                "normalized_model_confidence": normalized_model_confidence,
                "consecutive_support": consecutive_support,
                "consistency_score": consistency_score,
                "reliability_label": reliability_label,
                "needs_reverification": needs_reverification,
                "reverification_reason": reverification_reason,
                "confidence_method": "heuristic_temporal_v3",
            }
        )

    return recalibrated_results