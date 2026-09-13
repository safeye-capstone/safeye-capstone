from pathlib import Path

from app.api_schemas import (
    AIAnalysisResponse,
)

from app.pipeline import (
    analyze_video,
)

from app.response_builder import (
    build_action_guide,
    build_violated_regulation,
)


RISK_LABELS = {
    "NO_HELMET": "안전모 미착용",
    "UNFASTENED_SAFETY_HARNESS": "안전대 또는 안전고리 미체결",
    "FALL_HAZARD": "추락 위험",
    "BLOCKED_PATH": "통행로 장애",
}


def get_final_hazards(
    result: dict,
) -> list[dict]:
    """
    pipeline.py에서 RAG까지 완료된
    최종 경고 대상만 가져온다.
    """

    return result.get(
        "hazards",
        [],
    )


def calculate_video_severity(
    result: dict,
) -> str:
    """
    영상 전체 분석 결과 기준 severity 산정.

    severity는 confidence와 별개이며
    사고 발생 시 영향 수준을 의미한다.
    """

    hazards = get_final_hazards(
        result
    )

    if not hazards:
        return "INFO"

    risk_types = {
        hazard.get("risk_type")
        for hazard in hazards
    }

    # 고소작업 안전대 문제 또는
    # 실제 추락 위험
    if (
        "UNFASTENED_SAFETY_HARNESS"
        in risk_types
        or
        "FALL_HAZARD"
        in risk_types
    ):
        return "CRITICAL"

    # 일반적인 명확한 안전 위반
    if (
        "NO_HELMET"
        in risk_types
        or
        "BLOCKED_PATH"
        in risk_types
    ):
        return "WARNING"

    return "WARNING"


def build_video_description(
    result: dict,
) -> str:
    """
    영상 파이프라인의 최종 위험을
    사람이 읽을 수 있는 설명으로 만든다.
    """

    hazards = get_final_hazards(
        result
    )

    if not hazards:
        return (
            "영상에서 최종 경고 대상으로 "
            "확정된 위험이 확인되지 않았습니다."
        )

    descriptions = []

    for hazard in hazards:

        risk_type = hazard.get(
            "risk_type",
            "UNKNOWN",
        )

        risk_label = RISK_LABELS.get(
            risk_type,
            risk_type,
        )

        evidence = hazard.get(
            "evidence",
            [],
        )

        if isinstance(
            evidence,
            str,
        ):
            evidence_list = [
                evidence
            ]

        elif isinstance(
            evidence,
            list,
        ):
            evidence_list = [
                str(item).strip()
                for item in evidence
                if str(item).strip()
            ]

        else:
            evidence_list = []

        if evidence_list:

            descriptions.append(
                f"{risk_label}: "
                f"{evidence_list[0]}"
            )

        else:

            descriptions.append(
                f"{risk_label} 위험이 "
                "확인되었습니다."
            )

    return (
        "영상 분석 결과 다음 위험이 "
        "확인되었습니다. "
        + " / ".join(
            descriptions[:3]
        )
    )


def collect_regulations(
    result: dict,
) -> list[dict]:
    """
    각 위험에 연결된 RAG 법령을 모으고
    동일 법령/조항을 제거한다.
    """

    hazards = get_final_hazards(
        result
    )

    collected = []

    seen = set()

    for hazard in hazards:

        regulations = hazard.get(
            "regulations",
            [],
        )

        for regulation in regulations:

            metadata = regulation.get(
                "metadata",
                {},
            )

            key = (
                metadata.get(
                    "law_name"
                ),
                metadata.get(
                    "article"
                ),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            collected.append(
                regulation
            )

    return collected


def analyze_video_for_api(
    video_path: str | Path,
) -> AIAnalysisResponse:
    """
    기존 영상 분석 pipeline을 실행하고
    Backend 통신용 5개 필드로 변환한다.

    주의:
    전달된 영상은 VIDEO_DIR 안에 있어야 한다.
    """

    video_path = Path(
        video_path
    )

    # ---------------------------------------------------------
    # 1. 기존 영상 분석 Pipeline
    # ---------------------------------------------------------

    result = analyze_video(
        video_path.name
    )

    # ---------------------------------------------------------
    # 2. 최종 위험
    # ---------------------------------------------------------

    hazards = get_final_hazards(
        result
    )

    is_danger = bool(
        hazards
    )

    # ---------------------------------------------------------
    # 3. severity
    # ---------------------------------------------------------

    severity = calculate_video_severity(
        result
    )

    # ---------------------------------------------------------
    # 4. RAG 법령
    # ---------------------------------------------------------

    regulations = collect_regulations(
        result
    )

    # ---------------------------------------------------------
    # 5. response_builder가 사용할 최소 구조
    # ---------------------------------------------------------

    response_analysis = {
        "hazards": hazards,
    }

    # ---------------------------------------------------------
    # 6. Backend 통신용 5필드
    # ---------------------------------------------------------

    return AIAnalysisResponse(

        is_danger=is_danger,

        severity=severity,

        vlm_description=
            build_video_description(
                result
            ),

        violated_regulation=
            build_violated_regulation(
                regulations
            ),

        action_guide=
            build_action_guide(
                response_analysis,
                severity,
            ),
    )