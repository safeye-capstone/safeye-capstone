package com.safeye.backend.domain.complianceReport.repository;

import com.safeye.backend.domain.complianceReport.entity.ComplianceReport;
import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ComplianceReportRepository extends JpaRepository<ComplianceReport, UUID> {

  Optional<ComplianceReport> findByStartDate(LocalDate startDate);

  // 일일 리포트 배치 중복 생성 검증 전용
  boolean existsByStartDate(LocalDate targetDate);
}
