package com.safeye.backend.domain.compliance.dto.response;

import com.safeye.backend.domain.compliance.entity.ComplianceReport;
import com.safeye.backend.domain.compliance.entity.ReportSummary;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ComplianceReportDto(
    UUID id,
    String title,
    LocalDate targetDate,

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

  private static final String SUMMARY_MESSAGE = "Safety(안전), Explanation(설명), Analysis(분석) 아키텍처를 기반으로 분석된 일일 현장 안전 컴플라이언스 종합 통계입니다.";

  public record SummaryInfo(
      String message,                           // 고정 안내 메시지
      Integer resolutionRate,                   // 조치율(%) - TODO(프로토타입 이후): 현재 0
      Map<String, Long> decisionStateCounts,    // 판정별 건수
      //TODO: Map<String, Long> riskTypeCounts,         // 위험 유형별 건수 (확정·검토 대기만)
      List<ReportSummary.ZoneStat> zoneStats    // 구역별 통계
  ) {

  }

  public static ComplianceReportDto from(ComplianceReport report) {

    ReportSummary stored = report.getSummary();

    Map<String, Long> decisionStateCounts =
        (stored != null && stored.decisionStateCounts() != null) ? stored.decisionStateCounts()
            : Map.of();
    List<ReportSummary.ZoneStat> zoneStats =
        (stored != null && stored.zoneStats() != null) ? stored.zoneStats() : List.of();

    SummaryInfo summaryInfo = new SummaryInfo(
        SUMMARY_MESSAGE,
        0, // TODO: 조치 기능이 생기면 계산
        decisionStateCounts,
        zoneStats
    );

    return new ComplianceReportDto(
        report.getId(),
        report.getTitle(),
        report.getStartDate(),
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
