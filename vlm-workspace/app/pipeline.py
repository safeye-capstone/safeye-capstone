import json
from pathlib import Path

from app.local.config import FRAME_DIR, FRAME_INTERVAL_SEC, VIDEO_DIR
from app.local.ollama_client import analyze_image
from app.local.video_processor import clear_frames, extract_frames
from app.rag.aggregator import aggregate_frame_results
from app.rag.confidence_calibrator import apply_confidence_recalibration
from app.rag.reverification import apply_reverification
from app.rag.final_decision import apply_final_decisions
from app.rag.hazard_consolidator import (
    consolidate_related_hazards,
    get_primary_actionable_hazards,
)
from app.rag.query_builder import build_search_query, normalize_vlm_analysis
from app.rag.regulation_retriever import search_regulations


# ============================================================
# 결과 저장 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_DIR = BASE_DIR / "data" / "results"


# ============================================================
# VLM JSON 파싱
# ============================================================

def parse_vlm_json(raw_response: str) -> dict:
    """
    Ollama가 반환한 JSON 문자열을
    Python dict로 변환한다.
    """

    raw_response = raw_response.strip()

    # ```json ... ``` 형태 대응
    if raw_response.startswith("```"):
        lines = raw_response.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        raw_response = "\n".join(lines).strip()

    try:
        return json.loads(raw_response)

    except json.JSONDecodeError as error:
        raise ValueError(
            "VLM 응답이 올바른 JSON 형식이 아닙니다.\n"
            f"{raw_response}"
        ) from error


# ============================================================
# 프레임 한 장 분석
# ============================================================

def analyze_frame(frame_path: Path) -> dict:
    """
    프레임 한 장을 VLM으로 분석하고
    논리 정규화를 수행한다.
    """

    raw_response = analyze_image(frame_path)
    analysis = parse_vlm_json(raw_response)
    analysis = normalize_vlm_analysis(analysis)
    analysis["frame"] = frame_path.name

    return analysis


# ============================================================
# 프레임 분석 결과 출력
# ============================================================

def print_frame_summary(analysis: dict) -> None:
    frame_name = analysis.get("frame", "unknown")
    workers = analysis.get("workers", [])
    hazards = analysis.get("hazards", [])

    detected_hazards = [
        hazard
        for hazard in hazards
        if hazard.get("detected", False)
    ]

    print(f"[분석 완료] {frame_name}")
    print(f"  작업자 수: {len(workers)}")

    if not detected_hazards:
        print("  탐지 위험: 없음")
        return

    print("  탐지 위험:")

    for hazard in detected_hazards:
        risk_type = hazard.get("risk_type", "UNKNOWN")
        confidence = hazard.get("confidence", "LOW")
        evidence = hazard.get("evidence", "")

        print(f"    - {risk_type} ({confidence})")

        if evidence:
            print(f"      근거: {evidence}")


# ============================================================
# 위험에 RAG 결과 연결
# ============================================================

def attach_regulations(hazards: list[dict]) -> list[dict]:
    """
    Final Decision 이후
    실제 경고 대상으로 남은 위험에 대해서만
    RAG 검색을 수행한다.
    """

    results = []

    for hazard in hazards:
        if not hazard.get("detected", False):
            continue

        # 혹시 REJECTED가 들어오더라도
        # RAG 검색하지 않도록 추가 방어
        if hazard.get("final_decision") == "REJECTED":
            continue

        risk_type = hazard.get("risk_type", "UNKNOWN")
        query = build_search_query(hazard)

        print()
        print(f"[RAG 검색] {risk_type}")
        print(f"  검색문: {query}")

        try:
            regulations = search_regulations(
                query=query,
                final_top_k=5,
                per_collection_k=3,
            )

        except Exception as error:
            print(f"  RAG 검색 실패: {error}")
            regulations = []

        print(f"  검색된 법령: {len(regulations)}개")

        results.append(
            {
                **hazard,
                "search_query": query,
                "regulations": regulations,
            }
        )

    return results


# ============================================================
# 법령명 추출
# ============================================================

def get_regulation_name(regulation: dict) -> str:
    metadata = regulation.get("metadata", {})

    return (
        metadata.get("law_name")
        or metadata.get("document_name")
        or metadata.get("document_title")
        or regulation.get("collection")
        or "법령명 없음"
    )


# ============================================================
# 법령 조항 추출
# ============================================================

def get_article(regulation: dict) -> str:
    metadata = regulation.get("metadata", {})

    article = (
        metadata.get("article")
        or metadata.get("article_number")
        or ""
    )

    article_title = (
        metadata.get("article_title")
        or metadata.get("title")
        or ""
    )

    if article and article_title:
        return f"{article} {article_title}"

    if article:
        return article

    if article_title:
        return article_title

    return "조항 정보 없음"


# ============================================================
# Final Decision 결과 출력
# ============================================================

def print_decision_summary(decided_hazards: list[dict]) -> None:
    print()
    print("=" * 60)
    print("최종 위험 판단")
    print("=" * 60)

    if not decided_hazards:
        print("판단할 위험이 없습니다.")
        return

    for index, hazard in enumerate(decided_hazards, start=1):
        risk_type = hazard.get("risk_type", "UNKNOWN")
        decision = hazard.get("final_decision", "UNKNOWN")
        reason = hazard.get("final_decision_reason", "")
        final_label = hazard.get(
            "final_reliability_label",
            hazard.get("reliability_label", "UNKNOWN"),
        )
        final_score = hazard.get(
            "final_consistency_score",
            hazard.get("consistency_score", 0.0),
        )

        print()
        print(f"[판단 {index}]")
        print(f"위험 유형: {risk_type}")
        print(f"Final Decision: {decision}")
        print(f"최종 신뢰도: {final_label}")
        print(f"최종 일관성 점수: {final_score:.3f}")

        if reason:
            print(f"판단 사유: {reason}")


# ============================================================
# 통합 위험 결과 출력
# ============================================================

def print_aggregated_summary(hazards: list[dict]) -> None:
    print()
    print("=" * 60)
    print("프레임 통합 위험 분석")
    print("=" * 60)

    detected_hazards = [
        hazard
        for hazard in hazards
        if hazard.get("detected", False)
    ]

    if not detected_hazards:
        print("최종적으로 확인된 위험이 없습니다.")
        return

    for index, hazard in enumerate(detected_hazards, start=1):
        print()
        print(f"[위험 {index}]")
        print(f"유형: {hazard.get('risk_type')}")
        print(f"Aggregator 신뢰도: {hazard.get('confidence')}")
        print(
            f"Temporal support: "
            f"{hazard.get('temporal_support', 0):.3f}"
        )
        print(
            f"최대 연속 탐지: "
            f"{hazard.get('max_consecutive_detection_count', 0)}프레임"
        )
        print(
            f"1차 consistency score: "
            f"{hazard.get('consistency_score', 0):.3f}"
        )
        print(
            f"1차 reliability: "
            f"{hazard.get('reliability_label', 'UNKNOWN')}"
        )

        # ----------------------------------------------------
        # Prompt 재검증
        # ----------------------------------------------------

        reverification_applied = hazard.get(
            "reverification_applied",
            False,
        )

        print(
            f"Prompt 재검증 실행: "
            f"{'YES' if reverification_applied else 'NO'}"
        )

        if reverification_applied:
            print(
                f"재검증 프레임: "
                f"{hazard.get('reverification_frame', 'unknown')}"
            )

            prompt_support = hazard.get("prompt_agreement")

            print(f"Prompt 위험 지지율: {prompt_support}")
            print(
                f"재검증 Positive votes: "
                f"{hazard.get('reverification_positive_votes', 0)}"
            )
            print(
                f"재검증 Negative votes: "
                f"{hazard.get('reverification_negative_votes', 0)}"
            )

        # ----------------------------------------------------
        # 최종 신뢰도
        # ----------------------------------------------------

        final_score = hazard.get(
            "final_consistency_score",
            hazard.get("consistency_score", 0.0),
        )

        final_label = hazard.get(
            "final_reliability_label",
            hazard.get("reliability_label", "UNKNOWN"),
        )

        print(f"최종 consistency score: {final_score:.3f}")
        print(f"최종 reliability: {final_label}")
        print(f"검출 프레임 수: {hazard.get('detection_count', 0)}")

        evidence_frames = hazard.get("evidence_frames", [])

        if evidence_frames:
            print("검출 프레임: " + ", ".join(evidence_frames))


# ============================================================
# 최종 결과 출력
# ============================================================

def print_final_summary(result: dict) -> None:
    print()
    print("=" * 60)
    print("최종 분석 결과")
    print("=" * 60)

    print(f"영상: {result.get('video')}")
    print(f"전체 프레임: {result.get('total_frames')}")
    print(f"분석 성공: {result.get('analyzed_frames')}")
    print(f"분석 실패: {result.get('failed_frames')}")

    hazards = result.get("hazards", [])

    if not hazards:
        print()
        print("최종 경고 대상으로 확정된 위험이 없습니다.")
        return

    for index, hazard in enumerate(hazards, start=1):
        print()
        print("-" * 60)
        print(f"[위험 {index}]")
        print(f"위험 유형: {hazard.get('risk_type')}")

        # ----------------------------------------------------
        # Final Decision
        # ----------------------------------------------------

        final_decision = hazard.get("final_decision", "UNKNOWN")
        print(f"최종 판단: {final_decision}")

        decision_reason = hazard.get("final_decision_reason", "")

        if decision_reason:
            print(f"판단 사유: {decision_reason}")

        # ----------------------------------------------------
        # 신뢰도
        # ----------------------------------------------------

        final_label = hazard.get(
            "final_reliability_label",
            hazard.get("reliability_label", "UNKNOWN"),
        )

        final_score = hazard.get(
            "final_consistency_score",
            hazard.get("consistency_score", 0.0),
        )

        print(f"최종 신뢰도 등급: {final_label}")
        print(f"최종 일관성 점수: {final_score:.3f}")
        print(
            f"Prompt 재검증: "
            f"{'YES' if hazard.get('reverification_applied', False) else 'NO'}"
        )
        print(f"검출 프레임 수: {hazard.get('detection_count', 0)}")

        # ----------------------------------------------------
        # 판단 근거
        # ----------------------------------------------------

        evidence = hazard.get("evidence", [])

        if evidence:
            print("판단 근거:")

            for item in evidence[:3]:
                print(f"  - {item}")

        # ----------------------------------------------------
        # 관련 법령
        # ----------------------------------------------------

        regulations = hazard.get("regulations", [])

        print()
        print(f"관련 법령 (상위 {min(3, len(regulations))}개):")

        for law_index, regulation in enumerate(regulations[:3], start=1):
            law_name = get_regulation_name(regulation)
            article = get_article(regulation)
            distance = regulation.get("distance")

            print(f"  {law_index}. {law_name}")
            print(f"     {article}")

            if distance is not None:
                print(f"     distance: {distance:.4f}")


# ============================================================
# 결과 JSON 저장
# ============================================================

def save_result(result: dict) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    video_name = Path(result.get("video", "analysis")).stem
    output_path = RESULT_DIR / f"{video_name}_analysis.json"

    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path


# ============================================================
# 전체 영상 분석 Pipeline
# ============================================================

def analyze_video(video_name: str) -> dict:
    video_path = VIDEO_DIR / video_name

    if not video_path.exists():
        raise FileNotFoundError(
            f"영상 파일을 찾을 수 없습니다: {video_path}"
        )

    print()
    print("=" * 60)
    print("영상 분석 시작")
    print("=" * 60)
    print(f"영상: {video_path}")

    # ========================================================
    # 1. 기존 프레임 제거
    # ========================================================

    clear_frames(FRAME_DIR)

    # ========================================================
    # 2. 영상에서 프레임 추출
    # ========================================================

    frames = extract_frames(
        video_path=video_path,
        output_dir=FRAME_DIR,
        interval_sec=FRAME_INTERVAL_SEC,
    )

    print()
    print(f"총 {len(frames)}개 프레임 추출 완료")

    if not frames:
        raise RuntimeError(
            "영상에서 프레임을 추출하지 못했습니다."
        )

    # ========================================================
    # 3. 프레임별 VLM 분석
    # ========================================================

    frame_results = []
    failed_frame_names = []

    for index, frame_path in enumerate(frames, start=1):
        print()
        print(
            f"[{index}/{len(frames)}] "
            f"{frame_path.name} 분석 중..."
        )

        try:
            analysis = analyze_frame(frame_path)
            frame_results.append(analysis)
            print_frame_summary(analysis)

        except Exception as error:
            failed_frame_names.append(frame_path.name)
            print(f"[프레임 분석 실패] {frame_path.name}")
            print(f"오류: {error}")

    if not frame_results:
        raise RuntimeError(
            "정상적으로 분석된 프레임이 없습니다."
        )

    # ========================================================
    # 4. Aggregator
    #
    # 동일 위험을 여러 프레임에서 통합하고
    # Temporal consistency를 계산한다.
    # ========================================================

    aggregated_hazards = aggregate_frame_results(
        frame_results,
        min_detection_count=2,
        temporal_window_size=3,
    )

    # ========================================================
    # 5. Confidence Calibrator
    #
    # Temporal support
    # Model confidence
    # Consecutive support
    #
    # 를 이용해 1차 consistency score를 계산한다.
    # ========================================================

    calibrated_hazards = apply_confidence_recalibration(
        aggregated_hazards
    )

    # ========================================================
    # 6. Semantic Prompt Ensemble 재검증
    #
    # needs_reverification=True인 위험만
    # 추가 VLM 재검증을 수행한다.
    # ========================================================

    reverified_hazards = apply_reverification(
        aggregated_hazards=calibrated_hazards,
        frame_results=frame_results,
        frame_dir=FRAME_DIR,
    )

    # 재검증까지 끝난 결과 확인
    print_aggregated_summary(reverified_hazards)

    # ========================================================
    # 7. Final Decision
    #
    # CONFIRMED
    # REVIEW_REQUIRED
    # REJECTED
    # ========================================================

    decided_hazards = apply_final_decisions(reverified_hazards)

    # ========================================================
    # 8. Hazard Relation / 중복 위험 통합
    #
    # 예:
    #
    # 안전고리 미체결
    # →
    # UNFASTENED_SAFETY_HARNESS
    # +
    # FALL_HAZARD
    #
    # 두 개가 같은 근거에서 나온 경우
    # 안전대 위험을 Primary로 사용한다.
    # ========================================================

    consolidated_hazards = consolidate_related_hazards(
        decided_hazards
    )

    # ========================================================
    # 실제 사용자 경고 및 RAG 대상
    # ========================================================

    actionable_hazards = get_primary_actionable_hazards(
        consolidated_hazards
    )

    print()
    print(
        "[Final Decision] "
        f"전체 후보 {len(decided_hazards)}개 → "
        f"최종 경고 대상 {len(actionable_hazards)}개"
    )

    # ========================================================
    # 9. RAG 법령 검색
    #
    # REJECTED 위험에는 RAG를 실행하지 않는다.
    # ========================================================

    hazards_with_regulations = attach_regulations(
        actionable_hazards
    )

    # ========================================================
    # 10. 최종 결과
    # ========================================================

    result = {
        "video": video_name,
        "total_frames": len(frames),
        "analyzed_frames": len(frame_results),
        "failed_frames": len(failed_frame_names),
        "failed_frame_names": failed_frame_names,

        # ----------------------------------------------------
        # 프레임별 VLM 원본 분석
        # ----------------------------------------------------
        "frames": frame_results,

        # ----------------------------------------------------
        # Aggregator 결과
        # ----------------------------------------------------
        "aggregated_hazards": aggregated_hazards,

        # ----------------------------------------------------
        # Confidence Calibrator 결과
        # ----------------------------------------------------
        "calibrated_hazards": calibrated_hazards,

        # ----------------------------------------------------
        # Prompt Ensemble 재검증 결과
        # ----------------------------------------------------
        "reverified_hazards": reverified_hazards,

        # ----------------------------------------------------
        # Final Decision 전체 기록
        #
        # REJECTED도 여기에 남아 있다.
        # ----------------------------------------------------
        "decided_hazards": decided_hazards,

        # 위험 관계 정리 결과
        "consolidated_hazards": consolidated_hazards,

        # ----------------------------------------------------
        # 실제 경고 대상
        #
        # REJECTED 제외
        # ----------------------------------------------------
        "actionable_hazards": actionable_hazards,

        # ----------------------------------------------------
        # RAG까지 완료된 최종 결과
        # ----------------------------------------------------
        "hazards": hazards_with_regulations,
    }

    return result


# ============================================================
# 직접 실행
# ============================================================

if __name__ == "__main__":
    result = analyze_video("test.mp4")
    output_path = save_result(result)

    print_final_summary(result)

    print()
    print(f"전체 JSON 저장 위치: {output_path}")
