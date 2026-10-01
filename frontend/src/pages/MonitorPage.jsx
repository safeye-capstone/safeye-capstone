import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Play, Square, Radio, AlertTriangle } from "lucide-react";
import { startVirtualEdge, stopVirtualEdge } from "../api/virtualEdge";
import { formatTime } from "../utils/formatDate";
import { getSeverityTone } from "../constants/severity";
import SeverityBadge from "../components/common/SeverityBadge";
import PageHeader from "../components/layout/PageHeader";

export default function MonitorPage() {
  const { alerts = [], connected = false } = useOutletContext() ?? {};
  const [running, setRunning] = useState(false);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  const handleToggle = async () => {
    setPending(true);
    setError(null);
    try {
      if (running) {
        const message = await stopVirtualEdge();
        setStatus(message);
        setRunning(false);
      } else {
        const message = await startVirtualEdge();
        setStatus(message);
        setRunning(true);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader />

      <div className="flex items-center justify-between rounded-[14px] border border-border bg-white p-5">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-10 w-10 items-center justify-center rounded-full ${
              running ? "bg-safe-bg text-safe" : "bg-border text-muted"
            }`}
          >
            <Radio
              size={18}
              className={running ? "animate-pulse" : undefined}
            />
          </span>
          <div>
            <p className="font-semibold text-ink">
              {running ? "가상 엣지 구동 중" : "가상 엣지 정지됨"}
            </p>
            <p className="text-xs text-muted">
              {status ?? "대기 중"} / 실시간 알림{" "}
              {connected ? "연결됨" : "끊김"} / 수신 {alerts.length}건
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleToggle}
          disabled={pending}
          className={`flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
            running ? "bg-ink hover:bg-ink/85" : "bg-accent hover:bg-accent/90"
          }`}
        >
          {running ? <Square size={16} /> : <Play size={16} />}
          {pending ? "처리 중..." : running ? "감시 중지" : "감시 시작"}
        </button>
      </div>

      {error && (
        <div className="rounded-[10px] border border-border bg-danger-bg px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="rounded-[14px] border border-border bg-white">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-[14.5px] font-bold">실시간 경보 로그</h2>
        </div>

        {alerts.length === 0 ? (
          <p className="px-5 py-12 text-center text-sm text-muted">
            아직 수신된 경보가 없습니다.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {alerts.map((alert) => (
              <li key={alert.id} className="flex gap-4 px-5 py-4">
                <AlertTriangle
                  size={18}
                  className={`mt-0.5 shrink-0 ${getSeverityTone(alert.severity).text}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={alert.severity} />
                    <span className="text-sm font-medium text-ink">
                      {alert.zoneName ?? "구역 미상"}
                    </span>
                    <span className="text-xs text-muted">
                      {formatTime(alert.detectedAt)}
                    </span>
                  </div>
                  <p className="text-sm text-ink">{alert.vlmDescription}</p>
                  {alert.actionGuide && (
                    <p className="mt-1 text-xs text-muted">
                      조치: {alert.actionGuide}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
