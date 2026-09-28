export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8080";

if (!import.meta.env.VITE_API_URL) {
  console.warn("[SAFEye] VITE_API_URL 미설정 - 기본값 사용: .env.example 참고");
}

export const MAX_IMAGE_SIZE_MB = 10;
export const MAX_VIDEO_SIZE_MB = 50;
