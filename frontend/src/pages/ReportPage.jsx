import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import SeverityBar from "../components/report/SeverityBar";
import GenerateReportButton from "../components/report/GenerateReportButton";
import ZoneStatsTable from "../components/report/ZoneStatsTable";
import { useDailyReport } from "../hooks/useDailyReport";
import { useTodayKST } from "../hooks/useTodayKST";
import { addDays, formatReportDate } from "../utils/date";
import { SEVERITY_BADGE } from "../constants/severity";
import { DECISION_STATES } from "../constants/decisionState";
import { FEATURE_RESOLUTION_STATS } from "../constants/config";

const PENDING_NOTE = "집계 예정";

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
  const [today, syncToday] = useTodayKST();
  const [date, setDate] = useState(today);
  const isToday = date === today;

  const {
    report,
    notGenerated,
    error,
    loading,
    reload,
    generate,
    generating,
    generateError,
  } = useDailyReport(date);

  const handleGenerate = async () => {
    const result = await generate();

    // 자정을 넘겨 서버가 새 날짜를 집계한 경우, 그 날짜로 이동합니다.
    if (result?.status === "DATE_CHANGED") {
      syncToday();
      setDate(result.targetDate);
    }
  };

  const summary = report?.summary;
  const decisionCounts = summary?.decisionStateCounts ?? {};
  const pending = !FEATURE_RESOLUTION_STATS;

  return (
    <div className="w-full max-w-4xl">
      <PageHeader />

      <div className="flex items-center gap-3 mb-5">
        <button
          type="button"
          onClick={() => setDate(addDays(date, -1))}
          className="p-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          aria-label="이전 날짜"
        >
          <ChevronLeft size={16} />
        </button>

        <span className="text-sm font-bold text-ink min-w-[11rem] text-center">
          {formatReportDate(date)}
        </span>

        <button
          type="button"
          onClick={() => setDate(addDays(date, 1))}
          disabled={date >= today}
          className="p-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          aria-label="다음 날짜"
        >
          <ChevronRight size={16} />
        </button>

        {!isToday && (
          <button
            type="button"
            onClick={() => setDate(today)}
            className="text-xs text-muted underline ml-1"
          >
            오늘로
          </button>
        )}
      </div>

      {isToday && (
        <GenerateReportButton
          hasReport={Boolean(report)}
          generating={generating}
          disabled={loading}
          error={generateError}
          onGenerate={handleGenerate}
        />
      )}

      {loading && (
        <div className="border border-border rounded-lg bg-white p-10 text-center text-muted">
          불러오는 중...
        </div>
      )}

      {!loading && notGenerated && (
        <div className="border border-dashed border-border rounded-lg bg-white p-10 text-center">
          <p className="text-sm text-muted">
            아직 리포트가 생성되지 않았습니다.
          </p>
          <p className="text-xs text-muted mt-2">
            {isToday
              ? "위의 버튼으로 현재까지의 중간 집계를 만들 수 있습니다."
              : "리포트는 매일 자정에 전날 데이터를 기준으로 생성됩니다."}
          </p>
        </div>
      )}

      {!loading && error && (
        <div
          role="alert"
          className="border border-border rounded-lg bg-white p-10 text-center"
        >
          <p className="text-sm text-muted">{error.message}</p>
          {error.type === "UNKNOWN" && (
            <button
              type="button"
              onClick={reload}
              className="text-xs text-muted underline mt-2"
            >
              다시 시도
            </button>
          )}
        </div>
      )}

      {!loading && !error && report && (
        <div className="flex flex-col gap-4">
          {summary?.message && (
            <p className="text-sm text-ink">{summary.message}</p>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="전체 이벤트" value={report.totalCount ?? 0} />
            <StatCard
              label={SEVERITY_BADGE.CRITICAL.label}
              value={report.criticalCount ?? 0}
            />
            <StatCard
              label={SEVERITY_BADGE.WARNING.label}
              value={report.warningCount ?? 0}
            />
            <StatCard
              label={SEVERITY_BADGE.INFO.label}
              value={report.infoCount ?? 0}
            />
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

          <section>
            <h2 className="text-[13px] font-bold text-ink mb-3">판정별 건수</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {DECISION_STATES.map(({ key, label }) => (
                <StatCard
                  key={key}
                  label={label}
                  value={decisionCounts[key] ?? 0}
                />
              ))}
            </div>
          </section>

          <ZoneStatsTable zoneStats={summary?.zoneStats} />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <StatCard
              label="조치 완료율"
              value={summary?.resolutionRate ?? 0}
              unit="%"
              muted={pending}
              note={PENDING_NOTE}
            />
            <StatCard
              label="조치 건수"
              value={report.resolvedCount ?? 0}
              muted={pending}
              note={PENDING_NOTE}
            />
            <StatCard
              label="오탐 건수"
              value={report.falseAlarmCount ?? 0}
              muted={pending}
              note={PENDING_NOTE}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportPage;
