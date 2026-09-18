package com.safeye.backend.domain.dangerevent.exception;

import com.safeye.backend.global.error.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ReportErrorCode implements ErrorCode {

  COMPLIANCE_REPORT_NOT_FOUND(HttpStatus.NOT_FOUND, "REPORT-001", "요청하신 날짜의 컴플라이언스 리포트를 찾을 수 없습니다."),
  DUPLICATE_REPORT_EXISTS(HttpStatus.CONFLICT, "REPORT-002", "해당 날짜에 이미 생성된 리포트가 존재합니다."),
  INVALID_REPORT_DATE_RANGE(HttpStatus.BAD_REQUEST, "REPORT-003", "리포트 시작일은 종료일보다 이전이어야 합니다."),
  FUTURE_REPORT_NOT_AVAILABLE(HttpStatus.BAD_REQUEST, "REPORT-004", "당일 및 미래 날짜의 리포트는 조회할 수 없습니다. (전날 데이터까지 제공 가능)"),
  REPORT_GENERATION_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "REPORT-005", "일일 통계 리포트 자동 생성 중 오류가 발생했습니다.")
  ;

  private final HttpStatus status;
  private final String code;
  private final String message;
}
