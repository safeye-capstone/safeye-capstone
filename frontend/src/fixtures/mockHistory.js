const ZONES = ["A동 타설구역", "B동 자재창고", "C동 용접구역", "D동 외벽"];

// 판정 값마다 어울리는 설명
const SAMPLES = {
  CONFIRMED: [
    "작업자가 안전모를 착용하지 않은 상태로 타설 구역을 이동하고 있습니다.",
    "펌프카 붐대 하부로 작업자가 통행하고 있습니다.",
    "안전난간이 설치되지 않은 발판 단부에서 작업 중입니다.",
  ],
  REVIEW_REQUIRED: [
    "용접 작업 중 불티 비산 방지 덮개가 확인되지 않습니다.",
    "안전대를 착용했으나 걸이 설비에 체결했는지 확인되지 않습니다.",
    "자재 적치 높이가 기준을 초과한 것으로 보입니다.",
  ],
  REJECTED: [
    "단부 접근으로 보였으나 재검증 결과 안전난간 안쪽 작업으로 확인되었습니다.",
    "안전모 미착용으로 보였으나 재검증 결과 착용 상태로 확인되었습니다.",
  ],
  NO_DETECTION: [
    "작업자 전원이 안전모와 안전화를 착용하고 있습니다.",
    "통로 확보 상태가 양호하며 특이 위험 요소가 없습니다.",
    "자재 적치 상태가 안정적입니다.",
  ],
};

// 판정 값에 맞는 severity (API 규격 기준)
const SEVERITY_BY_STATE = {
  CONFIRMED: "CRITICAL",
  REVIEW_REQUIRED: "WARNING",
  REJECTED: "INFO",
  NO_DETECTION: "INFO",
};

// 대략 위험 18% / 경고 36%(검토 대기 18% + 기각 18%) / 안전 45%
const STATE_POOL = [
  ...Array(2).fill("CONFIRMED"),
  ...Array(2).fill("REVIEW_REQUIRED"),
  ...Array(2).fill("REJECTED"),
  ...Array(5).fill("NO_DETECTION"),
];

function pick(arr, i) {
  return arr[i % arr.length];
}

// 이력은 안전 관리자 화면이라 판정 불명(값 없음)은 넣지 않는다
export const MOCK_HISTORY = Array.from({ length: 45 }, (_, i) => {
  const decisionState = pick(STATE_POOL, i * 3 + 1);
  const isAlert = decisionState !== "NO_DETECTION";

  // 최근 것부터 약 40분 간격
  const detectedAt = new Date(
    Date.now() - i * 40 * 60 * 1000 - (i % 7) * 3 * 60 * 1000,
  ).toISOString();

  return {
    id: `mock-${String(i + 1).padStart(3, "0")}`,
    zoneName: pick(ZONES, i * 2 + 1),
    severity: SEVERITY_BY_STATE[decisionState],
    vlmDescription: pick(SAMPLES[decisionState], i),
    ragMetadata: { vlm_decision_state: decisionState },
    detectedAt,
    isResolved: isAlert && i % 4 === 0,
  };
});
