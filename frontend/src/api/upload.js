import { api } from "./client";
import { ApiError } from "./apiError";
import { mockVideoRequest } from "./uploadVideoMock";

// 백엔드 타임아웃(10분)보다 조금 길게: 백엔드의 TIMEOUT 응답을 먼저 받기 위함
const VIDEO_TIMEOUT_MS = 11 * 60 * 1000;

function toFormData(file, zoneId) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("zoneId", zoneId);
  return formData;
}

// VLM-001은 일반 실패 문구, details.reason이 TIMEOUT일 때만 시간 초과 문구
function toVideoError(err) {
  if (!(err instanceof ApiError) || err.code !== "VLM-001") return err;

  return new ApiError({
    status: err.status,
    code: err.code,
    details: err.details,
    message:
      err.details?.reason === "TIMEOUT"
        ? "분석 시간이 초과됐습니다. 더 짧은 영상으로 다시 시도해주세요."
        : "영상 분석에 실패했습니다. 잠시 후 다시 시도해주세요.",
  });
}

// 개발 서버에서 주소에 ?mock이 붙어 있을 때만 가짜 응답 사용
const isVideoMock = () =>
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).has("mock");

export const uploadImage = (file, zoneId) =>
  api.post("/api/upload/file", toFormData(file, zoneId));

export async function uploadVideo(file, zoneId) {
  try {
    if (isVideoMock()) return await mockVideoRequest(file);

    return await api.post("/api/upload/file", toFormData(file, zoneId), {
      timeoutMs: VIDEO_TIMEOUT_MS,
    });
  } catch (err) {
    throw toVideoError(err);
  }
}
