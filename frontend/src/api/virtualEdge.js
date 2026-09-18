import { API_BASE } from "../constants/config";

async function post(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  const body = await res.json().catch(() => null);

  if (!res.ok || body?.success === false) {
    throw new Error(
      body?.error?.message ?? `요청에 실패했습니다 (${res.status})`,
    );
  }

  return body?.data ?? null;
}

export const startVirtualEdge = () => post("/api/virtual-edge/start");
export const stopVirtualEdge = () => post("/api/virtual-edge/stop");
