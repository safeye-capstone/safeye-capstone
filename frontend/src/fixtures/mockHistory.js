const ZONES = ["A동 타설구역", "B동 자재창고", "C동 용접구역", "D동 외벽"];

const SAMPLES = {
  CRITICAL: [
    "작업자가 안전모를 착용하지 않은 상태로 타설 구역을 이동하고 있습니다.",
    "펌프카 붐대 하부로 작업자가 통행하고 있습니다.",
    "안전난간이 설치되지 않은 발판 단부에서 작업 중입니다.",
  ],
  WARNING: [
    "용접 작업 중 불티 비산 방지 덮개가 확인되지 않습니다.",
    "안전대를 착용했으나 걸이 설비에 체결하지 않았습니다.",
    "자재 적치 높이가 기준을 초과한 것으로 보입니다.",
  ],
  INFO: [
    "작업자 전원이 안전모와 안전화를 착용하고 있습니다.",
    "통로 확보 상태가 양호하며 특이 위험 요소가 없습니다.",
    "자재 적치 상태가 안정적입니다.",
  ],
};

// 실제 분포(약 18% / 18% / 64%)를 흉내냅니다
const SEVERITY_POOL = [
  ...Array(2).fill("CRITICAL"),
  ...Array(2).fill("WARNING"),
  ...Array(7).fill("INFO"),
];

function pick(arr, i) {
  return arr[i % arr.length];
}

export const MOCK_HISTORY = Array.from({ length: 45 }, (_, i) => {
  const severity = pick(SEVERITY_POOL, i * 3 + 1);
  const samples = SAMPLES[severity];

  // 최근 것부터 약 40분 간격
  const detectedAt = new Date(
    Date.now() - i * 40 * 60 * 1000 - (i % 7) * 3 * 60 * 1000,
  ).toISOString();

  return {
    id: `mock-${String(i + 1).padStart(3, "0")}`,
    zoneName: pick(ZONES, i * 2 + 1),
    severity,
    vlmDescription: pick(samples, i),
    detectedAt,
    isResolved: severity !== "INFO" && i % 4 === 0,
  };
});
