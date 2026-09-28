import { api } from "./client";

export const getZones = (options) => api.get("/api/zones", options);
