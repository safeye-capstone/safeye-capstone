package com.safeye.backend.domain.complianceReport.dto.response;

import com.safeye.backend.domain.complianceReport.entity.ComplianceReport;
import java.util.UUID;

public record ComplianceReportDto(
    UUID id,
    String title,

    Integer totalCount,
    Integer criticalCount,
    Integer warningCount,

    Integer infoCount,
    Integer resolvedCount,
    Integer falseAlarmCount,

    SummaryInfo summary,
    String fileUrl,
    String reportType
) {

  public record SummaryInfo(
      String message, // 메시지
      Integer resolutionRate // 조치율
  ) {}

  public static ComplianceReportDto from(ComplianceReport report) {

    int total = report.getTotalCount() != null ? report.getTotalCount() : 0;
    int resolved = report.getResolvedCount() != null ? report.getResolvedCount() : 0;
    int calculatedResolutionRate = total > 0 ? (resolved * 100 / total) : 0;

    SummaryInfo summaryInfo = new SummaryInfo(
        "Safety(안전), Explanation(설명), Analysis(분석) 아키텍처를 기반으로 분석된 일일 현장 안전 컴플라이언스 종합 통계입니다.",
        calculatedResolutionRate
    );

    return new ComplianceReportDto(
        report.getId(),
        report.getTitle(),
        report.getTotalCount(),
        report.getCriticalCount(),
        report.getWarningCount(),
        report.getInfoCount(),
        report.getResolvedCount(),
        report.getFalseAlarmCount(),
        summaryInfo,
        report.getFileUrl(),
        report.getReportType()
    );
  }
}
