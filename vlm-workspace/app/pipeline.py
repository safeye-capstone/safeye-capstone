import json
import logging
import time
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from app.local.config import FRAME_DIR, FRAME_INTERVAL_SEC, VIDEO_DIR
from app.local.ollama_client import analyze_image
from app.local.video_processor import extract_frames
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
logger = logging.getLogger(__name__)
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
        parsed = json.loads(raw_response)
        if not isinstance(parsed, dict):
            raise ValueError("VLM 응답은 JSON 객체여야 합니다.")
        return parsed
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
    logger.info(
        "프레임 분석 완료 - frame=%s, workers=%s, detected_hazards=%s",
        frame_name,
        len(workers),
        len(detected_hazards),
    )
    for hazard in detected_hazards:
        logger.debug(
            "프레임 위험 - frame=%s, risk_type=%s, confidence=%s, evidence=%r",
            frame_name,
            hazard.get("risk_type", "UNKNOWN"),
            hazard.get("confidence", "LOW"),
            hazard.get("evidence", ""),
        )
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
        query = ""
        rag_error = None
        logger.info(
            "RAG 검색 시작 - risk_type=%s, query=%s",
            risk_type,
            query,
        )
        try:
            query = build_search_query(hazard)
            regulations = search_regulations(
                query=query,
                final_top_k=5,
                per_collection_k=3,
            )
        except Exception as error:
            rag_error = type(error).__name__
            logger.exception(
                "RAG 검색 실패 - risk_type=%s, query=%s",
                risk_type,
                query,
            )
            regulations = []
        logger.info(
            "RAG 검색 완료 - risk_type=%s, regulations=%s",
            risk_type,
            len(regulations),
        )
        results.append(
            {
                **hazard,
                "search_query": query,
                "regulations": regulations,
                "rag_status": "failed" if rag_error else "completed",
                "rag_error": rag_error,
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
    output_path = RESULT_DIR / f"{video_name}_{uuid4().hex}_analysis.json"
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
def analyze_video(video_name: str, *, verbose: bool = False) -> dict:
    started = time.perf_counter()
    video_path = VIDEO_DIR / video_name
    if not video_path.is_file():
        raise FileNotFoundError(
            f"영상 파일을 찾을 수 없습니다: {video_path}"
        )
    logger.info(
        "영상 분석 시작 - video=%s",
        video_path,
    )
    # ========================================================
    # 1. 요청별 프레임 폴더 생성
    # ========================================================
    # 요청 폴더는 재검증 및 디버깅을 위해 보존한다. 다른 요청의 파일은 지우지 않는다.
    request_id = uuid4().hex
    frame_dir = FRAME_DIR / request_id
    frame_dir.mkdir(parents=True, exist_ok=False)
    logger.info("요청 프레임 폴더 - request_id=%s path=%s", request_id, frame_dir)
    extraction_started = time.perf_counter()
    # ========================================================
    # 2. 영상에서 프레임 추출
    # ========================================================
    frames = extract_frames(
        video_path=video_path,
        output_dir=frame_dir,
        interval_sec=FRAME_INTERVAL_SEC,
    )
    logger.info(
        "프레임 추출 완료 - total_frames=%s",
        len(frames),
    )
    if not frames:
        raise RuntimeError(
            "영상에서 프레임을 추출하지 못했습니다."
        )
    extraction_seconds = time.perf_counter() - extraction_started
    inference_started = time.perf_counter()
    # ========================================================
    # 3. 프레임별 VLM 분석
    # ========================================================
    frame_results = []
    aggregation_timeline = []
    failed_frame_names = []
    for index, frame_path in enumerate(frames, start=1):
        logger.info(
            "프레임 분석 시작 - index=%s/%s, frame=%s",
            index,
            len(frames),
            frame_path.name,
        )
        try:
            analysis = analyze_frame(frame_path)
            print_frame_summary(analysis)
        except Exception as error:
            failed_frame_names.append(frame_path.name)
            aggregation_timeline.append(
                {"frame": frame_path.name, "error": type(error).__name__}
            )
            logger.exception(
                "프레임 분석 실패 - frame=%s",
                frame_path.name,
            )
        else:
            frame_results.append(analysis)
            aggregation_timeline.append(analysis)
    if not frame_results:
        raise RuntimeError(
            "정상적으로 분석된 프레임이 없습니다."
        )
    inference_seconds = time.perf_counter() - inference_started
    decision_started = time.perf_counter()
    # ========================================================
    # 4. Aggregator
    #
    # 동일 위험을 여러 프레임에서 통합하고
    # Temporal consistency를 계산한다.
    # ========================================================
    aggregated_hazards = aggregate_frame_results(
        aggregation_timeline,
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
        deepcopy(aggregated_hazards)
    )
    # ========================================================
    # 6. Semantic Prompt Ensemble 재검증
    #
    # needs_reverification=True인 위험만
    # 추가 VLM 재검증을 수행한다.
    # ========================================================
    reverified_hazards = apply_reverification(
        aggregated_hazards=deepcopy(calibrated_hazards),
        frame_results=deepcopy(frame_results),
        frame_dir=frame_dir,
    )
    # 재검증까지 끝난 결과 확인
    if verbose:
        print_aggregated_summary(reverified_hazards)
    # ========================================================
    # 7. Final Decision
    #
    # CONFIRMED
    # REVIEW_REQUIRED
    # REJECTED
    # ========================================================
    decided_hazards = apply_final_decisions(deepcopy(reverified_hazards))
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
        deepcopy(decided_hazards)
    )
    # ========================================================
    # 실제 사용자 경고 및 RAG 대상
    # ========================================================
    actionable_hazards = get_primary_actionable_hazards(
        deepcopy(consolidated_hazards)
    )
    logger.info(
        "Final Decision 완료 - candidates=%s, actionable=%s",
        len(decided_hazards),
        len(actionable_hazards),
    )
    # ========================================================
    # 9. RAG 법령 검색
    #
    # REJECTED 위험에는 RAG를 실행하지 않는다.
    # ========================================================
    decision_seconds = time.perf_counter() - decision_started
    rag_started = time.perf_counter()
    hazards_with_regulations = attach_regulations(
        actionable_hazards
    )
    # ========================================================
    # 10. 최종 결과
    # ========================================================
    result = {
        "request_id": request_id,
        "frame_dir": str(frame_dir),
        "timings_seconds": {
            "extraction": round(extraction_seconds, 3),
            "frame_analysis": round(inference_seconds, 3),
            "decision_and_reverification": round(decision_seconds, 3),
            "rag": round(time.perf_counter() - rag_started, 3),
            "total": round(time.perf_counter() - started, 3),
        },
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    result = analyze_video("test.mp4", verbose=True)
    output_path = save_result(result)
    print_final_summary(result)
    print()
    print(f"전체 JSON 저장 위치: {output_path}")
