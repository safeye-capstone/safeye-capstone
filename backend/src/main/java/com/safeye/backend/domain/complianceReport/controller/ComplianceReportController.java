package com.safeye.backend.domain.complianceReport.controller;

import com.safeye.backend.domain.complianceReport.dto.response.ComplianceReportDto;
import com.safeye.backend.domain.complianceReport.service.ComplianceReportBatchService;
import com.safeye.backend.global.common.ApiResponse;
import java.time.LocalDate;
import java.time.ZoneId;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/reports")
public class ComplianceReportController {

  private final ComplianceReportBatchService complianceReportBatchService;

  @GetMapping("/daily")
  public ResponseEntity<ApiResponse<ComplianceReportDto>> getDailyReport(
      @RequestParam(name = "date", required = false)
      @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate date
  ) {
    // 날짜를 지정하지 않으면, 기본값으로 어제 데이터 리포트를 반환
    if (date == null) {
      date = LocalDate.now(ZoneId.of("Asia/Seoul")).minusDays(1);
    }

    ComplianceReportDto report = complianceReportBatchService.getDailyReport(date);

    return ResponseEntity.ok(ApiResponse.ok(report));
  }
}
