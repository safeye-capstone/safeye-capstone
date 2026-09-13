import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";

const SEVERITY_LABEL = {
  CRITICAL: "심각",
  CRITICAL_PINCH: "심각",
  WARNING: "주의",
};

function ToastItem({ alert, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(alert.id), 8000);
    return () => clearTimeout(timer);
  }, [alert.id, onDismiss]);

  const isCritical = alert.severity.startsWith("CRITICAL");

  return (
    <div
      onClick={() => onDismiss(alert.id)}
      className={`w-[340px] rounded-[12px] border p-4 shadow-lg cursor-pointer bg-white ${
        isCritical ? "border-danger" : "border-warn"
      }`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <AlertTriangle
          size={16}
          className={isCritical ? "text-danger" : "text-warn"}
        />
        <span
          className={`text-sm font-bold ${isCritical ? "text-danger" : "text-warn"}`}
        >
          {SEVERITY_LABEL[alert.severity] ?? alert.severity}
        </span>
        <span className="text-xs text-muted">{alert.zoneName}</span>
      </div>
      <p className="text-sm text-ink leading-relaxed">{alert.vlmDescription}</p>
    </div>
  );
}

function AlertToast({ alerts }) {
  const [toasts, setToasts] = useState([]);
  const seenIds = useRef(new Set());

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    const fresh = alerts.filter((a) => a.id && !seenIds.current.has(a.id));
    if (fresh.length === 0) return;

    fresh.forEach((a) => seenIds.current.add(a.id));
    setToasts((prev) => [...fresh, ...prev]);
  }, [alerts]);

  if (toasts.length == 0) return null;

  return (
    <div className="fixed top-20 right-6 z-50 flex flex-col gap-3">
      {toasts.map((alert) => (
        <ToastItem key={alert.id} alert={alert} onDismiss={dismiss} />
      ))}
    </div>
  );
}

export default AlertToast;
