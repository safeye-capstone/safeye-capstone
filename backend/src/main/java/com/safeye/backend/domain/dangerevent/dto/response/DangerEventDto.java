package com.safeye.backend.domain.dangerevent.dto.response;

import com.safeye.backend.domain.dangerevent.entity.DangerEvent;
import com.safeye.backend.domain.dangerevent.entity.Severity;
import com.safeye.backend.domain.dangerevent.entity.VlmDecisionState;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record DangerEventDto(
    UUID id,
    boolean isDanger,
    VlmDecisionState decisionState,
    String zoneName,
    Severity severity,
    String fileUrl,

    String vlmDescription,
    String violatedRegulation,
    String actionGuide,
    Map<String, Object> ragMetadata,

    boolean isResolved,
    Instant detectedAt,
    Instant resolvedAt
) {

  public static DangerEventDto from(DangerEvent event) {

    boolean calculatedIsDanger = (event.getSeverity() != null && event.getSeverity() != Severity.INFO);

    return new DangerEventDto(
        event.getId(),
        calculatedIsDanger,
        VlmDecisionState.from(event.getRagMetadata()),
        event.getWorkZone().getZoneName(),
        event.getSeverity(),
        event.getFileUrl(),
        event.getVlmDescription(),
        event.getViolatedRegulation(),
        event.getActionGuide(),
        event.getRagMetadata(),
        event.isResolved(),
        event.getCreatedAt(),
        event.getResolvedAt()
    );
  }
}
