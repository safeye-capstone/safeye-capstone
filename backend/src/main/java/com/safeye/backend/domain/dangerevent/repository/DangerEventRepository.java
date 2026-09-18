package com.safeye.backend.domain.dangerevent.repository;

import com.safeye.backend.domain.dangerevent.entity.DangerEvent;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface DangerEventRepository extends JpaRepository<DangerEvent, UUID> {

  @Query("SELECT d.severity, d.isResolved, d.isFalseAlarm, COUNT(d.id) " +
      "FROM DangerEvent d " +
      "WHERE d.createdAt >= :start AND d.createdAt < :end " +
      "GROUP BY d.severity, d.isResolved, d.isFalseAlarm")
  List<Object[]> countDailyStats(@Param("start") Instant start, @Param("end") Instant end);
}
