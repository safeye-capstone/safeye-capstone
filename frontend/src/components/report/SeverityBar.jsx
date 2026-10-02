import { SEVERITY_BADGE, SEVERITY_TONE } from "../../constants/severity";

const SEGMENTS = [
  { key: "criticalCount", severity: "CRITICAL" },
  { key: "warningCount", severity: "WARNING" },
  { key: "infoCount", severity: "INFO" },
].map((s) => ({
  ...s,
  label: SEVERITY_BADGE[s.severity].label,
  color: SEVERITY_TONE[s.severity].solid,
}));

function SeverityBar({ report }) {
  const total = report.totalCount ?? 0;

  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-border">
        {total > 0 &&
          SEGMENTS.map(({ key, color }) => {
            const count = report[key] ?? 0;
            if (count === 0) return null;
            return (
              <div
                key={key}
                className={color}
                style={{ width: `${(count / total) * 100}%` }}
              />
            );
          })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3">
        {SEGMENTS.map(({ key, label, color }) => {
          const count = report[key] ?? 0;
          const percent = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div key={key} className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${color}`} />
              <span className="text-xs text-muted">{label}</span>
              <span className="text-xs font-semibold text-ink">{count}건</span>
              <span className="text-xs text-muted">({percent}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default SeverityBar;
