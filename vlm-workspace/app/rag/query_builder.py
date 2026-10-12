from typing import Any


# 지원하는 위험 유형

VALID_RISK_TYPES = {
    "NO_HELMET",
    "UNFASTENED_SAFETY_HARNESS",
    "FALL_HAZARD",
    "BLOCKED_PATH",
}


# 위험 유형별 RAG 기본 검색문

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


# Confidence 값

CONFIDENCE_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


# Proximity 값

VALID_PROXIMITY = {
    "IMMEDIATE",
    "NEAR",
    "NOT_NEAR",
    "UNCERTAIN",
}


# Risk Type 문자열 정리

def split_risk_types(risk_type: str) -> list[str]:
    if not risk_type:
        return []

    values = risk_type.replace(",", "|").split("|")

    return [
        value.strip()
        for value in values
        if value.strip() in VALID_RISK_TYPES
    ]


# 작업자 상태 정규화

def _worker_state_description(worker: dict[str, Any]) -> list[str]:
    """보정된 상태를 설명한다. 모델의 자유 문장을 사실로 재사용하지 않는다."""
    descriptions = []
    for field, name in (("helmet", "안전모"), ("vest", "안전조끼")):
        state = worker.get(field, "UNCERTAIN")
        descriptions.append({
            "WEARING": f"{name} 착용으로 분석되었습니다.",
            "NOT_WEARING": f"{name} 미착용으로 분석되었습니다.",
        }.get(state, f"{name} 착용 여부를 판단할 수 없습니다."))
    descriptions.append({
        "GROUND": "발과 지지면의 관찰 정보에 따라 지상으로 분류되었습니다.",
        "ELEVATED": "발과 지지면의 관찰 정보에 따라 지면보다 높은 위치로 분류되었습니다.",
    }.get(worker.get("work_level"), "작업 위치가 지상인지 높은 위치인지 판단할 근거가 충분하지 않습니다."))
    descriptions.append({
        "CONNECTED": "안전대 착용 및 안전고리 연결로 분석되었습니다.",
        "WORN_NOT_CONNECTED": "안전대 착용 및 안전고리 미체결로 분석되었습니다.",
        "NOT_WEARING": "안전대 미착용으로 분석되었습니다.",
        "NOT_APPLICABLE": "현재 지상 작업 판정 규칙에서는 안전대 위험 판단 대상이 아닙니다.",
    }.get(worker.get("harness"), "안전대 위반 여부는 확정할 수 없습니다."))
    return descriptions


def normalize_workers(analysis: dict[str, Any]) -> None:
    """높이 관찰 근거가 부족하거나 상충하면 UNCERTAIN으로 보정한다.

    새 관찰 필드가 없는 이전 응답도 높이를 추정하지 않는다.
    모델이 관찰 필드 자체를 잘못 채운 경우까지 검증하는 기능은 아니다.
    원래 상태와 문장은 내부 worker 기록에만 보존한다.
    """
    workers = analysis.get("workers", [])
    rebuild_scene = False
    for worker in workers:
        observation = worker.get("height_observation")
        if not isinstance(observation, dict):
            observation = {}
        feet = observation.get("feet_visible", "UNCERTAIN")
        support = observation.get("support_visible", "UNCERTAIN")
        relation = observation.get("ground_relation", "UNCERTAIN")
        supported_level = {
            "AT_GROUND": "GROUND", "ABOVE_GROUND": "ELEVATED",
        }.get(relation, "UNCERTAIN")
        original_level = worker.get("work_level", "UNCERTAIN")
        # 근거가 명확해도 모델 결론과 상충하면 다른 확정 상태로 승격하지 않는다.
        level = original_level if (
            feet == "VISIBLE" and support == "VISIBLE"
            and original_level == supported_level
            and supported_level in {"GROUND", "ELEVATED"}
        ) else "UNCERTAIN"
        old_harness = worker.get("harness", "UNCERTAIN")
        harness = old_harness
        if level == "GROUND":
            harness = "NOT_APPLICABLE"
        elif level == "UNCERTAIN" or harness == "NOT_APPLICABLE":
            harness = "UNCERTAIN"

        # 불확실한 상태의 자유 설명에도 높이 단정이 남을 수 있어 재구성한다.
        rewrite = level == "UNCERTAIN" or level != original_level or harness != old_harness
        if rewrite:
            worker.setdefault("_original_observation", {
                key: worker.get(key) for key in (
                    "work_level", "harness", "position", "observations",
                )
            })
        worker["work_level"] = level
        worker["harness"] = harness
        if rewrite:
            worker["position"] = {
                "GROUND": "관찰 정보에 따른 지상 위치",
                "ELEVATED": "관찰 정보에 따른 높은 위치",
            }.get(level, "작업 높이를 판단할 수 없음")
            worker["observations"] = _worker_state_description(worker)
            rebuild_scene = True

    if rebuild_scene:
        analysis["scene_description"] = " ".join(
            f"작업자 {worker.get('worker_id', index)}: "
            + " ".join(_worker_state_description(worker))
            for index, worker in enumerate(workers, start=1)
        )


# 실제 안전대 위반 작업자 확인

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

    for worker in analysis.get("workers", []):
        work_level = worker.get("work_level", "UNCERTAIN")
        harness = worker.get("harness", "UNCERTAIN")

        if (
            work_level == "ELEVATED"
            and harness in {
                "NOT_WEARING",
                "WORN_NOT_CONNECTED",
            }
        ):
            result.append(worker)

    return result


# VLM 분석 결과 정규화

def normalize_helmet_hazards(analysis: dict[str, Any]) -> None:
    """안전모 위험과 설명은 작업자 상태에서 구성한다. 상충한 후보는 보류한다.

    detected=True는 모순 검토 후보도 포함한다. 확정 여부는 이미지 분류기가
    consistency_review_required를 검사한다. 영상 전체 판정 정책은 별도다.
    """
    workers = analysis.get("workers", [])
    not_wearing = [w for w in workers if w.get("helmet") == "NOT_WEARING"]
    all_wearing = bool(workers) and all(w.get("helmet") == "WEARING" for w in workers)
    normalized = []
    for hazard in analysis.get("hazards", []):
        for risk_type in split_risk_types(hazard.get("risk_type", "")):
            item = {**hazard, "risk_type": risk_type}
            if risk_type != "NO_HELMET":
                normalized.append(item)
                continue
            # 재정규화해도 원래 모순과 원본 기록을 잃지 않는다.
            if item.get("consistency_review_required"):
                normalized.append(item)
                continue
            expected_detected = bool(not_wearing)
            original_detected = item.get("detected") is True
            if original_detected != expected_detected:
                item["_original_hazard"] = dict(hazard)
                if original_detected:
                    reason = (
                        "작업자는 모두 안전모 착용으로 분석되었으나 미착용 위험 판정과 상충하여 추가 확인이 필요합니다."
                        if all_wearing else
                        "안전모 미착용이 확인된 작업자가 없으나 미착용 위험 후보가 있어 추가 확인이 필요합니다."
                    )
                else:
                    reason = "작업자 상태에는 안전모 미착용이 있으나 미착용 위험 미탐지 판정과 상충하여 추가 확인이 필요합니다."
                item.update(
                    detected=True, confidence="LOW", proximity="UNCERTAIN",
                    evidence=reason, consistency_review_required=True,
                    consistency_reason=reason,
                )
            else:
                # 위험 설명을 별도로 재판단하지 않고 상태에서 작성한다.
                if expected_detected:
                    ids = ", ".join(str(w.get("worker_id", "미상")) for w in not_wearing)
                    evidence = f"작업자 {ids}의 안전모 미착용으로 분석되었습니다."
                elif all_wearing:
                    evidence = "확인된 작업자 모두 안전모 착용으로 분석되었습니다."
                else:
                    evidence = "작업자 관찰에서 안전모 미착용은 확정되지 않았으며 불확실한 착용 상태는 추가 확인이 필요합니다."
                if evidence != item.get("evidence"):
                    item.setdefault("_original_hazard", dict(hazard))
                item["evidence"] = evidence
                if not expected_detected:
                    item["proximity"] = "UNCERTAIN"
            normalized.append(item)
    analysis["hazards"] = normalized


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

    # 1. Worker 상태 정규화

    normalize_workers(analysis)
    normalize_helmet_hazards(analysis)

    # 실제 고소작업 + 안전대 위반 작업자
    harness_violation_workers = get_harness_violation_workers(analysis)
    has_harness_violation = bool(harness_violation_workers)

    normalized_hazards = []

    # 2. VLM이 직접 생성한 hazard 정규화

    for hazard in analysis.get("hazards", []):
        risk_types = split_risk_types(
            hazard.get("risk_type", "")
        )

        detected = bool(hazard.get("detected", False))

        confidence = hazard.get("confidence", "LOW")
        if confidence not in CONFIDENCE_RANK:
            confidence = "LOW"

        proximity = hazard.get("proximity", "UNCERTAIN")
        if proximity not in VALID_PROXIMITY:
            proximity = "UNCERTAIN"

        evidence = (hazard.get("evidence", "") or "").strip()

        original_detected, original_confidence = detected, confidence
        original_proximity, original_evidence = proximity, evidence
        for risk_type in risk_types:
            detected, confidence = original_detected, original_confidence
            proximity, evidence = original_proximity, original_evidence
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

            if (
                risk_type == "UNFASTENED_SAFETY_HARNESS"
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
                    **hazard,
                    "risk_type": risk_type,
                    "detected": detected,
                    "confidence": confidence,
                    "proximity": proximity,
                    "evidence": evidence,
                }
            )

    # 3. Worker 정보 기반 위험 보완

    for worker in analysis.get("workers", []):
        worker_id = worker.get("worker_id", "unknown")
        helmet = worker.get("helmet", "UNCERTAIN")
        work_level = worker.get("work_level", "UNCERTAIN")
        harness = worker.get("harness", "UNCERTAIN")

        # 안전모 미착용 보완

        if helmet == "NOT_WEARING" and not any(
            h.get("risk_type") == "NO_HELMET" and h.get("detected")
            for h in normalized_hazards
        ):
            normalized_hazards.append(
                {
                    "risk_type": "NO_HELMET",
                    "detected": True,
                    "confidence": "HIGH",
                    "proximity": "UNCERTAIN",
                    "evidence": (
                        f"작업자 {worker_id}가 "
                        "안전모를 착용하지 않은 "
                        "것으로 분석됨"
                    ),
                }
            )

        # 고소작업 안전대 위반
        #
        # 반드시 ELEVATED인 경우에만 생성한다.

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
                    "risk_type": "UNFASTENED_SAFETY_HARNESS",
                    "detected": True,
                    "confidence": "HIGH",
                    "proximity": "IMMEDIATE",
                    "evidence": evidence,
                }
            )

    # 4. 중복 Hazard 제거

    unique_hazards = []
    seen = set()

    for hazard in normalized_hazards:
        key = (
            hazard.get("risk_type"),
            hazard.get("detected"),
            hazard.get("evidence"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_hazards.append(hazard)

    analysis["hazards"] = unique_hazards

    return analysis


# RAG 검색 Query 생성

def build_search_query(hazard: dict[str, Any]) -> str:
    risk_type = hazard.get("risk_type", "")

    if risk_type not in VALID_RISK_TYPES:
        return ""

    evidence = hazard.get("evidence", [])

    # evidence 형식 통일

    if isinstance(evidence, str):
        evidence_list = [evidence]
    elif isinstance(evidence, list):
        evidence_list = evidence
    else:
        evidence_list = []

    evidence_text = " ".join(
        str(item).strip()
        for item in evidence_list[:3]
        if str(item).strip()
    )

    base_query = SEARCH_QUERY_MAP[risk_type]

    # 안전대 위험 세부 Query 분기
    #
    # UNFASTENED_SAFETY_HARNESS를 FALL_HAZARD로 바꾸지 않는다.
    # 실제 evidence를 보고
    #
    # 1. 안전고리 미체결
    # 2. 안전대 미착용
    #
    # 을 구분해 RAG 검색문을 더 구체적으로 만든다.

    if risk_type == "UNFASTENED_SAFETY_HARNESS":
        evidence_lower = evidence_text.lower()

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

    # Risk Type Marker
    #
    # 모든 위험 유형을 그대로 regulation_retriever에 전달한다.

    marker = f"[RISK_TYPE={risk_type}]"

    # 최종 Query

    if evidence_text:
        return (
            f"{marker} "
            f"{base_query}. "
            f"현장 관찰 근거: "
            f"{evidence_text}"
        )

    return f"{marker} {base_query}"
