from typing import Any


# ============================================================
# 위험 유형
# ============================================================

FALL_HAZARD = "FALL_HAZARD"
HARNESS_HAZARD = "UNFASTENED_SAFETY_HARNESS"


# ============================================================
# 안전대 위험과 별개로 존재할 수 있는
# 독립적인 추락 위험 키워드
#
# 이런 표현이 FALL_HAZARD evidence에 있으면
# 단순히 안전대 위반의 파생 위험으로 보지 않는다.
# ============================================================

INDEPENDENT_FALL_KEYWORDS = {
    "개구부",
    "단부",
    "안전난간",
    "난간 미설치",
    "난간이 없음",
    "덮개 미설치",
    "덮개가 없음",
    "작업발판 불안정",
    "불안정한 작업발판",
    "발판 없음",
    "추락방호망 미설치",
    "추락방호망이 없음",
}


# ============================================================
# 안전대 위반과 연결된 FALL_HAZARD인지
# 확인하는 키워드
# ============================================================

HARNESS_RELATED_KEYWORDS = {
    "안전대",
    "안전고리",
    "부착설비",
    "미체결",
    "체결하지",
    "체결되지",
    "안전대 미착용",
}


# ============================================================
# Utility
# ============================================================

def normalize_evidence(
    hazard: dict[str, Any],
) -> list[str]:
    """evidence를 항상 list[str] 형태로 변환한다."""

    evidence = hazard.get("evidence", [])

    if isinstance(evidence, str):
        evidence = [evidence]

    if not isinstance(evidence, list):
        return []

    return [
        str(item).strip()
        for item in evidence
        if str(item).strip()
    ]


def build_evidence_text(
    hazard: dict[str, Any],
) -> str:
    """evidence 전체를 하나의 문자열로 합친다."""

    return " ".join(normalize_evidence(hazard))


# ============================================================
# 프레임 겹침 정도
#
# 예:
#
# FALL:
# frame1 frame2 frame3
#
# HARNESS:
# frame1 frame2 frame3
#
# → 1.0
#
# FALL:
# frame1 frame2 frame3
#
# HARNESS:
# frame3 frame4
#
# → 0.5
#
# 작은 집합을 기준으로 overlap을 계산한다.
# ============================================================

def calculate_frame_overlap(
    hazard_a: dict[str, Any],
    hazard_b: dict[str, Any],
) -> float:
    frames_a = set(hazard_a.get("evidence_frames", []))
    frames_b = set(hazard_b.get("evidence_frames", []))

    if not frames_a or not frames_b:
        return 0.0

    intersection = frames_a & frames_b
    denominator = min(len(frames_a), len(frames_b))

    if denominator == 0:
        return 0.0

    return round(len(intersection) / denominator, 3)


# ============================================================
# FALL_HAZARD가 안전대 위반에서 파생된 것인지 확인
# ============================================================

def is_harness_related_fall(
    fall_hazard: dict[str, Any],
    harness_hazard: dict[str, Any],
) -> bool:
    """
    다음 조건을 모두 만족하면:

    FALL_HAZARD
    =
    UNFASTENED_SAFETY_HARNESS에서 파생된
    상위 위험이라고 판단한다.

    조건:

    1. 안전대 위험이 CONFIRMED
    2. 두 위험의 프레임이 충분히 겹침
    3. FALL evidence에 안전대 관련 표현이 있음
    4. 개구부/난간 등 독립적인 추락 위험 근거가 없음
    """

    # --------------------------------------------------------
    # 안전대 위험이 확정되어 있어야 한다.
    # --------------------------------------------------------

    if harness_hazard.get("final_decision") != "CONFIRMED":
        return False

    # --------------------------------------------------------
    # 프레임 overlap
    # --------------------------------------------------------

    frame_overlap = calculate_frame_overlap(
        fall_hazard,
        harness_hazard,
    )

    if frame_overlap < 0.5:
        return False

    # --------------------------------------------------------
    # FALL evidence
    # --------------------------------------------------------

    evidence_text = build_evidence_text(fall_hazard).lower()

    # --------------------------------------------------------
    # 안전대 관련 근거가 있는지
    # --------------------------------------------------------

    has_harness_evidence = any(
        keyword.lower() in evidence_text
        for keyword in HARNESS_RELATED_KEYWORDS
    )

    if not has_harness_evidence:
        return False

    # --------------------------------------------------------
    # 독립적인 추락 위험 근거가 있으면
    # 두 위험을 분리한다.
    # --------------------------------------------------------

    has_independent_fall_evidence = any(
        keyword.lower() in evidence_text
        for keyword in INDEPENDENT_FALL_KEYWORDS
    )

    if has_independent_fall_evidence:
        return False

    return True


# ============================================================
# 위험 관계 통합
# ============================================================

def consolidate_related_hazards(
    hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    FALL_HAZARD와
    UNFASTENED_SAFETY_HARNESS가
    같은 사건에서 나온 중복 위험인지 판단한다.

    중복이라면:

    UNFASTENED_SAFETY_HARNESS
    → primary

    FALL_HAZARD
    → related / secondary

    단, 데이터를 삭제하지는 않는다.
    """

    results = [
        {
            **hazard,
            "is_primary_hazard": True,
            "parent_risk_type": None,
            "related_hazards": list(
                hazard.get("related_hazards", [])
            ),
            "relation_reason": None,
        }
        for hazard in hazards
    ]

    fall_hazard = None
    harness_hazard = None

    for hazard in results:
        risk_type = hazard.get("risk_type")

        if risk_type == FALL_HAZARD:
            fall_hazard = hazard

        elif risk_type == HARNESS_HAZARD:
            harness_hazard = hazard

    # 둘 중 하나가 없으면 관계 통합 불필요
    if fall_hazard is None or harness_hazard is None:
        return results

    # REJECTED는 관계 대상으로 사용하지 않는다.
    if fall_hazard.get("final_decision") == "REJECTED":
        return results

    if harness_hazard.get("final_decision") == "REJECTED":
        return results

    # ========================================================
    # 같은 사건에서 나온 위험인지 판정
    # ========================================================

    if not is_harness_related_fall(
        fall_hazard,
        harness_hazard,
    ):
        return results

    # ========================================================
    # 안전대 위반을 Primary Hazard로 지정
    # ========================================================

    harness_hazard["related_hazards"] = list(
        dict.fromkeys(
            harness_hazard["related_hazards"]
            + [FALL_HAZARD]
        )
    )

    harness_hazard["relation_reason"] = (
        "안전대 미착용 또는 안전고리 미체결로 인해 "
        "추락 위험이 파생된 동일 사건으로 판단됨"
    )

    # ========================================================
    # FALL_HAZARD는 Secondary Hazard
    # ========================================================

    fall_hazard["is_primary_hazard"] = False
    fall_hazard["parent_risk_type"] = HARNESS_HAZARD
    fall_hazard["relation_reason"] = (
        "독립적인 개구부·난간·발판 위험보다는 "
        "안전대 위반에서 파생된 추락 위험으로 판단됨"
    )

    return results


# ============================================================
# 사용자 경고 / RAG 대상으로 사용할
# Primary Hazard만 추출
# ============================================================

def get_primary_actionable_hazards(
    hazards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    다음 조건을 만족하는 위험만 반환한다.

    1. REJECTED가 아님
    2. Primary Hazard임

    따라서 중복된 FALL_HAZARD는
    기록에는 남지만 사용자 경고와
    RAG 검색에서는 제외된다.
    """

    return [
        hazard
        for hazard in hazards
        if (
            hazard.get("final_decision")
            in {
                "CONFIRMED",
                "REVIEW_REQUIRED",
            }
            and hazard.get("is_primary_hazard", True)
        )
    ]
