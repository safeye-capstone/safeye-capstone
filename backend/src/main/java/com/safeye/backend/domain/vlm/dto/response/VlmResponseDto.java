package com.safeye.backend.domain.vlm.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.safeye.backend.domain.dangerevent.entity.Severity;
import java.util.Map;

public record VlmResponseDto(
    @JsonProperty("is_danger")
    boolean isDanger,

    Severity severity,

    @JsonProperty("vlm_description")
    String vlmDescription,

    @JsonProperty("violated_regulation")
    String violatedRegulation,

    @JsonProperty("action_guide")
    String actionGuide,

    Map<String, Object> ragMetadata
) {

  private static final String DECISION_STATE_KEY = "vlm_decision_state";

  private static final String UNKNOWN_DECISION_STATE = "UNKNOWN";

  // 반환값: CONFIRMED / REVIEW_REQUIRED / REJECTED / NO_DETECTION / UNKNOWN
  public String decisionState() {
    if (ragMetadata == null) {
      return UNKNOWN_DECISION_STATE;
    }
    Object state = ragMetadata.get(DECISION_STATE_KEY);
    return (state instanceof String value && !value.isBlank()) ? value : UNKNOWN_DECISION_STATE;
  }

}
