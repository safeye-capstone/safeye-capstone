package com.safeye.backend.domain.vlm.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.safeye.backend.domain.dangerevent.entity.Severity;
import com.safeye.backend.domain.dangerevent.entity.VlmDecisionState;
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
  
  // 반환값: CONFIRMED / REVIEW_REQUIRED / REJECTED / NO_DETECTION / UNKNOWN
  public VlmDecisionState decisionState() {
    return VlmDecisionState.from(ragMetadata);
  }
}
