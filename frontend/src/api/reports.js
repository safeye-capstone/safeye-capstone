import { api } from "./client";

export function getDailyReport(date, options) {
  const query = `?${new URLSearchParams({ date })}`;
  return api.get(`/api/reports/daily${query}`, options);
}

export function createTodayReport(options) {
  return api.post("/api/reports/daily/today", undefined, options);
}
