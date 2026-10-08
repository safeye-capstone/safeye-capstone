package com.safeye.backend.domain.dangerevent.entity;

import java.util.Locale;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;

/*
 * 판정              | is_danger | severity              | 발생 경로
 *
 * CONFIRMED        | true      | CRITICAL 또는 WARNING  | 이미지·영상
 * REVIEW_REQUIRED  | false     | WARNING               | 이미지·영상
 * REJECTED         | false     | INFO                  | 영상만
 * NO_DETECTION     | false     | INFO                  | 이미지·영상
*/

@Slf4j
public enum VlmDecisionState {

  CONFIRMED,       // 확정 위험
  REVIEW_REQUIRED, // 검토 대기 (사람 확인 필요)
  REJECTED,        // AI가 오탐으로 기각
  NO_DETECTION,    // 위험 후보 없음
  UNKNOWN;         // ragMetadata 없음(과거 데이터) 또는 값 누락, 정의되지 않은 값

  public static final String METADATA_KEY = "vlm_decision_state";

  public static VlmDecisionState from(Map<String, Object> ragMetadata) {
    if (ragMetadata == null) {
      return UNKNOWN;
    }

    Object state = ragMetadata.get(METADATA_KEY);
    return (state instanceof String value && !value.isBlank()) ? fromValue(value) : UNKNOWN;
  }

  public static VlmDecisionState fromValue(String value) {
    if (value == null || value.isBlank()) {
      return UNKNOWN;
    }
    try {
      return valueOf(value.trim().toUpperCase(Locale.ROOT));
    } catch (IllegalArgumentException e) {
      log.warn("정의되지 않은 VLM 판정 값 - value: {}", value);
      return UNKNOWN;
    }
  }

  // 사람이 확인해야 하는 판정인지 검사 (확정 위험 또는 검토 대기)
  public boolean needsAttention() {
    return this == CONFIRMED || this == REVIEW_REQUIRED;
  }
}
