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

    // 안전한 상황 isDanger = false 일 경우
    if (!vlmResponseDto.isDanger()) {
      log.info("정상 상황 감지. DB 적재 스킵 - isDanger: false");

      // TODO: 임시 응답 확인용 (추후 삭제)
      DangerEvent dangerEvent = DangerEvent.createDangerEvent(
          workZone,
          vlmResponseDto.severity(),
          localFileUrl,
          vlmResponseDto.vlmDescription(),
          vlmResponseDto.violatedRegulation(),
          vlmResponseDto.actionGuide(),
          null
      );
      return DangerEventDto.from(dangerEvent);
    }

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

    log.info("위험 이벤트 저장 완료 - dangerEventId: {}", dangerEvent.getId());
    return DangerEventDto.from(dangerEvent);
  }

  public void processSimulatorDangerEvent(WorkZone workZone, File file, VlmResponseDto vlmResponseDto) {
    if (!vlmResponseDto.isDanger()) {
      log.info("정상 상황 감지. DB 적재 스킵 - isDanger: false");
      return;
    }

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
    log.info("위험 이벤트 저장 완료 - dangerEventId: {}", dangerEvent.getId());

    eventPublisher.publishEvent(
            new DangerEventCreatedEvent(DangerEventDto.from(dangerEvent))
    );
  }
}
