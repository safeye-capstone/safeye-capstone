package com.safeye.backend.domain.complianceReport.entity;

import com.safeye.backend.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import java.time.LocalDate;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "compliance_reports")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class ComplianceReport extends BaseEntity {

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

  @Lob
  @Column(columnDefinition = "TEXT")
  private String summary;

  // TODO: S3 연동 시 nullable = false로 지정
  @Column(nullable = true, length = 1000)
  private String fileUrl;

  @Column(nullable = false, length = 50)
  private String reportType;

  public static ComplianceReport createDailyReport(
      String title, LocalDate targetDate,
      Integer total, Integer critical, Integer warning,
      Integer info, Integer resolved, Integer falseAlarm,
      String summaryJson) {

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
        .summary(summaryJson)
        .fileUrl(null)
        .reportType("DAILY")
        .build();
  }
}