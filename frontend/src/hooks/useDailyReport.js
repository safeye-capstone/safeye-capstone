import { useCallback, useEffect, useState } from "react";
import { getDailyReport } from "../api/reports";

function toReportError(err) {
  if (err.code === "REPORT-001") {
    return {
      type: "NOT_GENERATED",
      message: "아직 리포트가 생성되지 않았습니다.",
    };
  }

  if (err.code === "REPORT-004") {
    return {
      type: "NOT_AVAILABLE",
      message: "당일 및 미래 날짜의 리포트는 조회할 수 없습니다.",
      availableUntil: err.details?.availableUntil,
    };
  }

  return {
    type: "UNKNOWN",
    message: err.message ?? "리포트를 불러오지 못했습니다.",
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
 *
 * @param {string} [date] - "2026-09-16" 형식. 생략하면 서버가 어제로 처리합니다.
 */
export function useDailyReport(date) {
  const [reloadKey, setReloadKey] = useState(0);

  const requestKey = `${date ?? "latest"}#${reloadKey}`;

  const [state, setState] = useState({
    key: null,
    report: null,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();

    getDailyReport(date, { signal: controller.signal })
      .then((report) => {
        if (controller.signal.aborted) return;
        setState({ key: requestKey, report, error: null });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setState({ key: requestKey, report: null, error: toReportError(err) });
      });

    return () => controller.abort();
  }, [date, requestKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const loading = state.key !== requestKey;

  return {
    report: loading ? null : state.report,
    error: loading ? null : state.error,
    loading,
    reload,
  };
}
