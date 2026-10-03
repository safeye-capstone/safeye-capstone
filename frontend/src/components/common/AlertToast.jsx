import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Eye, VolumeX } from "lucide-react";
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
  // 브라우저가 경보음을 막아서 사이렌을 못 울린 상태인지
  const [soundBlocked, setSoundBlocked] = useState(false);
  const soundBlockedRef = useRef(false);
  const seenIds = useRef(new Set());

  const markSoundBlocked = useCallback((blocked) => {
    soundBlockedRef.current = blocked;
    setSoundBlocked(blocked);
  }, []);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // 클릭·키 입력 때 소리 재생을 풀어둔다 (브라우저 자동재생 제한)
  useEffect(() => {
    const handleUnlock = async () => {
      const ready = await unlockSiren();
      if (!ready || !soundBlockedRef.current) return;

      // 막혀서 못 울린 사이렌을 한 번 울리고 배너를 내린다
      playSiren();
      markSoundBlocked(false);
    };

    window.addEventListener("pointerdown", handleUnlock);
    window.addEventListener("keydown", handleUnlock);
    return () => {
      window.removeEventListener("pointerdown", handleUnlock);
      window.removeEventListener("keydown", handleUnlock);
    };
  }, [markSoundBlocked]);

  useEffect(() => {
    const fresh = alerts.filter(
      (a) => a.id && getAlertKind(a) && !seenIds.current.has(a.id),
    );
    if (fresh.length === 0) return;

    fresh.forEach((a) => seenIds.current.add(a.id));
    setToasts((prev) => [...fresh, ...prev]);

    // 확정 위험이 하나라도 있으면 사이렌. 검토 대기는 소리 없이 토스트만
    if (fresh.some((a) => getAlertKind(a) === ALERT_KIND.SIREN)) {
      const played = playSiren();
      if (!played) markSoundBlocked(true);
    }
  }, [alerts, markSoundBlocked]);

  if (toasts.length === 0 && !soundBlocked) return null;

  return (
    <div className="fixed top-20 right-6 z-50 flex flex-col gap-3">
      {soundBlocked && (
        <div
          role="status"
          className="w-[340px] rounded-[12px] border border-border bg-white p-3 shadow-lg flex items-center gap-2 text-sm text-ink"
        >
          <VolumeX size={16} className="text-muted shrink-0" />
          <span className="break-keep">
            경보음이 꺼져 있습니다. 화면을 한 번 클릭하면 켜집니다.
          </span>
        </div>
      )}
      {toasts.map((alert) => (
        <ToastItem key={alert.id} alert={alert} onDismiss={dismiss} />
      ))}
    </div>
  );
}

export default AlertToast;
