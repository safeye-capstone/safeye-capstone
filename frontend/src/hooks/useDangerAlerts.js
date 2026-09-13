import { useState, useEffect } from "react";

export function useDangerAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const url = `${import.meta.env.VITE_API_URL}/api/alerts/subscribe`;
    const source = new EventSource(url);

    source.addEventListener("connected", () => {
      setConnected(true);
    });

    source.addEventListener("danger", (e) => {
      const alert = JSON.parse(e.data);
      setAlerts((prev) => [alert, ...prev]);
    });

    source.onerror = () => {
      setConnected(false);
    };

    return () => {
      source.close();
    };
  }, []);

  return { alerts, connected };
}
