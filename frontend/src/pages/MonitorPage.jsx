import { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { Play, Square, Radio, AlertTriangle } from "lucide-react";
import { startVirtualEdge, stopVirtualEdge } from "../api/virtualEdge";

const TOTAL_IMAGES = 44;
const PUSH_RATE_SEC = 6;

const SEVERITY_STYLE = {
  CRITICAL: { label: "위험", cls: "border-red-200 bg-red-50 text-red-700" },
  WARNING: {
    label: "주의",
    cls: "border-amber-200 bg-amber-50 text-amber-700",
  },
  INFO: {
    label: "안전",
    cls: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
};

function formatTime(instant) {
  if (!instant) return "-";
  return new Date(instant).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function MonitorPage() {
  const { alerts = [], connected = false } = useOutletContext() ?? {};
  const [running, setRunning] = useState(false);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!running) return;

    const timer = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          setRunning(false);
          setStatus("모의 이미지 전송 완료");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [running]);

  const handleToggle = async () => {
    setPending(true);
    setError(null);
    try {
      if (running) {
        const message = await stopVirtualEdge();
        setStatus(message);
        setRunning(false);
        setRemaining(0);
      } else {
        const message = await startVirtualEdge();
        setStatus(message);
        setRemaining(TOTAL_IMAGES * PUSH_RATE_SEC);
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
      <p className="text-sm text-gray-500">
        가상 엣지 디바이스를 구동하여 현장 영상 수집 상황을 재현하고, 위험
        판정을 실시간으로 수신합니다.
      </p>

      <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-10 w-10 items-center justify-center rounded-full ${
              running
                ? "bg-emerald-50 text-emerald-600"
                : "bg-gray-100 text-gray-400"
            }`}
          >
            <Radio
              size={18}
              className={running ? "animate-pulse" : undefined}
            />
          </span>
          <div>
            <p className="font-semibold text-gray-900">
              {running
                ? `가상 엣지 구동 중 (약 ${remaining}초 남음)`
                : "가상 엣지 정지됨"}
            </p>
            <p className="text-xs text-gray-500">
              {status ?? "대기 중"} / 실시간 알림{" "}
              {connected ? "연결됨" : "끊김"} / 수신 {alerts.length}건
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleToggle}
          disabled={pending}
          className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${
            running
              ? "bg-gray-800 hover:bg-gray-900"
              : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {running ? <Square size={16} /> : <Play size={16} />}
          {pending ? "처리 중..." : running ? "감시 중지" : "감시 시작"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-semibold text-gray-900">실시간 경보 로그</h2>
        </div>

        {alerts.length === 0 ? (
          <p className="px-5 py-12 text-center text-sm text-gray-400">
            아직 수신된 경보가 없습니다.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {alerts.map((alert, idx) => {
              const style =
                SEVERITY_STYLE[alert.severity] ?? SEVERITY_STYLE.INFO;
              return (
                <li key={alert.id ?? idx} className="flex gap-4 px-5 py-4">
                  <AlertTriangle
                    size={18}
                    className="mt-0.5 shrink-0 text-gray-400"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded border px-2 py-0.5 text-xs font-semibold ${style.cls}`}
                      >
                        {style.label}
                      </span>
                      <span className="text-sm font-medium text-gray-900">
                        {alert.zoneName ?? "구역 미상"}
                      </span>
                      <span className="text-xs text-gray-400">
                        {formatTime(alert.detectedAt)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">
                      {alert.vlmDescription}
                    </p>
                    {alert.actionGuide && (
                      <p className="mt-1 text-xs text-gray-500">
                        조치: {alert.actionGuide}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
