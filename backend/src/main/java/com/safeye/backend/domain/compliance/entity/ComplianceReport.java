package com.safeye.backend.domain.compliance.entity;

import com.safeye.backend.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "compliance_reports",
uniqueConstraints = @UniqueConstraint(
    name = "uk_compliance_report_type_start_date",
    columnNames = {"report_type", "start_date"}
))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class ComplianceReport extends BaseEntity {

  public static final ZoneId KST = ZoneId.of("Asia/Seoul");

  @Column(nullable = false, length = 255)
  private String title;

  @Column(nullable = false)
  private LocalDate startDate;

  @Column(nullable = false)
  private LocalDate endDate;

  @Column(nullable = false)
  private Integer totalCount;

  @Column(nullable = false)
  private Integer criticalCount;

  @Column(nullable = false)
  private Integer warningCount;

  @Column(nullable = false)
  private Integer infoCount;

  @Column(nullable = false)
  private Integer resolvedCount;

  @Column(nullable = false)
  private Integer falseAlarmCount;

  @JdbcTypeCode(SqlTypes.JSON)
  @Column(columnDefinition = "jsonb")
  private ReportSummary summary;

  // TODO: S3 연동 시 nullable = false로 지정
  @Column(nullable = true, length = 1000)
  private String fileUrl;

  @Column(nullable = false, length = 50)
  private String reportType;

  public static ComplianceReport createDailyReport(
      String title, LocalDate targetDate,
      Integer total, Integer critical, Integer warning,
      Integer info, Integer resolved, Integer falseAlarm,
      ReportSummary summary) {

    return ComplianceReport.builder()
        .title(title)
        .startDate(targetDate)
        .endDate(targetDate)
        .totalCount(total)
        .criticalCount(critical)
        .warningCount(warning)
        .infoCount(info)
        .resolvedCount(resolved)
        .falseAlarmCount(falseAlarm)
        .summary(summary)
        .fileUrl(null)
        .reportType("DAILY")
        .build();
  }

  // TODO: 추후 완성본 여부를 시각으로 추측하지 않고, 만들 때 기록한 상태를 그대로 보도록 리팩토링
  public boolean isFinal() {
    Instant dayEnd = startDate.plusDays(1).atStartOfDay(KST).toInstant();
    return !getCreatedAt().isBefore(dayEnd);
  }
}