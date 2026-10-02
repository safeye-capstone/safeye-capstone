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
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeoutException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.InvalidMediaTypeException;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClientRequest;


@Slf4j
@Service
@RequiredArgsConstructor
public class VlmApiService {

  private static final String IMAGE_ENDPOINT = "/api/vlm/analyze";
  private static final String VIDEO_ENDPOINT = "/api/vlm/analyze/video";

  private static final String IMAGE_PART = "image";
  private static final String VIDEO_PART = "video";

  private final WebClient vlmWebClient;

  @Value("${vlm.server.timeout:30}")
  private long imageTimeoutSeconds;

  @Value("${vlm.server.video-timeout:600}")
  private long videoTimeoutSeconds;

  // [단건 업로드 전용] 프론트엔드에서 수신한 MultipartFile 객체를 VLM 서버로 전송
  public VlmResponseDto analyzeFile(MultipartFile file) {
    String originalFilename = file.getOriginalFilename();
    String safeFilename = (originalFilename != null && !originalFilename.isBlank())
        ? StringUtils.cleanPath(originalFilename)
        : "unknown_file";

    // [영상 판별]
    boolean isVideo = isVideoContentType(file.getContentType());

    log.info("VLM 서버로 파일 분석 요청 시작 - 파일명: {}, 유형: {}", safeFilename, isVideo ? "영상" : "이미지");

    MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();

    bodyBuilder.part(isVideo ? VIDEO_PART : IMAGE_PART, file.getResource())
        .filename(safeFilename)
        .contentType(resolveMediaType(file.getContentType(), isVideo));

    return isVideo
        ? executeWebClientPost(bodyBuilder, safeFilename, VIDEO_ENDPOINT, Duration.ofSeconds(videoTimeoutSeconds))
        : executeWebClientPost(bodyBuilder, safeFilename, IMAGE_ENDPOINT, Duration.ofSeconds(imageTimeoutSeconds));
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

      bodyBuilder.part(IMAGE_PART, new FileSystemResource(file))
          .contentType(MediaType.parseMediaType(mimeType));

      bodyBuilder.part("delay", 0);

    } catch (IOException e) {
      log.error("[VirtualEdge] 시뮬레이터 파일 MIME 타입 추출 중 오류 발생", e);
      throw new BusinessException(FileErrorCode.INVALID_FILE_EXTENSION,
          Map.of("filename", file.getName()));
    }

    return executeWebClientPost(bodyBuilder, file.getName(), IMAGE_ENDPOINT, Duration.ofSeconds(imageTimeoutSeconds));
  }


  // [헬퍼 메서드] 조립된 MultipartBodyBuilder를 WebClient에 태워 전송 및 에러 핸들링
  private VlmResponseDto executeWebClientPost(MultipartBodyBuilder bodyBuilder, String filename, String endpoint, Duration timeout) {

    long startedAt = System.currentTimeMillis();

    VlmResponseDto response = vlmWebClient.post()
        .uri(endpoint)
        .contentType(MediaType.MULTIPART_FORM_DATA)

        // TODO: 추후 WebClientConfig로 로직 이동
        .httpRequest(httpRequest -> {
          HttpClientRequest nettyRequest = httpRequest.getNativeRequest();
          nettyRequest.responseTimeout(timeout);
        })

        .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
        .retrieve()

        .onStatus(HttpStatusCode::is4xxClientError, clientResponse -> {
          log.error("VLM 서버 클라이언트 에러 (4xx): {}", clientResponse.statusCode());
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR));
        })

        .onStatus(HttpStatusCode::is5xxServerError, clientResponse -> {
          log.error("VLM 서버 내부 에러 (5xx): {}", clientResponse.statusCode());
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR));
        })
        .bodyToMono(VlmResponseDto.class)

        .timeout(timeout)

        .onErrorResume(TimeoutException.class, e -> {
          log.error("VLM 타임아웃: {}초 안에 분석 결과를 받지 못함 - 파일명: {}", timeout.toSeconds(), filename);
          return Mono.error(new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR, Map.of("filename", filename, "reason", "TIMEOUT")));
        })

        .onErrorResume(WebClientRequestException.class, e -> {
          Throwable cause = e.getCause() != null ? e.getCause() : e;

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

    if (response == null) {
      log.error("VLM 응답 본문이 비어 있음 - 파일명: {}", filename);
      throw new BusinessException(GlobalErrorCode.VLM_SERVER_ERROR, Map.of("filename", filename, "reason", "EMPTY_RESPONSE"));
    }

    log.info("VLM 분석 완료 - 파일명: {}, 소요 시간: {}ms", filename, System.currentTimeMillis() - startedAt);
    return response;
  }

  // 영상 Content-Type 확인용 헬퍼 메서드
  private boolean isVideoContentType(String contentType) {
    return contentType != null && contentType.toLowerCase(Locale.ROOT).startsWith("video/");
  }

  // Content-Type이 없거나 형식이 잘못되면 기본값 사용 (이미지: image/jpeg, 영상: application/octet-stream)
  private MediaType resolveMediaType(String contentType, boolean isVideo) {
    if (contentType != null && !contentType.isBlank()) {
      try {
        return MediaType.parseMediaType(contentType);
      } catch (InvalidMediaTypeException e) {
        // 아래 기본값 사용
      }
    }
    return isVideo ? MediaType.APPLICATION_OCTET_STREAM : MediaType.IMAGE_JPEG;
  }
}