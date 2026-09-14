import { useState, useEffect } from "react";
import { API_BASE } from "../constants/config";

function StatsSummary() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/results`);
        const json = await response.json();
        setResults(json.data ?? []);
      } catch (err) {
        setError("통계를 불러오는 데 실패했습니다.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, []);

  if (loading) return <div className="p-4 text-muted">통계 불러오는 중...</div>;
  if (error)
    return <div className="p-4 text-danger font-semibold">{error}</div>;

  const total = results.length;
  const dangerCount = results.filter((item) => item.isDanger).length;
  const thisWeekCount = total;

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <StatCard label="총 분석 건수" value={total} unit="건" />
      <StatCard
        label="고위험 발견"
        value={dangerCount}
        unit="건"
        color="text-danger"
      />
      <StatCard label="이번 주 분석" value={thisWeekCount} unit="건" />
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
