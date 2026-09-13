from typing import Any


# ============================================================
# 지원하는 위험 유형
# ============================================================

VALID_RISK_TYPES = {
    "NO_HELMET",
    "UNFASTENED_SAFETY_HARNESS",
    "FALL_HAZARD",
    "BLOCKED_PATH",
}


# ============================================================
# 위험 유형별 RAG 기본 검색문
# ============================================================

SEARCH_QUERY_MAP = {

    "NO_HELMET": (
        "산업현장에서 근로자가 안전모를 착용하지 않은 상황. "
        "안전모, 보호구의 지급, 보호구 착용, "
        "머리 보호 및 낙하·비래 위험 관련 안전기준"
    ),

    "UNFASTENED_SAFETY_HARNESS": (
        "고소작업 중 안전대 사용 상태가 부적절한 상황. "
        "안전대 착용, 안전고리 체결, 안전대 부착설비, "
        "추락의 방지 및 고소작업 관련 안전기준"
    ),

    "FALL_HAZARD": (
        "산업현장에서 근로자의 추락 위험이 존재하는 상황. "
        "추락의 방지, 작업발판, 안전난간, 개구부, "
        "추락방호망, 안전대 및 고소작업 관련 안전기준"
    ),

    "BLOCKED_PATH": (
        "산업현장에서 작업자의 통행 경로 또는 작업장 통로가 "
        "자재, 장비 또는 장애물에 의해 방해되는 상황. "
        "통로의 설치, 안전한 통행, 작업장 출입구, "
        "통로 유지 및 장애물 제거 관련 안전기준"
    ),
}


# ============================================================
# Confidence 값
# ============================================================

CONFIDENCE_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


# ============================================================
# Proximity 값
# ============================================================

VALID_PROXIMITY = {
    "IMMEDIATE",
    "NEAR",
    "NOT_NEAR",
    "UNCERTAIN",
}


# ============================================================
# Risk Type 문자열 정리
# ============================================================

def split_risk_types(
    risk_type: str,
) -> list[str]:

    if not risk_type:
        return []

    values = (
        risk_type
        .replace(",", "|")
        .split("|")
    )

    return [
        value.strip()
        for value in values
        if value.strip() in VALID_RISK_TYPES
    ]


# ============================================================
# 작업자 상태 정규화
# ============================================================

def normalize_workers(
    analysis: dict[str, Any],
) -> None:
    """
    VLM이 서로 모순되는 worker 상태를 생성했을 때
    논리적으로 일관된 값으로 정규화한다.

    핵심 규칙:
    - GROUND 작업자는 안전대 판단 대상이 아니므로
      harness를 NOT_APPLICABLE로 강제한다.
    - ELEVATED / UNCERTAIN은 VLM의 원래 값을 유지한다.
    """

    workers = analysis.get(
        "workers",
        []
    )

    for worker in workers:

        work_level = worker.get(
            "work_level",
            "UNCERTAIN",
        )

        # ----------------------------------------------------
        # 지상 작업자는 안전대 판단 대상이 아님
        # ----------------------------------------------------

        if work_level == "GROUND":

            worker[
                "harness"
            ] = "NOT_APPLICABLE"


# ============================================================
# 실제 안전대 위반 작업자 확인
# ============================================================

def get_harness_violation_workers(
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    실제로 다음 두 조건을 모두 만족하는 작업자만 반환한다.

    1. ELEVATED
    2. NOT_WEARING 또는 WORN_NOT_CONNECTED

    UNCERTAIN은 위험으로 확정하지 않는다.
    """

    result = []

    for worker in analysis.get(
        "workers",
        []
    ):

        work_level = worker.get(
            "work_level",
            "UNCERTAIN",
        )

        harness = worker.get(
            "harness",
            "UNCERTAIN",
        )

        if (
            work_level == "ELEVATED"
            and harness in {
                "NOT_WEARING",
                "WORN_NOT_CONNECTED",
            }
        ):

            result.append(
                worker
            )

    return result


# ============================================================
# VLM 분석 결과 정규화
# ============================================================

def normalize_vlm_analysis(
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """
    VLM 결과를 후처리한다.

    주요 역할:
    1. worker 상태 논리 정규화
    2. hazard risk_type 정규화
    3. 안전모 미착용 보완
    4. 고소작업 안전대 미착용/미체결 보완
    5. 모순되는 안전대 위험 제거
    6. 중복 hazard 제거
    """

    # ========================================================
    # 1. Worker 상태 정규화
    # ========================================================

    normalize_workers(
        analysis
    )

    # 실제 고소작업 + 안전대 위반 작업자
    harness_violation_workers = (
        get_harness_violation_workers(
            analysis
        )
    )

    has_harness_violation = bool(
        harness_violation_workers
    )

    normalized_hazards = []

    # ========================================================
    # 2. VLM이 직접 생성한 hazard 정규화
    # ========================================================

    for hazard in analysis.get(
        "hazards",
        []
    ):

        risk_types = split_risk_types(
            hazard.get(
                "risk_type",
                "",
            )
        )

        detected = bool(
            hazard.get(
                "detected",
                False,
            )
        )

        confidence = hazard.get(
            "confidence",
            "LOW",
        )

        if confidence not in CONFIDENCE_RANK:
            confidence = "LOW"

        proximity = hazard.get(
            "proximity",
            "UNCERTAIN",
        )

        if proximity not in VALID_PROXIMITY:
            proximity = "UNCERTAIN"

        evidence = (
            hazard.get(
                "evidence",
                "",
            )
            or ""
        ).strip()

        for risk_type in risk_types:

            # ------------------------------------------------
            # 안전대 위험 안전장치
            #
            # VLM이 UNFASTENED_SAFETY_HARNESS=true라고
            # 직접 생성했더라도 실제 worker 정보에서
            #
            # ELEVATED
            # +
            # NOT_WEARING / WORN_NOT_CONNECTED
            #
            # 조합이 확인되지 않으면 위험을 확정하지 않는다.
            # ------------------------------------------------

            if (
                risk_type
                == "UNFASTENED_SAFETY_HARNESS"
                and detected
                and not has_harness_violation
            ):

                detected = False

                confidence = "LOW"

                proximity = "UNCERTAIN"

                evidence = (
                    "고소작업 중 안전대 미착용 또는 "
                    "미체결 상태가 명확하게 확인되지 않음"
                )

            normalized_hazards.append(
                {
                    "risk_type":
                        risk_type,

                    "detected":
                        detected,

                    "confidence":
                        confidence,

                    "proximity":
                        proximity,

                    "evidence":
                        evidence,
                }
            )

    # ========================================================
    # 3. Worker 정보 기반 위험 보완
    # ========================================================

    for worker in analysis.get(
        "workers",
        []
    ):

        worker_id = worker.get(
            "worker_id",
            "unknown",
        )

        helmet = worker.get(
            "helmet",
            "UNCERTAIN",
        )

        work_level = worker.get(
            "work_level",
            "UNCERTAIN",
        )

        harness = worker.get(
            "harness",
            "UNCERTAIN",
        )

        # ----------------------------------------------------
        # 안전모 미착용 보완
        # ----------------------------------------------------

        if helmet == "NOT_WEARING":

            normalized_hazards.append(
                {
                    "risk_type":
                        "NO_HELMET",

                    "detected":
                        True,

                    "confidence":
                        "HIGH",

                    "proximity":
                        "UNCERTAIN",

                    "evidence":
                        (
                            f"작업자 {worker_id}가 "
                            "안전모를 착용하지 않은 "
                            "것으로 분석됨"
                        ),
                }
            )

        # ----------------------------------------------------
        # 고소작업 안전대 위반
        #
        # 반드시 ELEVATED인 경우에만 생성한다.
        # ----------------------------------------------------

        if (
            work_level == "ELEVATED"
            and harness in {
                "NOT_WEARING",
                "WORN_NOT_CONNECTED",
            }
        ):

            if harness == "NOT_WEARING":

                evidence = (
                    f"작업자 {worker_id}가 "
                    "고소작업 중 안전대를 "
                    "착용하지 않은 것으로 분석됨"
                )

            else:

                evidence = (
                    f"작업자 {worker_id}가 "
                    "고소작업 중 안전대를 착용했으나 "
                    "안전고리를 부착설비에 "
                    "체결하지 않은 것으로 분석됨"
                )

            normalized_hazards.append(
                {
                    "risk_type":
                        "UNFASTENED_SAFETY_HARNESS",

                    "detected":
                        True,

                    "confidence":
                        "HIGH",

                    "proximity":
                        "IMMEDIATE",

                    "evidence":
                        evidence,
                }
            )

    # ========================================================
    # 4. 중복 Hazard 제거
    # ========================================================

    unique_hazards = []

    seen = set()

    for hazard in normalized_hazards:

        key = (
            hazard.get(
                "risk_type"
            ),
            hazard.get(
                "detected"
            ),
            hazard.get(
                "evidence"
            ),
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique_hazards.append(
            hazard
        )

    analysis[
        "hazards"
    ] = unique_hazards

    return analysis


# ============================================================
# RAG 검색 Query 생성
# ============================================================

def build_search_query(
    hazard: dict[str, Any],
) -> str:

    risk_type = hazard.get(
        "risk_type",
        "",
    )

    if risk_type not in VALID_RISK_TYPES:
        return ""

    evidence = hazard.get(
        "evidence",
        [],
    )

    # ========================================================
    # evidence 형식 통일
    # ========================================================

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

        evidence_list = evidence

    else:

        evidence_list = []

    evidence_text = " ".join(
        str(item).strip()
        for item in evidence_list[:3]
        if str(item).strip()
    )

    base_query = SEARCH_QUERY_MAP[
        risk_type
    ]

    # ========================================================
    # 안전대 위험 세부 Query 분기
    #
    # UNFASTENED_SAFETY_HARNESS를 FALL_HAZARD로 바꾸지 않는다.
    # 실제 evidence를 보고
    #
    # 1. 안전고리 미체결
    # 2. 안전대 미착용
    #
    # 을 구분해 RAG 검색문을 더 구체적으로 만든다.
    # ========================================================

    if (
        risk_type
        == "UNFASTENED_SAFETY_HARNESS"
    ):

        evidence_lower = (
            evidence_text.lower()
        )

        anchor_keywords = [
            "안전고리",
            "부착설비",
            "체결하지",
            "체결되지",
            "미체결",
        ]

        not_wearing_keywords = [
            "안전대 미착용",
            "안전대를 착용하지",
            "안전대 착용하지",
        ]

        if any(
            keyword in evidence_lower
            for keyword in anchor_keywords
        ):

            base_query = (
                "고소작업 중 근로자가 안전대를 착용하고 있으나 "
                "안전고리를 부착설비에 체결하지 않은 상황. "
                "안전대의 부착설비, 안전고리 체결, "
                "안전대 부속설비 점검 및 추락 방지 관련 안전기준"
            )

        elif any(
            keyword in evidence_lower
            for keyword in not_wearing_keywords
        ):

            base_query = (
                "고소작업 중 근로자가 안전대를 착용하지 않은 상황. "
                "안전대 착용, 보호구의 지급, "
                "높이 2미터 이상 추락 위험 작업 및 추락 방지 관련 안전기준"
            )

    # ========================================================
    # Risk Type Marker
    #
    # 모든 위험 유형을 그대로 regulation_retriever에 전달한다.
    # ========================================================

    marker = (
        f"[RISK_TYPE={risk_type}]"
    )

    # ========================================================
    # 최종 Query
    # ========================================================

    if evidence_text:

        return (
            f"{marker} "
            f"{base_query}. "
            f"현장 관찰 근거: "
            f"{evidence_text}"
        )

    return (
        f"{marker} "
        f"{base_query}"
    )
