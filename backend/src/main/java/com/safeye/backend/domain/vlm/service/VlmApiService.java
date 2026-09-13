package com.safeye.backend.domain.vlm.service;

import com.safeye.backend.domain.file.exception.FileErrorCode;
import com.safeye.backend.domain.vlm.dto.response.VlmResponseDto;
import com.safeye.backend.global.error.BusinessException;
import com.safeye.backend.global.error.GlobalErrorCode;
import io.netty.handler.timeout.ReadTimeoutException;
import io.netty.handler.timeout.WriteTimeoutException;
import java.io.File;
import java.io.IOException;
import java.net.ConnectException;
import java.nio.file.Files;
import java.time.Duration;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import reactor.core.publisher.Mono;


@Slf4j
@Service
@RequiredArgsConstructor
public class VlmApiService {

  private final WebClient vlmWebClient;

  // [단건 업로드 전용] 프론트엔드에서 수신한 MultipartFile 객체를 VLM 서버로 전송
  public VlmResponseDto analyzeFile(MultipartFile file) {
    String originalFilename = file.getOriginalFilename();
    String safeFilename = (originalFilename != null && !originalFilename.isBlank())
        ? StringUtils.cleanPath(originalFilename)
        : "unknown_image.jpg";

    log.info("VLM 서버로 파일 분석 요청 시작 - 파일명: {}", file.getOriginalFilename());

    MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();

    bodyBuilder.part("image", file.getResource())
        .filename(file.getOriginalFilename())
        .contentType(MediaType.parseMediaType(
            file.getContentType() != null ? file.getContentType() : MediaType.IMAGE_JPEG_VALUE));

    bodyBuilder.part("delay", 0);

    return executeWebClientPost(bodyBuilder, safeFilename);
  }

  // [시뮬레이터 전용] 가상 엣지 스케줄러가 읽어들인 File 객체를 VLM 서버로 전송
  public VlmResponseDto analyzeLocalSimulatorFile(File file) {
    log.info("VLM 서버로 로컬 파일 분석 요청 시작 (가상 엣지) - 파일명: {}", file.getName());

    MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();

    try {
      String mimeType = Files.probeContentType(file.toPath());
      if (mimeType == null) {
        mimeType = MediaType.IMAGE_JPEG_VALUE;
      }

      bodyBuilder.part("image", new FileSystemResource(file))
          .contentType(MediaType.parseMediaType(mimeType));

      bodyBuilder.part("delay", 0);

    } catch (IOException e) {
      log.error("[VirtualEdge] 시뮬레이터 파일 MIME 타입 추출 중 오류 발생", e);
      throw new BusinessException(FileErrorCode.INVALID_FILE_EXTENSION, Map.of("filename", file.getName()));
    }

    return executeWebClientPost(bodyBuilder, file.getName());
  }


  // [헬퍼 메서드] 조립된 MultipartBodyBuilder를 WebClient에 태워 전송 및 에러 핸들링
  private VlmResponseDto executeWebClientPost(MultipartBodyBuilder bodyBuilder, String filename) {
    return vlmWebClient.post()
        .uri("/v1/analyze")
        .contentType(MediaType.MULTIPART_FORM_DATA)
        .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
        .retrieve()

        .onStatus(HttpStatusCode::is4xxClientError, response -> {
          log.error("VLM 서버 클라이언트 에러 (4xx): {}", response.statusCode());
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR));
        })

        .onStatus(HttpStatusCode::is5xxServerError, response -> {
          log.error("VLM 서버 내부 에러 (5xx): {}", response.statusCode());
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR));
        })
        .bodyToMono(VlmResponseDto.class)

        // VLM 서버의 30초 무한 대기 타임아웃
        .timeout(Duration.ofSeconds(30))

        .onErrorResume(WebClientRequestException.class, e -> {
          Throwable cause = e.getCause();

          if (cause instanceof ConnectException) {
            log.error("VLM 연결 실패: VLM 서버 다운 또는 네트워크 연결 거부 - cause: {}", cause.getMessage());
          } else if (cause instanceof ReadTimeoutException
              || cause instanceof WriteTimeoutException) {
            log.error("VLM 타임아웃: VLM 서버 연산 시간 초과 - cause: {}", cause.getMessage());
          } else {
            log.error("VLM 요청 실패: 기타 물리적 통신 오류 발생 - cause: {}", cause.getMessage());
          }
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR,
              Map.of("filename", filename)));
        })

        .block();
  }
}
