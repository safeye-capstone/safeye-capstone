package com.safeye.backend.domain.virtualedge.service;

import com.safeye.backend.domain.dangerevent.service.DangerEventService;
import com.safeye.backend.domain.vlm.dto.response.VlmResponseDto;
import com.safeye.backend.domain.vlm.service.VlmApiService;
import com.safeye.backend.domain.zone.entity.WorkZone;
import com.safeye.backend.domain.zone.service.WorkZoneService;
import com.safeye.backend.global.error.BusinessException;
import jakarta.annotation.PostConstruct;
import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.LinkedBlockingQueue;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class VirtualEdgeSimulator {

  private final VlmApiService vlmApiService;
  private final WorkZoneService workZoneService;
  private final DangerEventService dangerEventService;

  // 환경변수
  private final LinkedBlockingQueue<File> edgeQueue = new LinkedBlockingQueue<>(3);

  // 환경변수
  private static final String MOCK_DIR_PATH = System.getProperty("user.dir") + "/uploads/mock/images/";

  private volatile boolean isRunning = false;
  private int currentFileIndex = 0;
  private List<File> mockImages = new ArrayList<>();

  @Value("${app.image.allowed-exts:jpg,jpeg,png,webp}")
  private List<String> allowedImageExts;

  @PostConstruct
  public void init() {
    File dir = new File(MOCK_DIR_PATH);
    if (!dir.exists()) {
      dir.mkdirs();
      log.warn("가상 엣지 테스트 폴더 미존재 - 경로: {}", MOCK_DIR_PATH);
      return;
    }

    File[] files = dir.listFiles((d, name) -> {
      int lastDot = name.lastIndexOf('.');
      if (lastDot == -1) return false;

      String ext = name.substring(lastDot + 1).toLowerCase();

      return allowedImageExts.contains(ext);
    });

    if (files != null && files.length > 0) {
      mockImages = Arrays.asList(files);
      log.info("[SUCCESS] 가상 엣지 초기화 완료 (모의 이미지 {}장 로드 완료)", mockImages.size());
    } else {
      log.warn("[WARN] 가상 엣지 테스트 폴더에 이미지 파일 미존재");
    }
  }

  public void start() {
    this.isRunning = true;
    log.info("[START] 가상 엣지 시뮬레이터 가동 시작");
  }

  public void stop() {
    this.isRunning = false;
    log.info("[STOP] 가상 엣지 시뮬레이터 중단");
  }

  // [Producer] 이미지를 큐에 적재
  @Scheduled(fixedRateString = "${app.simulator.push-rate:6000}")
  public void captureAndPushFrame() {
    if (!isRunning || mockImages == null || mockImages.isEmpty()) {
      return;
    }

    if (currentFileIndex >= mockImages.size()) {
      log.info("모의 이미지 전체 전송 완료 - 스케줄러 자동 중단");
      this.isRunning = false;
      this.currentFileIndex = 0;
      return;
    }

    File currentImage = mockImages.get(currentFileIndex);
    currentFileIndex++;

    // 백프레셔 및 적재
    while(!edgeQueue.offer(currentImage)) {
      File droppedImage = edgeQueue.poll();
      if (droppedImage != null) {
        log.warn("[Backpressure] 큐 적체 발생 - 오래된 이미지 폐기: {}", droppedImage.getName());
      }
    }

    log.info("[VirtualEdge] 이미지 큐 적재 완료: {} (현재 큐 크기: {})", currentImage.getName(), edgeQueue.size());
  }

  // [Consumer] VLM 전송 및 DB 적재
  @Scheduled(fixedDelayString = "${app.simulator.consume-delay:100}") // 동기 환경: 앞선 요청이 끝난 뒤 0.1초 후 다음 큐 확인
  public void processQueueAndSendToVlm() {
    if (!isRunning || edgeQueue.isEmpty()) {
      return;
    }

    File targetImage = null;
    try {
      targetImage = edgeQueue.poll();
      if (targetImage == null) {
        return;
      }

      String filename = targetImage.getName();
      if (!filename.contains("_")) {
        log.warn("올바르지 않은 파일명 포맷 스킵 - 파일명: {}", filename);
        return;
      }

      String zoneName = filename.split("_")[0];

      WorkZone zone = workZoneService.getWorkZoneByName(zoneName);

      log.info("VLM 분석 요청 발송 - 파일명: {}", filename);
      VlmResponseDto response = vlmApiService.analyzeLocalSimulatorFile(targetImage);

      log.info("[VirtualEdge] VLM 분석 완료 - 위험여부: {}, 심각도: {}, 설명: {}",
          response.isDanger(),
          response.severity(),
          response.vlmDescription());

      dangerEventService.processSimulatorDangerEvent(zone, targetImage, response);

    } catch (BusinessException e) {
      // throw 하지 않고 스케줄러가 다음 사진을 처리하도록 살려둠
      log.error("[VirtualEdge] 비즈니스 로직 에러 발생, 해당 이미지 스킵 - 코드: {}, 메시지: {}, 상세: {}",
          e.getErrorCode().getCode(), e.getMessage(), e.getDetails());
    } catch (Exception e) {
      log.error("[VirtualEdge] 시뮬레이터 큐 처리 중 시스템 예외 발생, 해당 이미지 스킵 - 파일명: {}",
          targetImage != null ? targetImage.getName() : "unknown", e);
    }
  }

}
