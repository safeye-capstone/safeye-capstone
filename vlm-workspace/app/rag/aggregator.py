import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

VALID_RISK_TYPES = (
    "NO_HELMET",
    "UNFASTENED_SAFETY_HARNESS",
    "FALL_HAZARD",
    "BLOCKED_PATH",
)

CONFIDENCE_SCORE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

# 한 번 탐지된 위험도 후보에서는 제거하지 않는다. 이 값은 위험을
# 확정적으로 지지하는 최소 프레임 수와 최종 confidence 계산에 사용한다.
MIN_DETECTION_COUNT = {
    "NO_HELMET": 2,
    "UNFASTENED_SAFETY_HARNESS": 2,
    "FALL_HAZARD": 2,
    "BLOCKED_PATH": 2,
}


def unique_strings(values: list[str]) -> list[str]:
    """빈 문자열을 제외하고 입력 순서를 유지하며 중복을 제거한다."""
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def normalize_risk_types(risk_type: str) -> list[str]:
    """`FALL_HAZARD | BLOCKED_PATH` 형태의 응답을 개별 위험으로 분리한다."""
    if not isinstance(risk_type, str) or not risk_type.strip():
        return []

    normalized = []
    for value in risk_type.replace(",", "|").split("|"):
        value = value.strip().upper()
        if value in VALID_RISK_TYPES and value not in normalized:
            normalized.append(value)
    return normalized


def calculate_max_consecutive_count(detection_flags: list[int]) -> int:
    """탐지가 끊기지 않고 이어진 최대 프레임 수를 반환한다."""
    max_count = 0
    current_count = 0
    for detected in detection_flags:
        if detected:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0
    return max_count


def calculate_temporal_support(detection_flags: list[int], window_size: int = 3) -> float:
    """가장 탐지가 집중된 연속 구간의 탐지 비율을 계산한다."""
    if not detection_flags:
        return 0.0
    if window_size < 1:
        raise ValueError("window_size는 1 이상이어야 합니다.")

    actual_window_size = min(window_size, len(detection_flags))
    best_detection_count = max(
        sum(detection_flags[start : start + actual_window_size])
        for start in range(len(detection_flags) - actual_window_size + 1)
    )
    return round(best_detection_count / actual_window_size, 3)


def _get_frame_timeline(
    frame_results: list[dict[str, Any]],
) -> tuple[list[tuple[str, list[dict[str, Any]] | None]], int]:
    """입력 순서를 보존한다. None은 미탐지가 아니라 분석 실패를 뜻한다."""
    timeline: list[tuple[str, list[dict[str, Any]] | None]] = []
    failed_count = 0

    for index, frame_result in enumerate(frame_results, start=1):
        if not isinstance(frame_result, dict):
            logger.warning("Aggregator 잘못된 프레임 결과 - index=%d", index)
            failed_count += 1
            timeline.append((f"frame_{index}", None))
            continue

        frame_name = str(frame_result.get("frame") or f"frame_{index}")
        hazards = frame_result.get("hazards")
        has_error = bool(frame_result.get("error") or frame_result.get("analysis_error"))
        if has_error or not isinstance(hazards, list):
            logger.warning("Aggregator 분석 실패 위치 유지 - frame=%s", frame_name)
            failed_count += 1
            timeline.append((frame_name, None))
            continue

        valid_hazards = [hazard for hazard in hazards if isinstance(hazard, dict)]
        malformed_count = len(hazards) - len(valid_hazards)
        if malformed_count:
            logger.warning(
                "Aggregator 잘못된 hazard 제외 - frame=%s count=%d",
                frame_name,
                malformed_count,
            )
        if hazards and not valid_hazards:
            failed_count += 1
            timeline.append((frame_name, None))
        else:
            timeline.append((frame_name, valid_hazards))

    return timeline, failed_count


def _collect_risk_buckets(
    timeline: list[tuple[str, list[dict[str, Any]] | None]],
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"frames": [], "evidence": [], "confidence_by_frame": {}}
    )

    for frame_index, (frame_name, hazards) in enumerate(timeline):
        if hazards is None:
            continue
        logger.debug("Aggregator frame=%s hazards=%d", frame_name, len(hazards))
        frame_seen_risks: set[str] = set()

        for hazard in hazards:
            if hazard.get("detected") is not True:
                continue

            raw_risk_type = hazard.get("risk_type", "")
            risk_types = normalize_risk_types(raw_risk_type)
            if not risk_types:
                logger.warning("Aggregator 잘못된 risk_type: %s", raw_risk_type)
                continue

            confidence = str(hazard.get("confidence", "LOW")).upper()
            confidence_score = CONFIDENCE_SCORE.get(confidence, CONFIDENCE_SCORE["LOW"])
            evidence = str(hazard.get("evidence") or "").strip()

            for risk_type in risk_types:
                bucket = buckets[risk_type]
                if risk_type not in frame_seen_risks:
                    bucket["frames"].append(frame_name)
                    frame_seen_risks.add(risk_type)
                if evidence:
                    bucket["evidence"].append(evidence)

                # 표시 이름이 같아도 서로 다른 입력 위치를 혼동하지 않는다.
                previous_score = bucket["confidence_by_frame"].get(frame_index, 0)
                bucket["confidence_by_frame"][frame_index] = max(
                    previous_score,
                    confidence_score,
                )

    return buckets


def _calculate_final_confidence(
    *,
    meets_min_detection_count: bool,
    average_score: float,
    temporal_support: float,
    detection_count: int,
) -> str:
    # HIGH는 기존 기준대로 최소 3개 프레임의 탐지 근거를 요구한다.
    if (
        meets_min_detection_count
        and detection_count >= 3
        and temporal_support >= 1.0
        and average_score >= 2.0
    ):
        return "HIGH"
    if meets_min_detection_count and temporal_support >= 0.66 and average_score >= 1.5:
        return "MEDIUM"
    return "LOW"


def aggregate_frame_results(
    frame_results: list[dict[str, Any]],
    min_detection_count: int = 2,
    temporal_window_size: int = 3,
) -> list[dict[str, Any]]:
    """여러 프레임의 VLM 결과를 위험 유형별로 통합한다.

    한 프레임에서만 탐지된 위험도 후보로 유지하지만 confidence는 LOW로
    제한한다. 실패 프레임은 탐지 비율의 분모에서 제외하지만 시간축에서는
    유지한다. 연속 탐지를 끊고 temporal support에는 지지 근거를 더하지 않는다.
    호출자는 실패 프레임도 원래 순서에 error와 함께 전달해야 한다.
    """
    if min_detection_count < 1:
        raise ValueError("min_detection_count는 1 이상이어야 합니다.")
    if temporal_window_size < 1:
        raise ValueError("temporal_window_size는 1 이상이어야 합니다.")
    if not frame_results:
        return []

    timeline, failed_frame_count = _get_frame_timeline(frame_results)
    total_frame_count = len(timeline) - failed_frame_count
    if not total_frame_count:
        logger.warning("Aggregator 정상 분석 프레임이 없습니다.")
        return []

    buckets = _collect_risk_buckets(timeline)
    aggregated_results = []

    for risk_type in VALID_RISK_TYPES:
        if risk_type not in buckets:
            continue

        data = buckets[risk_type]
        evidence_frames = unique_strings(data["frames"])
        detected_positions = set(data["confidence_by_frame"])
        detection_count = len(detected_positions)
        required_count = MIN_DETECTION_COUNT.get(risk_type, min_detection_count)
        meets_min_detection_count = detection_count >= required_count
        detection_ratio = round(detection_count / total_frame_count, 3)

        # 실패 위치의 0은 안전 판정이 아니라 탐지 근거가 없음을 의미한다.
        detection_flags = [int(index in detected_positions) for index in range(len(timeline))]
        temporal_support = calculate_temporal_support(
            detection_flags,
            window_size=temporal_window_size,
        )
        max_consecutive_count = calculate_max_consecutive_count(detection_flags)

        scores = list(data["confidence_by_frame"].values())
        average_score = round(sum(scores) / len(scores), 3) if scores else 1.0
        final_confidence = _calculate_final_confidence(
            meets_min_detection_count=meets_min_detection_count,
            average_score=average_score,
            temporal_support=temporal_support,
            detection_count=detection_count,
        )

        aggregated_results.append(
            {
                "risk_type": risk_type,
                "detected": True,
                "confidence": final_confidence,
                "detection_count": detection_count,
                "required_count": required_count,
                "meets_min_detection_count": meets_min_detection_count,
                "total_frame_count": total_frame_count,
                "input_frame_count": len(timeline),
                "failed_frame_count": failed_frame_count,
                "detection_ratio": detection_ratio,
                "temporal_support": temporal_support,
                "max_consecutive_detection_count": max_consecutive_count,
                "average_model_confidence_score": average_score,
                "evidence_frames": evidence_frames,
                "evidence": unique_strings(data["evidence"]),
            }
        )

    logger.info(
        "프레임 위험 통합 완료 - input=%d valid=%d failed=%d risks=%d",
        len(frame_results),
        total_frame_count,
        failed_frame_count,
        len(aggregated_results),
    )
    return aggregated_results
