import { API_BASE } from "../constants/config";
import { ApiError, toErrorMessage } from "./apiError";

async function request(path, { method = "GET", body, signal, timeoutMs } = {}) {
  // 호출한 쪽의 취소(signal)와 타임아웃을 하나의 controller로 합친다
  const controller = new AbortController();
  let timedOut = false;

  const abortFromCaller = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener("abort", abortFromCaller, { once: true });

  const timer = timeoutMs
    ? setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : null;

  const init = { method, signal: controller.signal };

  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let res;
  let text;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
    text = await res.text();
  } catch (err) {
    if (timedOut) {
      throw new ApiError({
        status: 0,
        code: "CLIENT_TIMEOUT",
        message:
          "서버 응답이 없어 요청을 중단했습니다. 잠시 후 다시 시도해주세요.",
      });
    }
    if (err.name === "AbortError") throw err;
    throw new ApiError({
      status: 0,
      code: "NETWORK",
      message: "서버에 연결할 수 없습니다.",
    });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abortFromCaller);
  }

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
