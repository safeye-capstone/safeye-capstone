import { api } from "./client";

export function getDailyReport(date, options) {
  const query = date ? `?${new URLSearchParams({ date })}` : "";
  return api.get(`/api/reports/daily${query}`, options);
}
