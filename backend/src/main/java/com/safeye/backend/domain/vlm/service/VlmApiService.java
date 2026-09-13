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
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
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


  @Value("${vlm.server.timeout}")
  private long vlmTimeout;


  // ==========================================================
  // 프론트엔드 단건 업로드
  // ==========================================================

  public VlmResponseDto analyzeFile(MultipartFile file) {

    String originalFilename = file.getOriginalFilename();

    String safeFilename =
        originalFilename != null
            && !originalFilename.isBlank()
            ? StringUtils.cleanPath(originalFilename)
            : "unknown_file";


    String contentType = file.getContentType();


    boolean videoFile = isVideoFile(
        contentType,
        safeFilename
    );


    String endpoint = videoFile
        ? "/api/vlm/analyze/video"
        : "/api/vlm/analyze";


    String partName = videoFile
        ? "video"
        : "image";


    MediaType mediaType = resolveMediaType(
        contentType,
        videoFile
    );


    log.info(
        "VLM 서버 분석 요청 시작 - 파일명: {}, type: {}, endpoint: {}",
        safeFilename,
        videoFile ? "video" : "image",
        endpoint
    );


    MultipartBodyBuilder bodyBuilder =
        new MultipartBodyBuilder();


    bodyBuilder
        .part(
            partName,
            file.getResource()
        )
        .filename(
            safeFilename
        )
        .contentType(
            mediaType
        );


    return executeWebClientPost(
        bodyBuilder,
        safeFilename,
        endpoint
    );
  }


  // ==========================================================
  // 가상 Edge Simulator
  // ==========================================================

  public VlmResponseDto analyzeLocalSimulatorFile(
      File file
  ) {

    log.info(
        "VLM 서버로 로컬 파일 분석 요청 시작 "
            + "(가상 엣지) - 파일명: {}",
        file.getName()
    );


    MultipartBodyBuilder bodyBuilder =
        new MultipartBodyBuilder();


    try {

      String mimeType =
          Files.probeContentType(
              file.toPath()
          );


      boolean videoFile = isVideoFile(
          mimeType,
          file.getName()
      );


      String endpoint = videoFile
          ? "/api/vlm/analyze/video"
          : "/api/vlm/analyze";


      String partName = videoFile
          ? "video"
          : "image";


      MediaType mediaType =
          resolveMediaType(
              mimeType,
              videoFile
          );


      bodyBuilder
          .part(
              partName,
              new FileSystemResource(file)
          )
          .filename(
              file.getName()
          )
          .contentType(
              mediaType
          );


      return executeWebClientPost(
          bodyBuilder,
          file.getName(),
          endpoint
      );


    } catch (IOException e) {

      log.error(
          "[VirtualEdge] MIME 타입 추출 중 오류 발생",
          e
      );


      throw new BusinessException(
          FileErrorCode.INVALID_FILE_EXTENSION,
          Map.of(
              "filename",
              file.getName()
          )
      );
    }
  }


  // ==========================================================
  // 이미지 / 영상 판별
  // ==========================================================

  private boolean isVideoFile(
      String contentType,
      String filename
  ) {

    if (
        contentType != null
        && contentType
            .toLowerCase(Locale.ROOT)
            .startsWith("video/")
    ) {

      return true;
    }


    String lowerFilename =
        filename
            .toLowerCase(
                Locale.ROOT
            );


    return (
        lowerFilename.endsWith(".mp4")
        || lowerFilename.endsWith(".avi")
        || lowerFilename.endsWith(".mov")
    );
  }


  // ==========================================================
  // MediaType
  // ==========================================================

  private MediaType resolveMediaType(
      String contentType,
      boolean videoFile
  ) {

    if (
        contentType != null
        && !contentType.isBlank()
    ) {

      try {

        return MediaType.parseMediaType(
            contentType
        );

      } catch (
          IllegalArgumentException ignored
      ) {

        // fallback 사용
      }
    }


    if (videoFile) {

      return MediaType.APPLICATION_OCTET_STREAM;
    }


    return MediaType.IMAGE_JPEG;
  }


  // ==========================================================
  // 실제 FastAPI 요청
  // ==========================================================

  private VlmResponseDto executeWebClientPost(
      MultipartBodyBuilder bodyBuilder,
      String filename,
      String endpoint
  ) {

    return vlmWebClient
        .post()
        .uri(endpoint)
        .contentType(
            MediaType.MULTIPART_FORM_DATA
        )
        .body(
            BodyInserters.fromMultipartData(
                bodyBuilder.build()
            )
        )
        .retrieve()

        .onStatus(
            HttpStatusCode::is4xxClientError,
            response -> {

              log.error(
                  "VLM 서버 클라이언트 에러 (4xx): {}",
                  response.statusCode()
              );

              return Mono.error(
                  new BusinessException(
                      GlobalErrorCode.VLM_SERVER_ERROR
                  )
              );
            }
        )

        .onStatus(
            HttpStatusCode::is5xxServerError,
            response -> {

              log.error(
                  "VLM 서버 내부 에러 (5xx): {}",
                  response.statusCode()
              );

              return Mono.error(
                  new BusinessException(
                      GlobalErrorCode.VLM_SERVER_ERROR
                  )
              );
            }
        )

        .bodyToMono(
            VlmResponseDto.class
        )

        .timeout(
            Duration.ofSeconds(
                vlmTimeout
            )
        )

        .onErrorResume(
            WebClientRequestException.class,
            e -> {

              Throwable cause =
                  e.getCause();


              if (
                  cause instanceof ConnectException
              ) {

                log.error(
                    "VLM 연결 실패: "
                        + "VLM 서버 다운 또는 연결 거부 - cause: {}",
                    cause.getMessage()
                );

              } else if (
                  cause instanceof ReadTimeoutException
                  || cause instanceof WriteTimeoutException
              ) {

                log.error(
                    "VLM 타임아웃: "
                        + "연산 시간 초과 - cause: {}",
                    cause.getMessage()
                );

              } else {

                log.error(
                    "VLM 요청 실패: "
                        + "기타 통신 오류 - cause: {}",
                    cause.getMessage()
                );
              }


              return Mono.error(
                  new BusinessException(
                      GlobalErrorCode.VLM_SERVER_ERROR,
                      Map.of(
                          "filename",
                          filename
                      )
                  )
              );
            }
        )

        .block();
  }
}