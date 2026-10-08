package com.safeye.backend.domain.dangerevent.repository;

import com.safeye.backend.domain.dangerevent.entity.DangerEvent;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface DangerEventRepository extends JpaRepository<DangerEvent, UUID> {

  @Query("SELECT d FROM DangerEvent d JOIN FETCH d.workZone " +
      "WHERE d.createdAt >= :start AND d.createdAt < :end")
  List<DangerEvent> findAllWithZoneBetween(@Param("start") Instant start,
      @Param("end") Instant end);
}
