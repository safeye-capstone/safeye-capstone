import StatsSummary from "../components/dashboard/StatsSummary";
import { useOutletContext } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import SeverityBadge from "../components/common/SeverityBadge";
import SampleDataNotice from "../components/common/SampleDataNotice";
import { MOCK_HISTORY } from "../fixtures/mockHistory";

const RECENT_ALERT_LIMIT = 5;

function DashboardPage() {
  const { alerts, connected } = useOutletContext();
  const recentAlerts = alerts.slice(0, RECENT_ALERT_LIMIT);
  const hiddenCount = alerts.length - recentAlerts.length;

  return (
    <div>
      <PageHeader />

      <SampleDataNotice>
        분석 통계는 샘플 데이터 기준입니다. 조회 API 연동 후 실제 수치가
        표시됩니다.
      </SampleDataNotice>

      <StatsSummary items={MOCK_HISTORY} liveAlertCount={alerts.length} />

      <div className="bg-white border border-border rounded-[14px] p-6">
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

        {recentAlerts.length === 0 ? (
          <p className="text-muted text-sm">수신된 경보가 없습니다.</p>
        ) : (
          <>
            {recentAlerts.map((alert) => (
              <div
                key={alert.id}
                className="border-b border-border py-3 last:border-0"
              >
                <div className="flex items-center gap-2 mb-1">
                  <SeverityBadge severity={alert.severity} />
                  <span className="text-xs text-muted">{alert.zoneName}</span>
                </div>
                <p className="text-sm text-ink">{alert.vlmDescription}</p>
              </div>
            ))}
            {hiddenCount > 0 && (
              <p className="pt-3 text-xs text-muted">
                외 {hiddenCount}건은 실시간 감시 화면에서 확인할 수 있습니다.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;
