package com.safeye.backend.domain.compliance.service;

import java.time.LocalDate;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class ComplianceReportScheduler {

  private final ComplianceReportService complianceReportService;

  @Scheduled(cron = "0 0 0 * * *", zone = "Asia/Seoul")
  public void generateYesterdayReport() {
    LocalDate yesterday = LocalDate.now(ComplianceReportService.KST).minusDays(1);
    try {
      complianceReportService.generateDailyReport(yesterday);
    } catch (Exception e) {
      log.error("[{}] 일일 리포트 자동 생성 실패", yesterday, e);
    }
  }

}
