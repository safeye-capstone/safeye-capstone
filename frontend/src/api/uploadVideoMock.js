//   /analyze/video?mock&state=REVIEW_REQUIRED   판정 바꾸기 (CONFIRMED 기본, NO_DETECTION, UNKNOWN 등)
import { ApiError } from "./apiError";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// 사용법 (개발 서버 전용)
//   /analyze/video?mock              8초 뒤 성공
//   /analyze/video?mock&delay=70     70초 뒤 성공 (경과 시간 "1분 10초" 확인용)
//   /analyze/video?mock=fail         VLM-001, reason 없음
//   /analyze/video?mock=timeout      VLM-001, reason TIMEOUT
export async function mockVideoRequest(file) {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mock");
  const delaySec = Number(params.get("delay")) || 8;
  const state = params.get("state") ?? "CONFIRMED";
  const severity =
    { CONFIRMED: "CRITICAL", REVIEW_REQUIRED: "WARNING" }[state] ?? "INFO";

  await wait(delaySec * 1000);

  if (mode === "fail" || mode === "timeout") {
    throw new ApiError({
      status: 502,
      code: "VLM-001",
      message: "VLM 서버 오류",
      details: mode === "timeout" ? { reason: "TIMEOUT" } : undefined,
    });
  }

  return {
    id: crypto.randomUUID(),
    isDanger: severity !== "INFO",
    zoneName: "목 데이터 구역",
    severity,
    // 방금 고른 파일을 그대로 재생해서 <video> 렌더링을 확인
    fileUrl: URL.createObjectURL(file),
    vlmDescription:
      "작업자가 안전모를 착용하지 않은 채 개구부 주변을 이동하는 장면이 영상 전반에 걸쳐 확인됩니다.",
    violatedRegulation: null,
    actionGuide: "즉시 작업을 중지하고 안전모 착용 후 작업을 재개하세요.",
    ragMetadata: { vlm_decision_state: "CONFIRMED" },
    isResolved: false,
    detectedAt: new Date().toISOString(),
    resolvedAt: null,
  };
}
