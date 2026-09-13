import StatsSummary from "../components/StatsSummary";
import ResultList from "../components/ResultList";
import { useOutletContext } from "react-router-dom";

function DashboardPage() {
  const { alerts, connected } = useOutletContext();

  return (
    <div>
      <StatsSummary />

      <div className="bg-white border border-border rounded-[14px] p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-[14.5px] font-bold">실시간 경보</h2>
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-safe" : "bg-muted"
            }`}
          />
          <span className="text-xs text-muted">
            {connected ? "연결됨" : "연결 끊김"}
          </span>
        </div>

        {alerts.length === 0 ? (
          <p className="text-muted text-sm">수신된 경보가 없습니다.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className="border-b border-border py-3 last:border-0"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`text-sm font-bold ${
                    alert.severity.startsWith("CRITICAL")
                      ? "text-danger"
                      : "text-warn"
                  }`}
                >
                  {alert.severity}
                </span>
                <span className="text-xs text-muted">{alert.zoneName}</span>
              </div>
              <p className="text-sm text-ink">{alert.vlmDescription}</p>
            </div>
          ))
        )}
      </div>

      <div className="bg-white border border-border rounded-[14px] p-6">
        <ResultList />
      </div>
    </div>
  );
}

export default DashboardPage;
