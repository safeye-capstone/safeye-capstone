import { useEffect, useState } from "react";
import { API_BASE } from "../constants/config";

export function useZones() {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    fetch(`${API_BASE}/api/zones`)
      .then((res) => res.json())
      .then((body) => {
        if (alive) setZones(body.data ?? []);
      })
      .catch(() => {
        if (alive) setZones([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  return { zones, loading };
}
