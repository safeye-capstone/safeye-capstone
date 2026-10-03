import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Eye } from "lucide-react";
import {
  ALERT_KIND,
  getAlertKind,
  getDecisionView,
  isReviewRequired,
} from "../../constants/decisionState";
import { playSiren, unlockSiren } from "../../utils/siren";

const TOAST_DURATION_MS = 8000;

function ToastItem({ alert, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(alert.id), TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [alert.id, onDismiss]);

  const { label, tone, alertKind } = getDecisionView(alert);
  const isSiren = alertKind === ALERT_KIND.SIREN;
  const Icon = isSiren ? AlertTriangle : Eye;
  // 검토 대기는 "확인 필요"로 안내한다. 판정 값이 없는 폴백은 기존 라벨(심각/주의) 유지
  const title = isReviewRequired(alert) ? "확인 필요" : label;

  return (
    <div
      onClick={() => onDismiss(alert.id)}
      className={`w-[340px] rounded-[12px] border p-4 shadow-lg cursor-pointer ${tone.box}`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={16} className={tone.text} />
        <span className={`text-sm font-bold ${tone.text}`}>{title}</span>
        <span className="text-xs text-muted">{alert.zoneName}</span>
      </div>
      <p className="text-sm text-ink leading-relaxed line-clamp-3">
        {alert.vlmDescription}
      </p>
    </div>
  );
}

function AlertToast({ alerts }) {
  const [toasts, setToasts] = useState([]);
  const seenIds = useRef(new Set());

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // 첫 클릭·키 입력 때 소리 재생을 풀어둔다 (브라우저 자동재생 제한)
  useEffect(() => {
    window.addEventListener("pointerdown", unlockSiren);
    window.addEventListener("keydown", unlockSiren);
    return () => {
      window.removeEventListener("pointerdown", unlockSiren);
      window.removeEventListener("keydown", unlockSiren);
    };
  }, []);

  useEffect(() => {
    const fresh = alerts.filter(
      (a) => a.id && getAlertKind(a) && !seenIds.current.has(a.id),
    );
    if (fresh.length === 0) return;

    fresh.forEach((a) => seenIds.current.add(a.id));
    setToasts((prev) => [...fresh, ...prev]);

    // 확정 위험이 하나라도 있으면 사이렌. 검토 대기는 소리 없이 토스트만
    if (fresh.some((a) => getAlertKind(a) === ALERT_KIND.SIREN)) {
      playSiren();
    }
  }, [alerts]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-20 right-6 z-50 flex flex-col gap-3">
      {toasts.map((alert) => (
        <ToastItem key={alert.id} alert={alert} onDismiss={dismiss} />
      ))}
    </div>
  );
}

export default AlertToast;
