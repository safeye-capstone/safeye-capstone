const SEGMENTS = [
  { key: "criticalCount", label: "심각", bar: "bg-danger", dot: "bg-danger" },
  { key: "warningCount", label: "주의", bar: "bg-warn", dot: "bg-warn" },
  { key: "infoCount", label: "안전", bar: "bg-safe", dot: "bg-safe" },
];

function SeverityBar({ report }) {
  const total = report.totalCount ?? 0;

  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-border">
        {total > 0 &&
          SEGMENTS.map(({ key, bar }) => {
            const count = report[key] ?? 0;
            if (count === 0) return null;
            return (
              <div
                key={key}
                className={bar}
                style={{ width: `${(count / total) * 100}%` }}
              />
            );
          })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3">
        {SEGMENTS.map(({ key, label, dot }) => {
          const count = report[key] ?? 0;
          const percent = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div key={key} className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${dot}`} />
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
