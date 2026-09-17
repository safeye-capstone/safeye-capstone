package com.safeye.backend.domain.dangerevent.service;

import com.safeye.backend.domain.dangerevent.dto.request.DangerEventUploadRequest;
import com.safeye.backend.domain.dangerevent.dto.response.DangerEventDto;
import com.safeye.backend.domain.dangerevent.entity.DangerEvent;
import com.safeye.backend.domain.dangerevent.event.DangerEventCreatedEvent;
import com.safeye.backend.domain.dangerevent.repository.DangerEventRepository;
import com.safeye.backend.domain.file.service.FileStorageService;
import com.safeye.backend.domain.vlm.dto.response.VlmResponseDto;
import com.safeye.backend.domain.vlm.service.VlmApiService;
import com.safeye.backend.domain.zone.entity.WorkZone;
import com.safeye.backend.domain.zone.service.WorkZoneService;
import java.io.File;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class DangerEventService {

  private final DangerEventRepository dangerEventRepository;
  private final FileStorageService fileStorageService;
  private final WorkZoneService workZoneService;
  private final VlmApiService vlmApiService;
  private final ApplicationEventPublisher eventPublisher;

  public DangerEventDto createDangerEvent(DangerEventUploadRequest request) {
    WorkZone workZone = workZoneService.getWorkZoneById(request.zoneId());

    String localFileUrl = fileStorageService.storeFile(request.file());

    VlmResponseDto vlmResponseDto = vlmApiService.analyzeFile(request.file());

    DangerEvent dangerEvent = DangerEvent.createDangerEvent(
        workZone,
        vlmResponseDto.severity(),
        localFileUrl,
        vlmResponseDto.vlmDescription(),
        vlmResponseDto.violatedRegulation(),
        vlmResponseDto.actionGuide(),
        null
    );

    dangerEventRepository.save(dangerEvent);

    log.info("위험 이벤트 저장 완료 (정상/위험 모두 포함) - dangerEventId: {}, severity: {}", dangerEvent.getId(),
        vlmResponseDto.severity());
    return DangerEventDto.from(dangerEvent);
  }

  public void processSimulatorDangerEvent(WorkZone workZone, File file,
      VlmResponseDto vlmResponseDto) {
    String mockFileUrl = "http://localhost:8080/uploads/mock/images/" + file.getName();

    DangerEvent dangerEvent = DangerEvent.createDangerEvent(
        workZone,
        vlmResponseDto.severity(),
        mockFileUrl,
        vlmResponseDto.vlmDescription(),
        vlmResponseDto.violatedRegulation(),
        vlmResponseDto.actionGuide(),
        null
    );

    dangerEventRepository.save(dangerEvent);
    log.info("[VirtualEdge] 위험 이벤트 저장 완료 (정상/위험 모두 포함) - dangerEventId: {}, severity: {}",
        dangerEvent.getId(), vlmResponseDto.severity());

    eventPublisher.publishEvent(new DangerEventCreatedEvent(DangerEventDto.from(dangerEvent)));
  }
}
