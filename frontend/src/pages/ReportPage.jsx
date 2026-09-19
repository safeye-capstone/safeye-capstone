import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import SeverityBar from "../components/SeverityBar";
import { useDailyReport } from "../hooks/useDailyReport";
import { addDays, formatReportDate, getYesterday } from "../utils/date";

function StatCard({ label, value, unit = "건", muted = false, note }) {
  return (
    <div className="border border-border rounded-lg bg-white p-4">
      <p className="text-xs text-muted mb-1.5">{label}</p>
      {muted ? (
        <p className="text-sm text-muted">{note}</p>
      ) : (
        <p className="text-2xl font-bold text-ink leading-none">
          {value}
          <span className="text-sm font-normal text-muted ml-1">{unit}</span>
        </p>
      )}
    </div>
  );
}

function ReportPage() {
  const [date, setDate] = useState(undefined);
  const { report, loading, error } = useDailyReport(date);

  const maxDate = getYesterday();
  const shown = report?.targetDate ?? date ?? maxDate;
  const atLatest = shown >= maxDate;

  const move = (days) => {
    if (!shown) return;
    setDate(addDays(shown, days));
  };

  return (
    <div className="w-full max-w-4xl">
      <PageHeader />

      <div className="flex items-center gap-3 mb-5">
        <button
          type="button"
          onClick={() => move(-1)}
          disabled={!shown}
          className="p-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          aria-label="이전 날짜"
        >
          <ChevronLeft size={16} />
        </button>

        <span className="text-sm font-bold text-ink min-w-[11rem] text-center">
          {shown ? formatReportDate(shown) : "불러오는 중..."}
        </span>

        <button
          type="button"
          onClick={() => move(1)}
          disabled={!shown || atLatest}
          className="p-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          aria-label="다음 날짜"
        >
          <ChevronRight size={16} />
        </button>

        {date !== undefined && (
          <button
            type="button"
            onClick={() => setDate(undefined)}
            className="text-xs text-muted underline ml-1"
          >
            최신으로
          </button>
        )}
      </div>

      {loading && (
        <div className="border border-border rounded-lg bg-white p-10 text-center text-muted">
          불러오는 중...
        </div>
      )}

      {!loading && error && (
        <div className="border border-border rounded-lg bg-white p-10 text-center">
          <p className="text-sm text-muted">{error.message}</p>
          {error.type === "NOT_GENERATED" && (
            <p className="text-xs text-muted mt-2">
              리포트는 매일 자정에 전날 데이터를 기준으로 생성됩니다.
            </p>
          )}
        </div>
      )}

      {!loading && !error && report && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="전체 이벤트" value={report.totalCount ?? 0} />
            <StatCard label="심각" value={report.criticalCount ?? 0} />
            <StatCard label="주의" value={report.warningCount ?? 0} />
            <StatCard label="안전" value={report.infoCount ?? 0} />
          </div>

          <section className="border border-border rounded-lg bg-white p-5">
            <h2 className="text-[13px] font-bold text-ink mb-4">
              위험 등급 분포
            </h2>
            {(report.totalCount ?? 0) === 0 ? (
              <p className="text-sm text-muted">
                해당 날짜에 기록된 이벤트가 없습니다.
              </p>
            ) : (
              <SeverityBar report={report} />
            )}
          </section>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <StatCard label="조치 완료율" muted note="집계 예정" />
            <StatCard label="오탐 건수" muted note="집계 예정" />
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportPage;
