package com.safeye.backend.domain.complianceReport.service;

import com.safeye.backend.domain.complianceReport.dto.response.ComplianceReportDto;
import com.safeye.backend.domain.complianceReport.entity.ComplianceReport;
import com.safeye.backend.domain.complianceReport.repository.ComplianceReportRepository;
import com.safeye.backend.domain.dangerevent.entity.Severity;
import com.safeye.backend.domain.dangerevent.exception.ReportErrorCode;
import com.safeye.backend.domain.dangerevent.repository.DangerEventRepository;
import com.safeye.backend.global.error.BusinessException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ComplianceReportBatchService {

  private final DangerEventRepository dangerEventRepository;
  private final ComplianceReportRepository complianceReportRepository;

  @Scheduled(cron = "0 0 0 * * *")
  @Transactional
  public void generateDailyReport() {
    LocalDate targetDate = LocalDate.now(ZoneId.of("Asia/Seoul")).minusDays(1);
    log.info("[{}] 일일 컴플라이언스 통계 배치를 시작합니다.", targetDate);

    if (complianceReportRepository.existsByStartDate(targetDate)) {
      log.warn("[{}] 이미 생성된 리포트가 존재하여 배치를 중단합니다.", targetDate);
      throw new BusinessException(ReportErrorCode.DUPLICATE_REPORT_EXISTS,
          Map.of("date", targetDate));
    }

    Instant startOfDay = targetDate.atStartOfDay(ZoneId.of("Asia/Seoul")).toInstant();
    Instant endOfDay = targetDate.atTime(LocalTime.MAX).atZone(ZoneId.of("Asia/Seoul")).toInstant();

    int total = 0, critical = 0, warning = 0, info = 0;
    int resolved = 0;
    int falseAlarm = 0;
    String summaryJson = "{}";

    try {
      List<Object[]> stats = dangerEventRepository.countDailyStats(startOfDay, endOfDay);

      for (Object[] row : stats) {
        Severity severity = (Severity) row[0];
        boolean isResolved = (boolean) row[1];
        boolean isFalseAlarm = (boolean) row[2];
        int count = ((Long) row[3]).intValue();

        total += count;
        if (Severity.CRITICAL.equals(severity)) {
          critical += count;
        } else if (Severity.WARNING.equals(severity)) {
          warning += count;
        } else if (Severity.INFO.equals(severity)) {
          info += count;
        }

        if (isResolved) {
          resolved += count;
        }
        if (isFalseAlarm) {
          falseAlarm += count;
        }
      }
    } catch (Exception e) {
      log.error("[{}] DB 통계 집계 중 알 수 없는 오류 발생", targetDate, e);
      throw new BusinessException(ReportErrorCode.REPORT_GENERATION_FAILED);
    }

    ComplianceReport report = ComplianceReport.createDailyReport(
        targetDate.toString() + " SEA 컴플라이언스 리포트",
        targetDate, total, critical, warning, info, resolved, falseAlarm, summaryJson
    );

    complianceReportRepository.save(report);
    log.info("[{}] 일일 통계 적재 완료 - 총 위반 건수: {}", targetDate, total);
  }

  @Transactional(readOnly = true)
  public ComplianceReportDto getDailyReport(LocalDate date) {
    LocalDate availableDate = LocalDate.now(ZoneId.of("Asia/Seoul")).minusDays(1);
    if (date.isAfter(availableDate)) {
      log.warn("[{}] 리포트 조회 실패 - 미래 또는 당일 데이터는 아직 조회할 수 없습니다. (최대 조회 가능 날짜: {})", date,
          availableDate);
      throw new BusinessException(ReportErrorCode.FUTURE_REPORT_NOT_AVAILABLE,
          Map.of("requestedDate", date.toString(), "availableUntil", availableDate));
    }

    ComplianceReport report = complianceReportRepository.findByStartDate(date)
        .orElseThrow(() -> {
          log.warn("[{}] 리포트 조회 실패 - 해당 날짜의 리포트가 존재하지 않습니다.", date);
          return new BusinessException(ReportErrorCode.COMPLIANCE_REPORT_NOT_FOUND,
              Map.of("requestedDate", date.toString()));
        });

    return ComplianceReportDto.from(report);
  }
}
