import { useCallback, useEffect, useRef, useState } from "react";
import { createTodayReport, getDailyReport } from "../api/reports";

// 실제 error.code 값 확인 후 안 쓰는 쪽은 지우기
const NOT_FOUND_CODES = new Set(["COMPLIANCE_REPORT_NOT_FOUND", "REPORT-001"]);
const FUTURE_CODES = new Set(["FUTURE_REPORT_NOT_AVAILABLE", "REPORT-004"]);

function toReportError(err) {
  if (FUTURE_CODES.has(err.code)) {
    return {
      type: "NOT_AVAILABLE",
      message: "미래 날짜의 리포트는 조회할 수 없습니다.",
    };
  }

  return {
    type: "UNKNOWN",
    message: err.message ?? "리포트를 불러오지 못했습니다.",
  };
}

/**
 * 일일 리포트 조회 + 오늘 리포트 생성
 *
 * @param {string} date - "2026-10-03" 형식. 항상 넣습니다.
 *
 * 반환값
 * - report: 리포트 (없으면 null)
 * - notGenerated: 리포트가 아직 생성되지 않음 (에러 아님)
 * - error: 조회 실패 { type, message }
 * - generate: 오늘 리포트 생성/재집계. 결과를 { status, targetDate? }로 돌려줍니다.
 *   - APPLIED: POST 응답으로 report를 바꿈
 *   - DATE_CHANGED: 서버의 오늘이 화면 날짜와 달라 반영하지 않음 (targetDate로 이동 필요)
 *   - STALE: 요청 중에 날짜를 옮겨서 반영하지 않음
 *   - FAILED: 요청 실패. 기존 report는 유지됩니다.
 * - generating / generateError: 생성 요청 상태
 */
export function useDailyReport(date) {
  const [reloadKey, setReloadKey] = useState(0);
  const requestKey = `${date}#${reloadKey}`;

  const [state, setState] = useState({
    key: null,
    report: null,
    notGenerated: false,
    error: null,
  });

  const [gen, setGen] = useState({ key: null, pending: false, error: null });

  const requestKeyRef = useRef(requestKey);
  const dateRef = useRef(date);
  const generatingRef = useRef(false);

  useEffect(() => {
    requestKeyRef.current = requestKey;
    dateRef.current = date;
  }, [requestKey, date]);

  useEffect(() => {
    const controller = new AbortController();

    getDailyReport(date, { signal: controller.signal })
      .then((report) => {
        if (controller.signal.aborted) return;
        setState({ key: requestKey, report, notGenerated: false, error: null });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;

        if (NOT_FOUND_CODES.has(err.code)) {
          setState({
            key: requestKey,
            report: null,
            notGenerated: true,
            error: null,
          });
          return;
        }

        setState({
          key: requestKey,
          report: null,
          notGenerated: false,
          error: toReportError(err),
        });
      });

    return () => controller.abort();
  }, [date, requestKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const generate = useCallback(async () => {
    if (generatingRef.current) return null;
    generatingRef.current = true;

    const startedKey = requestKeyRef.current;
    const startedDate = dateRef.current;
    setGen({ key: startedKey, pending: true, error: null });

    try {
      const report = await createTodayReport();
      setGen({ key: startedKey, pending: false, error: null });

      // 요청 중에 날짜를 옮겼다면 화면에 반영하지 않습니다.
      if (requestKeyRef.current !== startedKey) {
        return { status: "STALE" };
      }

      // 서버는 항상 서버 시각의 오늘을 집계합니다.
      // 자정을 넘겨 다른 날짜의 리포트가 오면 지금 화면에 넣지 않습니다.
      if (report?.targetDate && report.targetDate !== startedDate) {
        return { status: "DATE_CHANGED", targetDate: report.targetDate };
      }

      setState({
        key: startedKey,
        report,
        notGenerated: false,
        error: null,
      });
      return { status: "APPLIED" };
    } catch (err) {
      setGen({
        key: startedKey,
        pending: false,
        error: err.message ?? "리포트를 생성하지 못했습니다.",
      });
      return { status: "FAILED" };
    } finally {
      generatingRef.current = false;
    }
  }, []);

  const loading = state.key !== requestKey;

  return {
    report: loading ? null : state.report,
    notGenerated: loading ? false : state.notGenerated,
    error: loading ? null : state.error,
    loading,
    reload,
    generate,
    generating: gen.pending,
    generateError: gen.key === requestKey ? gen.error : null,
  };
}
