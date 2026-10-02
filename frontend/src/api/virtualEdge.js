import { api } from "./client";

export const startVirtualEdge = () => api.post("/api/virtual-edge/start");
export const stopVirtualEdge = () => api.post("/api/virtual-edge/stop");
