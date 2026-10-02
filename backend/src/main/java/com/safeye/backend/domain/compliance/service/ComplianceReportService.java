package com.safeye.backend.domain.compliance.service;

import com.safeye.backend.domain.compliance.dto.response.ComplianceReportDto;
import com.safeye.backend.domain.compliance.entity.ComplianceReport;
import com.safeye.backend.domain.compliance.entity.ReportSummary;
import com.safeye.backend.domain.compliance.entity.ReportSummary.ZoneStat;
import com.safeye.backend.domain.compliance.repository.ComplianceReportRepository;
import com.safeye.backend.domain.dangerevent.entity.DangerEvent;
import com.safeye.backend.domain.dangerevent.entity.VlmDecisionState;
import com.safeye.backend.domain.dangerevent.exception.ReportErrorCode;
import com.safeye.backend.domain.dangerevent.repository.DangerEventRepository;
import com.safeye.backend.domain.zone.entity.WorkZone;
import com.safeye.backend.global.error.BusinessException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ComplianceReportService {

  public static final ZoneId KST = ZoneId.of("Asia/Seoul");

  private final DangerEventRepository dangerEventRepository;
  private final ComplianceReportRepository complianceReportRepository;

  // 일일 리포트 생성
  // [이미 리포트가 있을 때]
  // 완성본(그날이 끝난 뒤, 즉 자정 배치가 만든 것) → 다시 만들지 않고 그대로 반환
  // 중간 집계본(그날 안에 수동으로 만든 것) → 지우고 지금까지의 데이터로 재생성

  @Transactional
  public ComplianceReportDto generateDailyReport(LocalDate targetDate) {
    if (targetDate.isAfter(LocalDate.now(KST))) {
      throw new BusinessException(ReportErrorCode.FUTURE_REPORT_NOT_AVAILABLE,
          Map.of("requestedDate", targetDate.toString()));
    }

    Instant start = targetDate.atStartOfDay(KST).toInstant();
    Instant end = targetDate.plusDays(1).atStartOfDay(KST).toInstant();

    Optional<ComplianceReport> existing = complianceReportRepository.findByStartDate(targetDate);
    if (existing.isPresent()) {
      ComplianceReport existingReport = existing.get();

      if (!existingReport.getCreatedAt().isBefore(end)) {
        log.info("[{}] 완성된 리포트가 이미 존재하여 생성을 건너뜁니다.", targetDate);
        return ComplianceReportDto.from(existingReport);
      }

      log.info("[{}] 중간 집계 리포트가 존재하므로 삭제하고 다시 생성합니다.", targetDate);
      complianceReportRepository.delete(existingReport);
      complianceReportRepository.flush();
    }

    log.info("[{}] 일일 컴플라이언스 통계 집계를 시작합니다.", targetDate);
    List<DangerEvent> events;
    try {
      events = dangerEventRepository.findAllWithZoneBetween(start, end);
    } catch (Exception e) {
      log.error("[{}] 리포트 집계용 이벤트 조회 중 오류 발생", targetDate, e);
      throw new BusinessException(ReportErrorCode.REPORT_GENERATION_FAILED);
    }

    ComplianceReport report = buildReport(targetDate, events);
    complianceReportRepository.save(report);

    log.info("[{}] 일일 리포트 생성 완료 - 분석 이벤트: {}건, 판정별: {}", targetDate, events.size(),
        report.getSummary().decisionStateCounts());
    return ComplianceReportDto.from(report);
  }

  @Transactional(readOnly = true)
  public ComplianceReportDto getDailyReport(LocalDate date) {
    if (date.isAfter(LocalDate.now(KST))) {
      log.warn("[{}] 리포트 조회 실패 - 미래 날짜는 조회할 수 없습니다.", date);
      throw new BusinessException(ReportErrorCode.FUTURE_REPORT_NOT_AVAILABLE,
          Map.of("requestedDate", date.toString()));
    }

    ComplianceReport report = complianceReportRepository.findByStartDate(date)
        .orElseThrow(() -> {
          log.warn("[{}] 리포트 조회 실패 - 해당 날짜의 리포트가 존재하지 않습니다.", date);
          return new BusinessException(ReportErrorCode.COMPLIANCE_REPORT_NOT_FOUND,
              Map.of("requestedDate", date.toString()));
        });

    return ComplianceReportDto.from(report);
  }

  // 집계

  // 하루치 이벤트를 한 번 순회하면서 컬럼 값(severity별 건수)과 summary를 함께 계산
  private ComplianceReport buildReport(LocalDate date, List<DangerEvent> events) {
    int critical = 0;
    int warning = 0;
    int info = 0;

    // [판정별 건수]
    Map<String, Long> decisionStateCounts = new LinkedHashMap<>();
    for (VlmDecisionState state : VlmDecisionState.values()) {
      decisionStateCounts.put(state.name(), 0L);
    }

    // [구역별 통계]
    Map<UUID, ZoneCounter> zoneCounters = new HashMap<>();

    for (DangerEvent event : events) {
      // 주의: 검토 대기도 WARNING으로 오므로 warningCount에 섞임. 확정/검토 구분은 summary에서 수행.
      if (event.getSeverity() != null) {
        switch (event.getSeverity()) {
          case CRITICAL -> critical++;
          case WARNING -> warning++;
          case INFO -> info++;
        }
      }

      VlmDecisionState state = VlmDecisionState.from(event.getRagMetadata());
      decisionStateCounts.merge(state.name(), 1L, Long::sum);

      WorkZone zone = event.getWorkZone();
      zoneCounters
          .computeIfAbsent(zone.getId(), zoneId -> new ZoneCounter(zone.getZoneName()))
          .add(state);
    }

    List<ZoneStat> zoneStats = zoneCounters.entrySet().stream()
        .map(entry -> entry.getValue().toStat(entry.getKey()))
        .sorted(Comparator.comparing(ZoneStat::zoneName))
        .toList();

    ReportSummary summary = new ReportSummary(decisionStateCounts, zoneStats);

    // TODO: 조치 완료, 오탐 처리 기능 생성 후 실제 건수로 집계
    int resolved = 0;
    int falseAlarm = 0;

    return ComplianceReport.createDailyReport(
        date + " SEA 컴플라이언스 리포트", date, events.size(), critical, warning, info, resolved, falseAlarm, summary
    );
  }

  private static final class ZoneCounter {

    private final String zoneName;
    private long analyzed;
    private long confirmed;
    private long reviewRequired;

    private ZoneCounter(String zoneName) {
      this.zoneName = zoneName;
    }

    void add(VlmDecisionState state) {
      analyzed++;
      if (state == VlmDecisionState.CONFIRMED) {
        confirmed++;
      } else if (state == VlmDecisionState.REVIEW_REQUIRED) {
        reviewRequired++;
      }
    }

    ZoneStat toStat(UUID zoneId) {
      return new ZoneStat(zoneId, zoneName, analyzed, confirmed, reviewRequired);
    }
  }
}
