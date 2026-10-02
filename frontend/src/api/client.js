import { API_BASE } from "../constants/config";
import { ApiError, toErrorMessage } from "./apiError";

async function request(path, { method = "GET", body, signal } = {}) {
  const init = { method, signal };

  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError({
      status: 0,
      code: "NETWORK",
      message: "서버에 연결할 수 없습니다.",
    });
  }

  const text = await res.text();

  let json = null;

  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      if (res.ok) {
        throw new ApiError({
          status: res.status,
          code: "INVALID_RESPONSE",
          message: "서버 응답 형식이 올바르지 않습니다.",
        });
      }
    }
  }

  if (!res.ok || json?.success == false) {
    throw new ApiError({
      status: res.status,
      code: json?.error?.code,
      message: toErrorMessage(res.status, json?.error),
      details: json?.error?.details,
    });
  }

  return json?.data ?? null;
}

export const api = {
  get: (path, options) => request(path, options),
  post: (path, body, options) =>
    request(path, { ...options, method: "POST", body }),
};
