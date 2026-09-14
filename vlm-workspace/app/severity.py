SEVERITY_ORDER = {
    "INFO": 1,
    "WARNING": 2,
    "CRITICAL": 3,
}


def get_detected_hazards(analysis: dict) -> list[dict]:
    return [
        hazard
        for hazard in analysis.get("hazards", [])
        if hazard.get("detected", False)
    ]


def has_elevated_worker(analysis: dict) -> bool:
    return any(
        worker.get("work_level") == "ELEVATED"
        for worker in analysis.get("workers", [])
    )


def calculate_severity(analysis: dict) -> str:
    """
    severity는 VLM confidence와 별개다.

    CRITICAL
    - 고소작업 안전대 미체결
    - 추락 위험 + 즉시/근접 노출
    - 안전모 미착용 + 즉시 추락 위험

    WARNING
    - 안전모 미착용
    - 통행로 장애
    - 즉시성은 낮지만 명확한 규정 위반

    INFO
    - 위험 없음
    - 재확인 수준
    """

    hazards = get_detected_hazards(analysis)

    if not hazards:
        return "INFO"

    risk_types = {
        hazard.get("risk_type")
        for hazard in hazards
    }

    # --------------------------------------------------------
    # 고소작업 안전대 미체결
    # --------------------------------------------------------

    if (
        "UNFASTENED_SAFETY_HARNESS" in risk_types
        and has_elevated_worker(analysis)
    ):
        return "CRITICAL"

    # --------------------------------------------------------
    # 직접적인 추락 위험
    # --------------------------------------------------------

    fall_hazards = [
        hazard
        for hazard in hazards
        if hazard.get("risk_type") == "FALL_HAZARD"
    ]

    for hazard in fall_hazards:
        if hazard.get("proximity") in {
            "IMMEDIATE",
            "NEAR",
        }:
            return "CRITICAL"

    # --------------------------------------------------------
    # 안전모 미착용 + 추락 위험 조합
    # --------------------------------------------------------

    if (
        "NO_HELMET" in risk_types
        and "FALL_HAZARD" in risk_types
    ):
        return "CRITICAL"

    # --------------------------------------------------------
    # 일반 명확한 위험
    # --------------------------------------------------------

    if (
        "NO_HELMET" in risk_types
        or "BLOCKED_PATH" in risk_types
        or "FALL_HAZARD" in risk_types
    ):
        return "WARNING"

    return "INFO"