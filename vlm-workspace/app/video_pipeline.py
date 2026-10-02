"""영상 분석 결과를 최종 판단 상태에 따라 백엔드 응답으로 변환한다."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from app.api_schemas import AIAnalysisResponse
from app.pipeline import analyze_video
from app.response_builder import build_action_guide, build_violated_regulation

RISK_LABELS = {
    "NO_HELMET": "안전모 미착용",
    "UNFASTENED_SAFETY_HARNESS": "안전대 또는 안전고리 미체결",
    "FALL_HAZARD": "추락 위험",
    "BLOCKED_PATH": "통행로 장애",
}
VALID_DECISIONS = {"CONFIRMED", "REVIEW_REQUIRED", "REJECTED"}
CRITICAL_RISK_TYPES = {"UNFASTENED_SAFETY_HARNESS", "FALL_HAZARD"}


def get_decision_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    """기각·보조 위험을 포함한 통합 판단 기록을 가져온다."""
    hazards = result.get("consolidated_hazards")
    if not isinstance(hazards, list):
        raise ValueError("영상 결과에 consolidated_hazards 목록이 필요합니다.")
    for hazard in hazards:
        if not isinstance(hazard, dict) or hazard.get("final_decision") not in VALID_DECISIONS:
            raise ValueError("영상 위험 후보의 final_decision이 없거나 올바르지 않습니다.")
    return hazards


def get_final_hazards(result: dict[str, Any]) -> list[dict[str, Any]]:
    """RAG 성공 여부와 별개로 확정·재검토 대표 위험을 반환한다."""
    return [
        hazard for hazard in get_decision_records(result)
        if hazard["final_decision"] != "REJECTED" and hazard.get("is_primary_hazard", True)
    ]


def get_video_decision_state(result: dict[str, Any]) -> str:
    """확정, 재검토, 전체 기각, 후보 미탐지를 구분한다."""
    records = get_decision_records(result)
    states = {hazard["final_decision"] for hazard in records}
    if "CONFIRMED" in states:
        return "CONFIRMED"
    if "REVIEW_REQUIRED" in states:
        return "REVIEW_REQUIRED"
    return "REJECTED" if records else "NO_DETECTION"


def calculate_video_severity(result: dict[str, Any]) -> str:
    """확정 위험의 유형을 우선하고, 재검토만 있으면 WARNING으로 반환한다."""
    records = get_decision_records(result)
    confirmed = [hazard for hazard in records if hazard["final_decision"] == "CONFIRMED"]
    if confirmed:
        risk_types = {hazard.get("risk_type") for hazard in confirmed}
        return "CRITICAL" if risk_types & CRITICAL_RISK_TYPES else "WARNING"
    if any(hazard["final_decision"] == "REVIEW_REQUIRED" for hazard in records):
        return "WARNING"
    return "INFO"


def _describe_hazard(hazard: dict[str, Any]) -> str:
    risk_type = hazard.get("risk_type", "UNKNOWN")
    label = RISK_LABELS.get(risk_type, risk_type)
    evidence = hazard.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(item).strip() for item in evidence if item is not None and str(item).strip()]
    return f"{label}: {evidence[0]}" if evidence else label


def build_video_description(result: dict[str, Any]) -> str:
    """확정 위험과 검토 대기를 별도로 설명한다."""
    hazards = get_final_hazards(result)
    confirmed = [hazard for hazard in hazards if hazard["final_decision"] == "CONFIRMED"]
    review = [hazard for hazard in hazards if hazard["final_decision"] == "REVIEW_REQUIRED"]
    descriptions = []
    if confirmed:
        details = " / ".join(_describe_hazard(hazard) for hazard in confirmed[:3])
        descriptions.append(f"영상 분석에서 확정된 위험: {details}.")
    if review:
        details = " / ".join(_describe_hazard(hazard) for hazard in review[:3])
        descriptions.append(f"검토 대기 후보의 관찰 근거: {details}. 위험 확정 전 추가 확인이 필요합니다.")
    if not descriptions:
        if get_video_decision_state(result) == "REJECTED":
            descriptions.append("탐지된 위험 후보는 최종 판단에서 기각되었으며, 확정된 위험은 없습니다.")
        else:
            descriptions.append("정상 분석된 프레임에서 위험 후보가 탐지되지 않았습니다.")
    failed_frames = result.get("failed_frames", 0)
    if failed_frames:
        descriptions.append(f"분석에 실패한 {failed_frames}개 프레임은 판단 근거에 포함되지 않았습니다.")
    return " ".join(descriptions)


def collect_regulations(result: dict[str, Any]) -> list[dict[str, Any]]:
    """확정된 대표 위험의 법령만 위반 법령 응답용으로 수집한다."""
    confirmed_types = {
        hazard.get("risk_type") for hazard in get_final_hazards(result)
        if hazard["final_decision"] == "CONFIRMED"
    }
    collected = []
    seen = set()
    for hazard in result.get("hazards", []):
        if hazard.get("risk_type") not in confirmed_types:
            continue
        for regulation in hazard.get("regulations", []):
            metadata = regulation.get("metadata") or {}
            key = (
                regulation.get("collection"),
                metadata.get("law_name") or metadata.get("document_name") or metadata.get("document_title"),
                metadata.get("article") or metadata.get("article_number"),
                metadata.get("article_title") or metadata.get("title"),
                regulation.get("id"),
            )
            # 식별 정보가 전혀 없는 법령은 임의로 같은 항목으로 합치지 않는다.
            if any(value is not None for value in key):
                if key in seen:
                    continue
                seen.add(key)
            collected.append(regulation)
    return collected


def build_rag_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """위험별 점수와 판단·통합 기록, 재검토 대상의 RAG 결과를 보존한다."""
    rag_by_risk = {hazard.get("risk_type"): hazard for hazard in result.get("hazards", [])}
    records = []
    for hazard in get_decision_records(result):
        record = deepcopy(hazard)
        record["vlm_decision_state"] = hazard["final_decision"]
        score = hazard.get("final_consistency_score")
        record["final_consistency_score"] = score if score is not None else hazard.get("consistency_score")
        rag_result = rag_by_risk.get(hazard.get("risk_type"))
        if rag_result is not None:
            for field in ("search_query", "regulations", "rag_status", "rag_error"):
                if field in rag_result:
                    record[field] = deepcopy(rag_result[field])
        records.append(record)
    return {
        "vlm_decision_state": get_video_decision_state(result),
        "hazards": records,
        "request_id": result.get("request_id"),
        "total_frames": result.get("total_frames"),
        "analyzed_frames": result.get("analyzed_frames"),
        "failed_frames": result.get("failed_frames"),
    }


def build_video_action_guide(result: dict[str, Any], severity: str) -> str:
    hazards = get_final_hazards(result)
    confirmed = [hazard for hazard in hazards if hazard["final_decision"] == "CONFIRMED"]
    review = [hazard for hazard in hazards if hazard["final_decision"] == "REVIEW_REQUIRED"]
    guides = []
    if confirmed:
        guide = build_action_guide({"hazards": confirmed}, severity)
        if guide:
            guides.append(guide)
    if review:
        labels = ", ".join(RISK_LABELS.get(hazard.get("risk_type"), hazard.get("risk_type", "UNKNOWN")) for hazard in review)
        guides.append(f"검토 대기 항목({labels})은 담당자가 원본 영상과 현장 상황을 추가 확인해 주세요.")
    if guides:
        return "\n".join(guides)
    return "확정된 위험에 대한 조치 안내는 없습니다. 현장 점검을 지속해 주세요."


def analyze_video_for_api(video_path: str | Path) -> AIAnalysisResponse:
    """VIDEO_DIR 안의 영상을 분석해 기본 5개 필드와 ragMetadata를 반환한다."""
    video_path = Path(video_path)
    result = analyze_video(video_path.name)
    state = get_video_decision_state(result)
    severity = calculate_video_severity(result)
    regulations = collect_regulations(result)
    return AIAnalysisResponse(
        is_danger=state == "CONFIRMED",
        severity=severity,
        vlm_description=build_video_description(result),
        violated_regulation=build_violated_regulation(regulations) if regulations else "",
        action_guide=build_video_action_guide(result, severity),
        ragMetadata=build_rag_metadata(result),
    )
