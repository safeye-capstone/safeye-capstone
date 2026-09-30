import { useState, useEffect, useCallback, useRef } from "react";
import { createAlertStream } from "../api/alerts";

const MAX_ALERTS = 100;

export function useDangerAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const seenIdsRef = useRef(new Set());

  const addAlert = useCallback((event) => {
    if (!event) return;

    const id =
      event.id ?? `manual-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    if (seenIdsRef.current.has(id)) return;
    seenIdsRef.current.add(id);

    setAlerts((prev) => [{ ...event, id }, ...prev].slice(0, MAX_ALERTS));
  }, []);

  useEffect(() => {
    const source = createAlertStream();

    source.addEventListener("connected", () => {
      setConnected(true);
    });

    source.addEventListener("danger", (e) => {
      try {
        addAlert(JSON.parse(e.data));
      } catch (err) {
        console.error("SSE 데이터 파싱 실패:", e.data, err);
      }
    });

    source.onerror = () => {
      setConnected(false);
    };

    return () => source.close();
  }, [addAlert]);

  return { alerts, connected, pushAlert: addAlert };
}
