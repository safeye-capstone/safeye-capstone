import { normalizeSeverity } from "../../constants/severity";
import { start0fWeek } from "../../utils/date";

function StatsSummary({ items = [], liveAlertCount = 0 }) {
  const weekStart = start0fWeek();

  const total = items.length;
  const criticalCount = items.filter(
    (item) => normalizeSeverity(item.severity) === "CRITICAL",
  ).length;
  const thisWeekCount = items.filter(
    (item) => item.detectedAt && new Date(item.detectedAt) >= weekStart,
  ).length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <StatCard label="총 분석 건수" value={total} unit="건" />
      <StatCard
        label="심각 발견"
        value={criticalCount}
        unit="건"
        color="text-danger"
      />
      <StatCard label="이번 주 분석" value={thisWeekCount} unit="건" />
      <StatCard label="실시간 수신 경보" value={liveAlertCount} unit="건" />
    </div>
  );
}

function StatCard({ label, value, unit, color = "text-ink" }) {
  return (
    <div className="bg-white border border-border rounded-[14px] p-5">
      <p className="text-[13px] text-muted font-semibold mb-2.5">{label}</p>
      <div className="flex items-baseline gap-1.5">
        <p className={`text-[28px] font-extrabold ${color}`}>{value}</p>
        <p className="text-[13px] text-muted">{unit}</p>
      </div>
    </div>
  );
}

export default StatsSummary;
