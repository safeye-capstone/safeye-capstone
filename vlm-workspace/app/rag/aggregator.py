from collections import defaultdict
from typing import Any


# ============================================================
# 위험 유형 설정
# ============================================================

VALID_RISK_TYPES = {
    "NO_HELMET",
    "UNFASTENED_SAFETY_HARNESS",
    "FALL_HAZARD",
    "BLOCKED_PATH",
}


# ============================================================
# VLM confidence 점수
#
# 실제 확률이 아니라 내부 비교용 점수이다.
# ============================================================

CONFIDENCE_SCORE = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


# ============================================================
# Temporal 기준으로 위험을 충분히 확인했다고 볼
# 최소 탐지 프레임 수
#
# 중요:
# 이 값보다 적게 탐지됐다고 위험 후보를 삭제하지 않는다.
# 1회 탐지는 재검증 대상으로 유지한다.
# ============================================================

MIN_DETECTION_COUNT = {
    "NO_HELMET": 2,
    "UNFASTENED_SAFETY_HARNESS": 2,
    "FALL_HAZARD": 2,
    "BLOCKED_PATH": 2,
}


# ============================================================
# Utility
# ============================================================

def unique_strings(
    values: list[str],
) -> list[str]:
    """
    순서를 유지하면서 문자열 중복 제거
    """

    return list(
        dict.fromkeys(values)
    )


def normalize_risk_types(
    risk_type: str,
) -> list[str]:
    """
    VLM이 다음처럼 여러 위험 유형을 하나의 문자열로 반환한 경우:

    FALL_HAZARD | BLOCKED_PATH

    개별 risk_type으로 분리한다.
    """

    if not risk_type:
        return []

    values = (
        risk_type
        .replace(",", "|")
        .split("|")
    )

    normalized = []

    for value in values:

        value = value.strip()

        if value in VALID_RISK_TYPES:

            normalized.append(
                value
            )

    return normalized


# ============================================================
# 최대 연속 탐지 프레임 수
# ============================================================

def calculate_max_consecutive_count(
    detection_flags: list[int],
) -> int:
    """
    예:

    [1, 1, 1, 0]
    → 3

    [1, 0, 1, 0]
    → 1
    """

    max_count = 0
    current_count = 0

    for detected in detection_flags:

        if detected:

            current_count += 1

            max_count = max(
                max_count,
                current_count,
            )

        else:

            current_count = 0

    return max_count


# ============================================================
# Temporal Support
# ============================================================

def calculate_temporal_support(
    detection_flags: list[int],
    window_size: int = 3,
) -> float:
    """
    가장 위험이 집중된 연속 프레임 구간의
    탐지 일치도를 계산한다.

    예:

    [1, 1, 1] → 1.0
    [1, 1, 0] → 0.667
    [1, 0, 0] → 0.333
    """

    if not detection_flags:

        return 0.0

    actual_window_size = min(
        window_size,
        len(detection_flags),
    )

    best_support = 0.0

    for start_index in range(
        len(detection_flags)
        - actual_window_size
        + 1
    ):

        window = detection_flags[
            start_index:
            start_index
            + actual_window_size
        ]

        support = (
            sum(window)
            / len(window)
        )

        best_support = max(
            best_support,
            support,
        )

    return round(
        best_support,
        3,
    )


# ============================================================
# 여러 프레임 위험 통합
# ============================================================

def aggregate_frame_results(
    frame_results: list[dict[str, Any]],
    min_detection_count: int = 2,
    temporal_window_size: int = 3,
) -> list[dict[str, Any]]:
    """
    여러 프레임의 VLM 결과를 위험 유형별로 통합한다.

    핵심 변경점:

    기존:
        2프레임 미만 탐지
        → detected=False
        → 재검증도 못 하고 탈락

    변경:
        1프레임이라도 탐지
        → detected=True
        → 위험 후보로 유지

    대신:

        meets_min_detection_count

    필드로 Temporal 최소 탐지 조건 충족 여부를
    별도로 관리한다.
    """

    # ========================================================
    # 전체 프레임 순서
    # ========================================================

    frame_names = [

        frame_result.get(
            "frame",
            f"frame_{index}",
        )

        for index, frame_result
        in enumerate(
            frame_results,
            start=1,
        )
    ]

    total_frame_count = len(
        frame_names
    )

    # ========================================================
    # 위험 유형별 수집 공간
    # ========================================================

    buckets = defaultdict(
        lambda: {
            "frames": [],
            "evidence": [],

            # 같은 프레임에서 같은 위험이
            # 여러 번 생성되어도 confidence가
            # 중복 계산되지 않도록 프레임별 저장
            "confidence_by_frame": {},
        }
    )

    # ========================================================
    # 1. 프레임별 hazard 수집
    # ========================================================

    for frame_result in frame_results:

        frame_name = frame_result.get(
            "frame",
            "unknown",
        )

        hazards = frame_result.get(
            "hazards",
            [],
        )

        print(
            f"[Aggregator] "
            f"{frame_name}: "
            f"{len(hazards)}개 hazard"
        )

        frame_seen_risks = set()

        for hazard in hazards:

            detected = hazard.get(
                "detected",
                False,
            )

            if not detected:
                continue

            raw_risk_type = hazard.get(
                "risk_type",
                "",
            )

            risk_types = (
                normalize_risk_types(
                    raw_risk_type
                )
            )

            if not risk_types:

                print(
                    "[Aggregator 경고] "
                    f"잘못된 risk_type: "
                    f"{raw_risk_type}"
                )

                continue

            confidence = hazard.get(
                "confidence",
                "LOW",
            )

            if (
                confidence
                not in CONFIDENCE_SCORE
            ):

                confidence = "LOW"

            confidence_score = (
                CONFIDENCE_SCORE[
                    confidence
                ]
            )

            evidence = (
                hazard.get(
                    "evidence",
                    "",
                )
                or ""
            ).strip()

            for risk_type in risk_types:

                # --------------------------------------------
                # 동일 프레임 탐지 중복 방지
                # --------------------------------------------

                if (
                    risk_type
                    not in frame_seen_risks
                ):

                    buckets[
                        risk_type
                    ]["frames"].append(
                        frame_name
                    )

                    frame_seen_risks.add(
                        risk_type
                    )

                # --------------------------------------------
                # Evidence
                # --------------------------------------------

                if evidence:

                    buckets[
                        risk_type
                    ]["evidence"].append(
                        evidence
                    )

                # --------------------------------------------
                # 같은 프레임에서 동일 위험이 여러 번 나온 경우
                # 가장 높은 confidence만 사용
                # --------------------------------------------

                previous_score = (
                    buckets[
                        risk_type
                    ][
                        "confidence_by_frame"
                    ].get(
                        frame_name
                    )
                )

                if (
                    previous_score is None
                    or confidence_score
                    > previous_score
                ):

                    buckets[
                        risk_type
                    ][
                        "confidence_by_frame"
                    ][
                        frame_name
                    ] = confidence_score

    # ========================================================
    # 2. 위험 유형별 최종 통합
    # ========================================================

    aggregated_results = []

    for (
        risk_type,
        data,
    ) in buckets.items():

        evidence_frames = (
            unique_strings(
                data[
                    "frames"
                ]
            )
        )

        detection_count = len(
            evidence_frames
        )

        required_count = (
            MIN_DETECTION_COUNT.get(
                risk_type,
                min_detection_count,
            )
        )

        # ====================================================
        # 핵심 변경
        #
        # 한 프레임에서라도 실제 탐지됐다면
        # 위험 후보로 유지한다.
        #
        # detected는 이제
        # "최종 확정 위험"이 아니라
        # "VLM에서 발생한 위험 후보" 의미이다.
        # ====================================================

        detected = (
            detection_count >= 1
        )

        # ====================================================
        # 기존 최소 탐지 프레임 조건은
        # 별도 필드로 관리한다.
        # ====================================================

        meets_min_detection_count = (
            detection_count
            >= required_count
        )

        # ----------------------------------------------------
        # 전체 영상 대비 탐지 비율
        # ----------------------------------------------------

        if total_frame_count:

            detection_ratio = (
                detection_count
                / total_frame_count
            )

        else:

            detection_ratio = 0.0

        detection_ratio = round(
            detection_ratio,
            3,
        )

        # ====================================================
        # Temporal Flag
        # ====================================================

        evidence_frame_set = set(
            evidence_frames
        )

        detection_flags = [

            (
                1
                if frame_name
                in evidence_frame_set
                else 0
            )

            for frame_name
            in frame_names
        ]

        # ----------------------------------------------------
        # Temporal Support
        # ----------------------------------------------------

        temporal_support = (
            calculate_temporal_support(
                detection_flags,
                window_size=(
                    temporal_window_size
                ),
            )
        )

        # ----------------------------------------------------
        # 최대 연속 탐지
        # ----------------------------------------------------

        max_consecutive_count = (
            calculate_max_consecutive_count(
                detection_flags
            )
        )

        # ----------------------------------------------------
        # VLM confidence 평균
        # ----------------------------------------------------

        scores = list(
            data[
                "confidence_by_frame"
            ].values()
        )

        if scores:

            average_score = (
                sum(scores)
                / len(scores)
            )

        else:

            average_score = 1.0

        average_score = round(
            average_score,
            3,
        )

        # ====================================================
        # Aggregator confidence
        #
        # HIGH / MEDIUM은 최소 탐지 조건을 충족해야 한다.
        #
        # 단일 프레임 탐지는 VLM이 HIGH를 줬더라도
        # Aggregator 단계에서는 LOW로 유지하고
        # 이후 Prompt 재검증으로 보낸다.
        # ====================================================

        if (
            meets_min_detection_count

            and detection_count >= 3

            and temporal_support >= 1.0

            and average_score >= 2.0
        ):

            final_confidence = "HIGH"

        elif (
            meets_min_detection_count

            and temporal_support >= 0.66

            and average_score >= 1.5
        ):

            final_confidence = "MEDIUM"

        else:

            final_confidence = "LOW"

        # ====================================================
        # 결과
        # ====================================================

        aggregated_results.append(
            {
                "risk_type":
                    risk_type,

                # VLM이 한 번 이상 탐지한 위험 후보
                "detected":
                    detected,

                # Aggregator 단계 confidence
                "confidence":
                    final_confidence,

                "detection_count":
                    detection_count,

                "required_count":
                    required_count,

                # 핵심 신규 필드
                "meets_min_detection_count":
                    meets_min_detection_count,

                "total_frame_count":
                    total_frame_count,

                "detection_ratio":
                    detection_ratio,

                "temporal_support":
                    temporal_support,

                "max_consecutive_detection_count":
                    max_consecutive_count,

                "average_model_confidence_score":
                    average_score,

                "evidence_frames":
                    evidence_frames,

                "evidence":
                    unique_strings(
                        data[
                            "evidence"
                        ]
                    ),
            }
        )

    return aggregated_results