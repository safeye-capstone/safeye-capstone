package com.safeye.backend.domain.compliance.entity;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ReportSummary(
    Map<String, Long> decisionStateCounts, // 판정별 건수
    //TODO: Map<String, Long> riskTypeCounts, // 위험 유형별 건수
    List<ZoneStat> zoneStats // 구역별 통계
) {

  public record ZoneStat(
      UUID zoneId,
      String zoneName,
      long analyzedCount,
      long confirmedCount,
      long reviewRequiredCount
  ) {

  }

}
