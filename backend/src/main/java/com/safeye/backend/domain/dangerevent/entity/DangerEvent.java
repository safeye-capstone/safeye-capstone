package com.safeye.backend.domain.dangerevent.entity;

import com.safeye.backend.domain.zone.entity.WorkZone;
import com.safeye.backend.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.Map;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "danger_events", indexes = @Index(name = "idx_danger_event_created_at", columnList = "created_at"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class DangerEvent extends BaseEntity {

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "zone_id", nullable = false)
  private WorkZone workZone;

  @Enumerated(EnumType.STRING)
  private Severity severity;

  @Column(nullable = false, length = 512) // 추후 S3 도입 염두
  private String fileUrl;

  @Column(nullable = false, columnDefinition = "TEXT")
  private String vlmDescription;

  @Column(columnDefinition = "TEXT")
  private String violatedRegulation;

  @Column(columnDefinition = "TEXT")
  private String actionGuide;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(columnDefinition = "jsonb")
  private Map<String, Object> ragMetadata;

  @Builder.Default
  @Column(nullable = false)
  private boolean isResolved = false;

  private Instant resolvedAt;

  @Builder.Default
  @Column(nullable = false)
  private boolean isFalseAlarm = false;

  public static DangerEvent createDangerEvent(WorkZone workZone, Severity severity, String fileUrl,
      String vlmDescription, String violatedRegulation,
      String actionGuide, Map<String, Object> ragMetadata) {

    return DangerEvent.builder()
        .workZone(workZone)
        .severity(severity)
        .fileUrl(fileUrl)
        .vlmDescription(vlmDescription)
        .violatedRegulation(violatedRegulation)
        .actionGuide(actionGuide)
        .ragMetadata(ragMetadata)
        .build();
  }

  public void resolveEvent() {
    this.isResolved = true;
    this.resolvedAt = Instant.now();
  }
}
