import { useState, useEffect, useCallback, useRef } from "react";
import { createAlertStream } from "../api/alerts";
import { createId } from "../utils/id";
import { getAlertKind } from "../constants/decisionState";

const MAX_ALERTS = 100;
const INITIAL_RETRY_MS = 3000;
const MAX_RETRY_MS = 30000;

export function useDangerAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const seenIdsRef = useRef(new Set());

  const addAlert = useCallback((event) => {
    if (!event) return;

    // 확정 위험·검토 대기만 경보로 다룬다.
    // 판정 값이 없으면 severity가 INFO가 아닌 것만 (getAlertKind가 판단)
    if (!getAlertKind(event)) return;

    const id = event.id ?? createId("manual");

    if (seenIdsRef.current.has(id)) return;

    seenIdsRef.current.add(id);

    setAlerts((prev) => [{ ...event, id }, ...prev].slice(0, MAX_ALERTS));
  }, []);

  useEffect(() => {
    let source = null;
    let retryTimer = null;
    let retryDelay = INITIAL_RETRY_MS;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      source = createAlertStream();

      source.addEventListener("connected", () => {
        retryDelay = INITIAL_RETRY_MS;
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

        if (source.readyState !== EventSource.CLOSED) return;

        source.close();
        retryTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RETRY_MS);
      };
    };

    connect();

    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      source?.close();
    };
  }, [addAlert]);

  return { alerts, connected, pushAlert: addAlert };
}
