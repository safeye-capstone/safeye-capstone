import { useCallback, useEffect, useState } from "react";
import { getTodayKST } from "../utils/date";

const CHECK_INTERVAL_MS = 30_000;

/**
 * KST 기준 오늘 날짜. 자정을 넘기면 자동으로 갱신됩니다.
 * 백그라운드 탭에서는 타이머가 늦어질 수 있어, 탭으로 돌아올 때도 확인합니다.
 */
export function useTodayKST() {
  const [today, setToday] = useState(getTodayKST);

  // 값이 같으면 React가 리렌더링하지 않습니다.
  const sync = useCallback(() => setToday(getTodayKST()), []);

  useEffect(() => {
    const timer = setInterval(sync, CHECK_INTERVAL_MS);
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("focus", sync);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("focus", sync);
    };
  }, [sync]);

  return [today, sync];
}
