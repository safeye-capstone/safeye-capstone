import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../constants/config";

export function useDangerAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const seenIdsRef = useRef(new Set());

  const addAlert = useCallback((event) => {
    if (!event) return;

    const key = event.id ?? `manual-${Date.now()}`;
    if (seenIdsRef.current.has(key)) return;
    seenIdsRef.current.add(key);

    setAlerts((prev) => [{ ...event, id: key }, ...prev]);
  }, []);

  useEffect(() => {
    const url = `${API_BASE}/api/alerts/subscribe`;
    const source = new EventSource(url);

    source.addEventListener("connected", () => {
      setConnected(true);
    });

    source.addEventListener("danger", (e) => {
      console.log("SSE 수신:", e.data);
      addAlert(JSON.parse(e.data));
    });

    source.onerror = () => {
      setConnected(false);
    };

    return () => {
      source.close();
    };
  }, [addAlert]);

  return { alerts, connected, pushAlert: addAlert };
}
