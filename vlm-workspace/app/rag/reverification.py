import json
import logging
from pathlib import Path
from typing import Any

from app.local.ollama_client import analyze_image, load_video_prompt
from app.rag.query_builder import normalize_vlm_analysis


logger = logging.getLogger(__name__)


# ============================================================
# 지원 위험 유형
# ============================================================

VALID_RISK_TYPES = {
    "NO_HELMET",
    "UNFASTENED_SAFETY_HARNESS",
    "FALL_HAZARD",
    "BLOCKED_PATH",
}


# ============================================================
# 기존 VLM confidence 비교용
# ============================================================

CONFIDENCE_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


# ============================================================
# 재검증용 Semantic Prompt
#
# 같은 의미를 서로 다른 방식으로 질문한다.
#
# 목적:
# 특정 프롬프트 문구에 따라 판단이 바뀌는
# prompt sensitivity를 확인한다.
# ============================================================

REVERIFICATION_PROMPTS = {
    "NO_HELMET": [
        """
이번 재검증에서는 안전모 착용 여부만 집중적으로 확인하세요.

이미지에서 실제로 관찰 가능한 시각적 근거만 사용하세요.

작업자의 머리 부분을 확인하고,
안전모를 착용하지 않았다고 명확하게 판단할 수 있는지
다시 평가하세요.

머리 부분이 가려져 있거나 해상도가 부족한 경우에는
억지로 위험으로 판단하지 말고 불확실하게 판단하세요.
""",
        """
이 장면에서 근로자의 안전모 착용 상태를 재검토하세요.

안전모 미착용으로 판단하려면
작업자의 머리 부분에서 보호용 안전모가 없다는
충분한 시각적 근거가 있어야 합니다.

단순히 안전모가 잘 보이지 않는다는 이유만으로
미착용으로 판단하지 마세요.
""",
    ],
    "UNFASTENED_SAFETY_HARNESS": [
        """
이번 재검증에서는 고소작업자의 안전대 상태만 확인하세요.

다음 조건을 구분해서 판단하세요.

1. 작업자가 실제로 고소작업 중인지
2. 안전대를 착용하고 있는지
3. 안전고리가 부착설비에 체결되어 있는지

이미지에서 확인되지 않는 내용을 추측하지 마세요.
""",
        """
이 장면에서 추락방지용 안전대가 필요한 작업자가
안전대를 올바르게 사용하고 있는지 다시 평가하세요.

지상 작업자에게 안전대 미착용 위험을 적용하지 마세요.

고소작업이면서 안전대 미착용 또는 안전고리 미체결이
시각적으로 확인될 때만 위험으로 판단하세요.
""",
    ],
    "FALL_HAZARD": [
        """
이번 재검증에서는 실제 추락 위험이 존재하는지 집중적으로 확인하세요.

단순히 작업자가 높은 위치에 있다는 이유만으로
추락 위험을 확정하지 마세요.

개구부, 보호되지 않은 단부, 안전난간 미설치,
불안정한 작업발판, 추락방호조치 미설치 등
구체적인 시각적 근거가 있는지 확인하세요.
""",
        """
이 장면을 다시 확인하여 근로자가 실제로
추락할 가능성이 있는 위험한 작업환경인지 판단하세요.

추락 위험이라고 판단하려면
작업자와 추락 가능 지점 사이의 공간적 관계와
난간, 발판, 개구부 또는 안전대 등
추락방호 상태를 확인하세요.

시각적 근거가 부족하면 위험을 확정하지 마세요.
""",
    ],
    "BLOCKED_PATH": [
        """
이번 재검증에서는 작업자의 통행 경로가
실제로 방해받고 있는지 집중적으로 확인하세요.

자재나 장비가 있다는 이유만으로
통로 장애 위험으로 판단하지 마세요.

작업자가 이동해야 하는 통로 또는 출입구가
실제로 막혀 있거나 통행이 어렵다는
시각적 근거가 있는지 확인하세요.
""",
        """
이 장면의 작업 통로와 이동 경로를 다시 확인하세요.

자재, 장비 또는 장애물이
근로자의 정상적인 통행을 실질적으로 방해하고 있는 경우에만
BLOCKED_PATH 위험으로 판단하세요.

단순히 주변에 물체가 존재하는 경우에는
통로 장애로 판단하지 마세요.
""",
    ],
}


# ============================================================
# JSON Parsing
# ============================================================

def parse_vlm_json(raw_response: str) -> dict[str, Any]:
    """
    analyze_image()가 반환한 JSON 문자열을
    Python dict로 변환한다.
    """

    raw_response = raw_response.strip()

    # 혹시 Markdown fence가 붙은 경우 제거
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
            "재검증 VLM 응답이 올바른 JSON이 아닙니다."
        ) from error


# ============================================================
# 특정 위험 탐지 여부 확인
# ============================================================

def find_target_hazard(
    analysis: dict[str, Any],
    risk_type: str,
) -> dict[str, Any] | None:
    """
    VLM 결과에서 특정 risk_type이
    detected=True인지 확인한다.
    """

    for hazard in analysis.get("hazards", []):
        if (
            hazard.get("risk_type") == risk_type
            and hazard.get("detected", False)
        ):
            return hazard

    return None


# ============================================================
# 재검증에 사용할 대표 프레임 선택
#
# 기존에 해당 위험이 탐지된 프레임 중
# confidence가 가장 높은 프레임을 선택한다.
# ============================================================

def select_reverification_frame(
    hazard: dict[str, Any],
    frame_results: list[dict[str, Any]],
    frame_dir: Path,
) -> Path | None:
    risk_type = hazard.get("risk_type", "")
    evidence_frames = set(hazard.get("evidence_frames", []))

    best_frame_name = None
    best_confidence = -1

    for frame_result in frame_results:
        frame_name = frame_result.get("frame", "")

        # Aggregator에서 실제 위험 근거로 사용하지 않은
        # 프레임은 제외
        if frame_name not in evidence_frames:
            continue

        for frame_hazard in frame_result.get("hazards", []):
            if frame_hazard.get("risk_type") != risk_type:
                continue

            if not frame_hazard.get("detected", False):
                continue

            confidence = frame_hazard.get("confidence", "LOW")
            confidence_score = CONFIDENCE_RANK.get(confidence, 1)

            if confidence_score > best_confidence:
                best_confidence = confidence_score
                best_frame_name = frame_name

    if not best_frame_name:
        return None

    frame_path = frame_dir / best_frame_name

    if not frame_path.exists():
        return None

    return frame_path


# ============================================================
# 재검증 Prompt 생성
# ============================================================

def build_reverification_prompt(
    risk_type: str,
    additional_instruction: str,
) -> str:
    """
    기존 video_analysis prompt를 유지하면서
    위험별 재검증 지시만 추가한다.
    """

    base_prompt = load_video_prompt()

    return (
        base_prompt
        + "\n\n"
        + """
============================================================
[추가 재검증 단계]
============================================================

이번 응답은 기존 분석 결과를 그대로 반복하는 단계가 아닙니다.

이미지를 처음부터 다시 확인하고
아래 재검증 기준에 따라 독립적으로 판단하세요.

확인할 수 없는 내용을 추측하지 마세요.
시각적 근거가 부족한 경우 불확실성을 유지하세요.

재검증 대상 위험 유형:
"""
        + risk_type
        + "\n\n"
        + additional_instruction
    )


# ============================================================
# 단일 Prompt 재검증
# ============================================================

def run_single_reverification(
    image_path: Path,
    risk_type: str,
    instruction: str,
) -> dict[str, Any]:
    prompt = build_reverification_prompt(
        risk_type=risk_type,
        additional_instruction=instruction,
    )

    raw_response = analyze_image(
        image_path=image_path,
        prompt=prompt,
    )

    analysis = parse_vlm_json(raw_response)

    # 기존 query_builder의 논리 정규화를
    # 재검증 결과에도 동일하게 적용
    analysis = normalize_vlm_analysis(analysis)

    target_hazard = find_target_hazard(
        analysis,
        risk_type,
    )

    detected = target_hazard is not None
    evidence = ""
    confidence = "LOW"

    if target_hazard:
        evidence = target_hazard.get("evidence", "")
        confidence = target_hazard.get("confidence", "LOW")

    return {
        "detected": detected,
        "confidence": confidence,
        "evidence": evidence,
    }


# ============================================================
# Semantic Prompt Ensemble
#
# 동일 이미지에 대해
# 서로 다른 표현의 Prompt 2개를 사용한다.
# ============================================================

def run_prompt_ensemble(
    image_path: Path,
    risk_type: str,
) -> dict[str, Any]:
    prompts = REVERIFICATION_PROMPTS.get(risk_type, [])

    if not prompts:
        return {
            "successful_votes": 0,
            "positive_votes": 0,
            "negative_votes": 0,
            "prompt_agreement": None,
            "majority_detected": None,
            "details": [],
        }

    details = []
    positive_votes = 0
    successful_votes = 0

    for index, instruction in enumerate(prompts, start=1):
        logger.info(
            "재검증 시작 - risk_type=%s, prompt=%s/%s",
            risk_type,
            index,
            len(prompts),
        )

        try:
            result = run_single_reverification(
                image_path=image_path,
                risk_type=risk_type,
                instruction=instruction,
            )

            successful_votes += 1

            if result["detected"]:
                positive_votes += 1

            details.append(
                {
                    "prompt_index": index,
                    "status": "SUCCESS",
                    **result,
                }
            )

            logger.info(
                "재검증 결과 - risk_type=%s, prompt=%s/%s, detected=%s",
                risk_type,
                index,
                len(prompts),
                result["detected"],
            )

        except Exception as error:
            logger.warning(
                "재검증 실패 - risk_type=%s, prompt=%s/%s, error=%s",
                risk_type,
                index,
                len(prompts),
                error,
            )

            details.append(
                {
                    "prompt_index": index,
                    "status": "FAILED",
                    "error": str(error),
                }
            )

    # --------------------------------------------------------
    # 모든 재검증 실패
    # --------------------------------------------------------

    if successful_votes == 0:
        return {
            "successful_votes": 0,
            "positive_votes": 0,
            "negative_votes": 0,
            "prompt_agreement": None,
            "majority_detected": None,
            "details": details,
        }

    negative_votes = successful_votes - positive_votes
    prompt_agreement = positive_votes / successful_votes

    # 2개 Prompt 기준:
    #
    # 2/2 → True
    # 1/2 → 애매
    # 0/2 → False
    #
    # tie(1/2)를 위험 확정으로 처리하지 않는다.
    majority_detected = positive_votes > negative_votes

    return {
        "successful_votes": successful_votes,
        "positive_votes": positive_votes,
        "negative_votes": negative_votes,
        "prompt_agreement": round(prompt_agreement, 3),
        "majority_detected": majority_detected,
        "details": details,
    }


# ============================================================
# Reliability Label
# ============================================================

def score_to_label(score: float) -> str:
    if score >= 0.80:
        return "HIGH"

    if score >= 0.60:
        return "MEDIUM"

    return "LOW"


# ============================================================
# 재검증 결과 반영
#
# 기존 consistency score를 없애지 않고
# Prompt Ensemble 결과를 별도 feature로 추가한다.
#
# 기존 점수 70%
# Prompt agreement 30%
#
# 아직 실제 Ground Truth로 학습한 calibration이 아니므로
# heuristic score이다.
# ============================================================

def combine_reverification_score(
    original_score: float,
    prompt_agreement: float,
) -> float:
    score = (
        0.70 * original_score
        + 0.30 * prompt_agreement
    )

    score = max(0.0, min(1.0, score))

    return round(score, 3)


# ============================================================
# 전체 Aggregated Hazard 재검증
# ============================================================

def apply_reverification(
    aggregated_hazards: list[dict[str, Any]],
    frame_results: list[dict[str, Any]],
    frame_dir: Path,
) -> list[dict[str, Any]]:
    """
    confidence_calibrator에서
    needs_reverification=True로 판단된 위험만
    Semantic Prompt Ensemble을 실행한다.

    중요:
    재검증 결과가 부정적이라고 해서
    detected 값을 자동으로 False로 바꾸지 않는다.

    안전 시스템이므로 false negative를 줄이기 위해
    최종 판단 신뢰도만 조정한다.
    """

    results = []

    for hazard in aggregated_hazards:
        # ----------------------------------------------------
        # 애초에 최종 위험이 아닌 경우
        # ----------------------------------------------------

        if not hazard.get("detected", False):
            results.append(
                {
                    **hazard,
                    "reverification_applied": False,
                }
            )
            continue

        # ----------------------------------------------------
        # 이미 HIGH reliability라면
        # 추가 VLM 호출을 하지 않는다.
        # ----------------------------------------------------

        if not hazard.get("needs_reverification", False):
            results.append(
                {
                    **hazard,
                    "reverification_applied": False,
                    "final_consistency_score": hazard.get(
                        "consistency_score",
                        0.0,
                    ),
                    "final_reliability_label": hazard.get(
                        "reliability_label",
                        "LOW",
                    ),
                    "final_needs_reverification": False,
                }
            )
            continue

        risk_type = hazard.get("risk_type", "")

        if risk_type not in VALID_RISK_TYPES:
            results.append(
                {
                    **hazard,
                    "reverification_applied": False,
                }
            )
            continue

        # ----------------------------------------------------
        # 가장 적합한 대표 프레임 선택
        # ----------------------------------------------------

        frame_path = select_reverification_frame(
            hazard=hazard,
            frame_results=frame_results,
            frame_dir=frame_dir,
        )

        if frame_path is None:
            results.append(
                {
                    **hazard,
                    "reverification_applied": False,
                    "reverification_error": (
                        "재검증에 사용할 "
                        "대표 프레임을 찾지 못함"
                    ),
                    "final_consistency_score": hazard.get(
                        "consistency_score",
                        0.0,
                    ),
                    "final_reliability_label": hazard.get(
                        "reliability_label",
                        "LOW",
                    ),
                    "final_needs_reverification": True,
                }
            )
            continue

        logger.info(
            "위험 재검증 실행 - risk_type=%s, representative_frame=%s",
            risk_type,
            frame_path.name,
        )

        ensemble_result = run_prompt_ensemble(
            image_path=frame_path,
            risk_type=risk_type,
        )

        prompt_agreement = ensemble_result.get("prompt_agreement")
        original_score = float(
            hazard.get("consistency_score", 0.0)
        )

        # ----------------------------------------------------
        # 재검증 자체가 실패했다면 기존 점수 유지
        # ----------------------------------------------------

        if prompt_agreement is None:
            final_score = original_score
        else:
            final_score = combine_reverification_score(
                original_score=original_score,
                prompt_agreement=float(prompt_agreement),
            )

        final_label = score_to_label(final_score)
        final_needs_reverification = final_label != "HIGH"

        results.append(
            {
                **hazard,
                "reverification_applied": True,
                "reverification_frame": frame_path.name,
                "reverification_successful_votes": ensemble_result.get(
                    "successful_votes",
                    0,
                ),
                "reverification_positive_votes": ensemble_result.get(
                    "positive_votes",
                    0,
                ),
                "reverification_negative_votes": ensemble_result.get(
                    "negative_votes",
                    0,
                ),
                "prompt_agreement": prompt_agreement,
                "reverification_majority_detected": ensemble_result.get(
                    "majority_detected"
                ),
                "reverification_details": ensemble_result.get(
                    "details",
                    [],
                ),
                "final_consistency_score": final_score,
                "final_reliability_label": final_label,
                "final_needs_reverification": final_needs_reverification,
                "final_confidence_method": (
                    "heuristic_temporal_"
                    "prompt_ensemble_v1"
                ),
            }
        )

    return results
