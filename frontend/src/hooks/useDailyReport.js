import { useCallback, useEffect, useState } from "react";
import { API_BASE, DAILY_REPORT_ENDPOINT } from "../constants/config";

/** 에러 응답을 화면에서 분기하기 좋은 형태로 변환합니다. */
function toReportError(json) {
  const code = json?.error?.code;
  const details = json?.error?.details;

  if (code === "REPORT-001") {
    return {
      type: "NOT_GENERATED",
      message: "아직 리포트가 생성되지 않았습니다.",
    };
  }

  if (code === "REPORT-004") {
    return {
      type: "NOT_AVAILABLE",
      message: "당일 및 미래 날짜의 리포트는 조회할 수 없습니다.",
      availableUntil: details?.availableUntil,
    };
  }

  return {
    type: "UNKNOWN",
    message: json?.error?.message ?? "리포트를 불러오지 못했습니다.",
  };
}

/**
 * 일일 리포트 조회
 *
 * 응답 예시:
 * {
 *   id, title,
 *   totalCount, criticalCount, warningCount, infoCount,
 *   resolvedCount,    // 현재 항상 0 (조치 API 미구현)
 *   falseAlarmCount,  // 현재 항상 0 (오탐 API 미구현)
 *   summary: { message, resolutionRate },
 *   fileUrl,          // 현재 항상 null (PDF 미구현)
 *   reportType        // "DAILY"
 * }
 * TODO: 백엔드에서 대상 일자 필드 추가 예정
 *
 * @param {string} [date] - "2026-09-16" 형식. 생략하면 서버가 어제로 처리합니다.
 */
export function useDailyReport(date) {
  const [state, setState] = useState({
    report: null,
    loading: true,
    error: null,
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let alive = true;

    const query = date ? `?date=${date}` : "";

    fetch(`${API_BASE}${DAILY_REPORT_ENDPOINT}${query}`)
      .then((res) => res.json().then((body) => ({ res, body })))
      .then(({ res, body }) => {
        if (!alive) return;

        if (!res.ok || !body.success) {
          setState({
            report: null,
            loading: false,
            error: toReportError(body),
          });
          return;
        }
        setState({ report: body.data, loading: false, error: null });
      })
      .catch(() => {
        if (!alive) return;
        setState({
          report: null,
          loading: false,
          error: { type: "UNKNOWN", message: "리포트를 불러오지 못했습니다." },
        });
      });

    return () => {
      alive = false;
    };
  }, [date, reloadKey]);

  const reload = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    setReloadKey((k) => k + 1);
  }, []);

  return { ...state, reload };
}
