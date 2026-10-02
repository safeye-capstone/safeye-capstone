package com.safeye.backend.domain.compliance.repository;

import com.safeye.backend.domain.compliance.entity.ComplianceReport;
import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ComplianceReportRepository extends JpaRepository<ComplianceReport, UUID> {

  Optional<ComplianceReport> findByStartDate(LocalDate startDate);
}
