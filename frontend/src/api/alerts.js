import { API_BASE } from "../constants/config";

export const createAlertStream = () =>
  new EventSource(`${API_BASE}/api/alerts/subscribe`);
