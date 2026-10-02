export class ApiError extends Error {
  constructor({ status, code, message, details }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function toErrorMessage(status, error) {
  if (status === 413) {
    return "파일 용량이 서버 제한을 초과했습니다.";
  }

  const limit = error?.details?.limit;
  if (limit) {
    const limitMB = Math.round(Number(limit) / (1024 * 1024));
    return `파일이 너무 큽니다. ${limitMB}MB까지 업로드할 수 있어요.`;
  }

  return error?.message ?? `요청에 실패했습니다 (${status})`;
}
